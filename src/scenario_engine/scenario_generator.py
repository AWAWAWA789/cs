"""情景生成器。

整合双轨融合、贝叶斯校准与多周期融合结果，输出 4-6 种标准未来走势情景。
每个情景的概率、方向、关键价位、仓位与浪形草图均由算法生成，不依赖 LLM，
也不使用成交量。
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

import numpy as np
import pandas as pd

from src.features.swing import identify_swing_points
from src.scenario_engine.adaptive_calibration import load_temperature
from src.scenario_engine.bayesian_calibration import calibrate_probabilities
from src.scenario_engine.fusion import fuse_results
from src.scenario_engine.multi_timeframe_fusion import fuse_timeframes
from src.scenario_engine.similarity_search import find_similar_states
from src.scenario_engine.state_vector import compute_state_vector, get_state_columns
from src.scenario_engine.template_matcher import match_templates


STANDARD_SCENARIOS = {
    "bullish_continuation": {
        "display_name": "上涨延续",
        "direction": 1,
        "description": "当前趋势向上，预计价格沿原方向继续运行。",
    },
    "bearish_reversal": {
        "display_name": "下跌反转",
        "direction": -1,
        "description": "当前出现顶部信号，预计价格转头向下。",
    },
    "dip_then_rise": {
        "display_name": "先跌后涨",
        "direction": 1,
        "description": "短线回调后继续上行，形成 higher low。",
    },
    "rally_then_fall": {
        "display_name": "先涨后跌",
        "direction": -1,
        "description": "短线反弹后继续下行，形成 lower high。",
    },
    "range_bound": {
        "display_name": "区间震荡",
        "direction": 0,
        "description": "多空力量均衡，价格在支撑与阻力之间波动。",
    },
    "weak_trend": {
        "display_name": "弱势整理",
        "direction": 0,
        "description": "趋势动能不足，等待方向选择。",
    },
}


MAX_POSITION_RISK = 0.02


def _direction_to_int(direction: Any) -> int:
    """将方向描述转换为整数。"""
    if isinstance(direction, (int, float)):
        return int(np.sign(direction))
    if isinstance(direction, str):
        return {"bullish": 1, "bearish": -1, "both": 0, "neutral": 0}.get(
            direction.lower(), 0
        )
    return 0


def _label_for_direction(direction: int) -> str:
    """将方向整数映射为标签。"""
    if direction > 0:
        return "bullish"
    if direction < 0:
        return "bearish"
    return "neutral"


def _extract_last_swings(df: pd.DataFrame, n: int = 4) -> list[dict[str, Any]]:
    """提取最近的 n 个 swing 高点/低点作为浪形草图关键点位。"""
    if len(df) < 10:
        return []
    feat_df = identify_swing_points(df, high_col="high", low_col="low", order=2)
    events: list[dict[str, Any]] = []
    for i in range(len(feat_df)):
        row = feat_df.iloc[i]
        if row["swing_high"]:
            events.append({
                "idx": i,
                "type": "high",
                "price": float(row["high"]),
            })
        if row["swing_low"]:
            events.append({
                "idx": i,
                "type": "low",
                "price": float(row["low"]),
            })
    events.sort(key=lambda e: e["idx"])
    return events[-n:]


def _compute_price_levels(
    df: pd.DataFrame,
    direction: int,
    support: float | None,
    resistance: float | None,
    target: float | None,
    stop_loss: float | None,
) -> dict[str, float | None]:
    """补全关键价位：如候选未提供，则基于最近 Swing 与 ATR 估算。"""
    close = float(df["close"].iloc[-1])
    atr = float(df["close"].diff().abs().rolling(window=20, min_periods=1).mean().iloc[-1])
    if atr <= 0 or np.isnan(atr):
        atr = close * 0.01

    recent_high = float(df["high"].tail(20).max())
    recent_low = float(df["low"].tail(20).min())

    if direction > 0:
        support = support if support is not None else recent_low
        resistance = resistance if resistance is not None else recent_high
        target = target if target is not None else close + (close - support) * 1.5
        stop_loss = stop_loss if stop_loss is not None else support - 0.5 * atr
    elif direction < 0:
        resistance = resistance if resistance is not None else recent_high
        support = support if support is not None else recent_low
        target = target if target is not None else close - (resistance - close) * 1.5
        stop_loss = stop_loss if stop_loss is not None else resistance + 0.5 * atr
    else:
        support = support if support is not None else recent_low
        resistance = resistance if resistance is not None else recent_high
        target = target if target is not None else (support + resistance) / 2
        stop_loss = stop_loss if stop_loss is not None else support - 0.5 * atr

    return {
        "support": round(support, 6),
        "resistance": round(resistance, 6),
        "target": round(target, 6),
        "stop_loss": round(stop_loss, 6),
    }


def _compute_position_size(
    probability: float,
    target: float,
    stop_loss: float,
    close: float,
    max_risk: float = MAX_POSITION_RISK,
) -> float:
    """基于凯利公式近似与最大风险约束输出仓位比例。"""
    if close <= 0 or target == stop_loss:
        return 0.0
    win = abs(target - close) / close
    loss = abs(stop_loss - close) / close
    if loss <= 0:
        return 0.0
    edge = probability - (1 - probability) * (loss / win) if win > 0 else 0.0
    kelly = max(0.0, edge) / (win / loss + 1e-12)
    # 限制最大风险敞口。
    return round(min(kelly, max_risk / (loss + 1e-12), 1.0), 6)


def _build_wave_sketch(
    df: pd.DataFrame,
    direction: int,
    support: float,
    resistance: float,
    target: float,
) -> list[dict[str, Any]]:
    """生成浪形草图关键点位序列。"""
    close = float(df["close"].iloc[-1])
    swings = _extract_last_swings(df, n=4)
    sketch = [
        {"label": "current", "price": round(close, 6), "type": "current"},
    ]
    for s in swings:
        sketch.append({
            "label": s["type"],
            "price": round(s["price"], 6),
            "type": s["type"],
            "idx": s["idx"],
        })

    if direction > 0:
        sketch.extend([
            {"label": "support", "price": round(support, 6), "type": "support"},
            {"label": "resistance", "price": round(resistance, 6), "type": "resistance"},
            {"label": "target", "price": round(target, 6), "type": "target"},
        ])
    elif direction < 0:
        sketch.extend([
            {"label": "resistance", "price": round(resistance, 6), "type": "resistance"},
            {"label": "support", "price": round(support, 6), "type": "support"},
            {"label": "target", "price": round(target, 6), "type": "target"},
        ])
    else:
        sketch.extend([
            {"label": "support", "price": round(support, 6), "type": "support"},
            {"label": "resistance", "price": round(resistance, 6), "type": "resistance"},
            {"label": "mid", "price": round((support + resistance) / 2, 6), "type": "mid"},
        ])

    # 按价格排序去重，便于可视化。
    seen = set()
    unique = []
    for pt in sketch:
        key = (pt["label"], round(pt["price"], 4))
        if key not in seen:
            seen.add(key)
            unique.append(pt)
    return unique


def _valid_source(source: Any) -> str:
    """确保 source 字段为合法值之一，避免 unknown 泄漏到最终输出。"""
    valid = {"similarity", "template", "fusion", "fallback"}
    normalized = str(source).lower() if isinstance(source, str) else ""
    if normalized == "fused":
        return "fusion"
    if normalized in valid:
        return normalized
    return "fallback"


def _map_to_standard_scenario(candidate: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    """将融合候选映射为一种标准情景，并补全所有字段。

    关键价位不直接使用候选中的模板投影值（可能来自历史价位或不同周期尺度），
    而是统一基于当前 DataFrame（日线或请求周期）的价格尺度重新估算，确保
    support/resistance/target/stop_loss 与 current close 处于同一价格尺度。
    """
    direction = _direction_to_int(candidate.get("direction", 0))
    label = _label_for_direction(direction)

    # 根据候选名称或方向选择标准情景键。
    name = candidate.get("name", "")
    std_key = "weak_trend"
    if direction > 0:
        if "flag" in name or "impulse" in name or "extension" in name or "continuation" in name:
            std_key = "bullish_continuation"
        elif "bottom" in name or "rise" in name or "dip" in name:
            std_key = "dip_then_rise"
        else:
            std_key = "bullish_continuation"
    elif direction < 0:
        if "top" in name or "reversal" in name or "fall" in name:
            std_key = "bearish_reversal"
        elif "rally" in name:
            std_key = "rally_then_fall"
        else:
            std_key = "bearish_reversal"
    else:
        std_key = "range_bound"

    meta = STANDARD_SCENARIOS[std_key]
    # 统一使用当前 df 的价格尺度重新计算关键价位。
    levels = _compute_price_levels(df, direction, None, None, None, None)

    close = float(df["close"].iloc[-1])
    position_size = _compute_position_size(
        float(candidate.get("probability", 0.0)),
        levels["target"] or close,
        levels["stop_loss"] or close,
        close,
    )

    wave_sketch = _build_wave_sketch(
        df,
        direction,
        levels["support"] or close,
        levels["resistance"] or close,
        levels["target"] or close,
    )

    return {
        "name": meta["display_name"],
        "scenario_key": std_key,
        "probability": round(float(candidate.get("probability", 0.0)), 6),
        "direction": direction,
        "direction_label": label,
        "support": levels["support"],
        "resistance": levels["resistance"],
        "target": levels["target"],
        "stop_loss": levels["stop_loss"],
        "position_size": position_size,
        "wave_sketch": wave_sketch,
        "description": meta["description"],
        "source": _valid_source(candidate.get("source", "fallback")),
    }


def _compute_probability_threshold(probabilities: list[float]) -> float:
    """计算动态概率入选门槛。

    规则：
    - 相对下界 = max(1 / n, 0.10)，n 为候选情景数；
    - 动态下界 = 第 3 大概率（若存在）的 50%；
    - 绝对硬底 = 0.05；
    - 最终门槛 = 三者最大值。
    """
    n = len(probabilities)
    if n == 0:
        return 0.0

    sorted_probs = sorted(probabilities, reverse=True)
    relative_floor = max(1.0 / n, 0.10)
    dynamic_floor = sorted_probs[2] * 0.5 if n >= 3 else 0.0
    absolute_floor = 0.05

    return float(max(relative_floor, dynamic_floor, absolute_floor))


def _normalize_probabilities(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对情景概率做重归一化，使总和为 1。"""
    total = sum(s["probability"] for s in scenarios)
    if total <= 0:
        equal = round(1.0 / len(scenarios), 6) if scenarios else 0.0
        for s in scenarios:
            s["probability"] = equal
        return scenarios

    for s in scenarios:
        s["probability"] = round(s["probability"] / total, 6)

    # 修正浮点误差：将余量加到最后一个元素。
    remainder = 1.0 - sum(s["probability"] for s in scenarios)
    if scenarios:
        scenarios[-1]["probability"] = round(scenarios[-1]["probability"] + remainder, 6)
    return scenarios


def _select_high_probability_scenarios(
    scenarios: list[dict[str, Any]],
    df: pd.DataFrame,
    min_scenarios: int = 2,
    max_scenarios: int = 4,
    target_scenarios: int = 3,
) -> list[dict[str, Any]]:
    """按动态概率门槛筛选情景，确保数量在 [min, max] 之间，并做概率重归一化。

    流程：
    1. 按 scenario_key 去重，保留概率最高者；
    2. 计算动态概率门槛，筛选高概率情景；
    3. 若数量不足目标值，依次补足次高概率情景（不低于 5% 绝对硬底）；
    4. 若仍不足最小值，从标准情景集合中补充 fallback 情景，fallback 概率固定为 0.20；
    5. 若超过最大值，截断到前 max_scenarios；
    6. 重归一化概率，使总和为 1。
    """
    if not scenarios:
        return []

    # 按 scenario_key 去重，保留概率最高者。
    by_key: dict[str, dict[str, Any]] = {}
    for s in scenarios:
        key = s.get("scenario_key", "")
        if key not in by_key or s["probability"] > by_key[key]["probability"]:
            by_key[key] = dict(s)
    unique_scenarios = list(by_key.values())

    # 按概率降序排列。
    sorted_scenarios = sorted(
        unique_scenarios, key=lambda x: x["probability"], reverse=True
    )
    probabilities = [s["probability"] for s in sorted_scenarios]
    threshold = _compute_probability_threshold(probabilities)

    # 先按门槛筛选。
    selected = [s for s in sorted_scenarios if s["probability"] >= threshold]

    # 补足到目标数量：允许低于动态门槛但不低于 5% 硬底的情景入选。
    absolute_floor = 0.05
    remaining = [
        s for s in sorted_scenarios
        if s not in selected and s["probability"] >= absolute_floor
    ]
    while len(selected) < target_scenarios and remaining:
        selected.append(remaining.pop(0))

    # 兜底：仍不足目标数量时，从标准情景集合补充 fallback。
    if len(selected) < target_scenarios:
        present_keys = {s["scenario_key"] for s in selected}
        fallback_prob = 0.20
        for key in STANDARD_SCENARIOS:
            if len(selected) >= target_scenarios:
                break
            if key not in present_keys:
                meta = STANDARD_SCENARIOS[key]
                levels = _compute_price_levels(
                    df, meta["direction"], None, None, None, None
                )
                close = float(df["close"].iloc[-1])
                fallback = {
                    "name": meta["display_name"],
                    "scenario_key": key,
                    "probability": fallback_prob,
                    "direction": meta["direction"],
                    "direction_label": _label_for_direction(meta["direction"]),
                    "support": levels["support"],
                    "resistance": levels["resistance"],
                    "target": levels["target"],
                    "stop_loss": levels["stop_loss"],
                    "position_size": _compute_position_size(
                        fallback_prob,
                        levels["target"] or close,
                        levels["stop_loss"] or close,
                        close,
                    ),
                    "wave_sketch": _build_wave_sketch(
                        df,
                        meta["direction"],
                        levels["support"] or close,
                        levels["resistance"] or close,
                        levels["target"] or close,
                    ),
                    "description": meta["description"],
                    "source": "fallback",
                }
                selected.append(fallback)
                present_keys.add(key)

    # 截断：超过 max_scenarios 时只保留前 max_scenarios。
    if len(selected) > max_scenarios:
        selected = selected[:max_scenarios]

    return _normalize_probabilities(selected)


def _count_unique_directions(scenarios: list[dict[str, Any]]) -> int:
    """统计不同方向的数量。"""
    return len({s["direction"] for s in scenarios})


def _ensure_diversity(
    scenarios: list[dict[str, Any]],
    df: pd.DataFrame,
    min_scenarios: int = 4,
    max_scenarios: int = 6,
    required_keys: tuple[str, ...] = ("bullish_continuation", "bearish_reversal", "dip_then_rise", "range_bound"),
) -> list[dict[str, Any]]:
    """确保最终情景集合至少包含 4 种、最多 6 种标准情景。"""
    present_keys = {s["scenario_key"] for s in scenarios}

    # 优先补齐必需的标准情景。
    for key in required_keys:
        if key not in present_keys:
            meta = STANDARD_SCENARIOS[key]
            levels = _compute_price_levels(
                df,
                meta["direction"],
                None,
                None,
                None,
                None,
            )
            close = float(df["close"].iloc[-1])
            position_size = _compute_position_size(
                0.01,
                levels["target"] or close,
                levels["stop_loss"] or close,
                close,
            )
            wave_sketch = _build_wave_sketch(
                df,
                meta["direction"],
                levels["support"] or close,
                levels["resistance"] or close,
                levels["target"] or close,
            )
            scenarios.append({
                "name": meta["display_name"],
                "scenario_key": key,
                "probability": 0.01,
                "direction": meta["direction"],
                "direction_label": _label_for_direction(meta["direction"]),
                "support": levels["support"],
                "resistance": levels["resistance"],
                "target": levels["target"],
                "stop_loss": levels["stop_loss"],
                "position_size": position_size,
                "wave_sketch": wave_sketch,
                "description": meta["description"],
                "source": "fallback",
            })
            present_keys.add(key)

    available = [k for k in STANDARD_SCENARIOS if k not in present_keys]

    while len(scenarios) < min_scenarios and available:
        key = available.pop(0)
        meta = STANDARD_SCENARIOS[key]
        scenarios.append({
            "name": meta["display_name"],
            "scenario_key": key,
            "probability": 0.01,
            "direction": meta["direction"],
            "direction_label": _label_for_direction(meta["direction"]),
            "support": None,
            "resistance": None,
            "target": None,
            "stop_loss": None,
            "position_size": 0.0,
            "wave_sketch": [],
            "description": meta["description"],
            "source": "fallback",
        })

    # 截断到最大数量。
    if len(scenarios) > max_scenarios:
        scenarios = scenarios[:max_scenarios]

    # 归一化概率。
    total = sum(s["probability"] for s in scenarios)
    if total > 0:
        for s in scenarios:
            s["probability"] = round(s["probability"] / total, 6)
    else:
        equal = round(1.0 / len(scenarios), 6) if scenarios else 0.0
        for s in scenarios:
            s["probability"] = equal

    scenarios.sort(key=lambda x: x["probability"], reverse=True)
    return scenarios


def _run_similarity_search(
    df: pd.DataFrame,
    n_neighbors: int,
    state_df: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    """执行相似性搜索，优先使用预计算状态向量。"""
    return find_similar_states(
        df,
        method="knn",
        n_neighbors=n_neighbors,
        state_df=state_df,
    )


def _run_template_matching(
    df: pd.DataFrame,
    min_confidence: float,
) -> list[dict[str, Any]]:
    """执行模板匹配。"""
    return match_templates(df, min_confidence=min_confidence)


def _generate_single_period(
    period: str,
    df: pd.DataFrame,
    *,
    n_neighbors: int,
    min_confidence: float,
    similarity_weight: float,
    template_weight: float,
    temperature: float,
    precompute_state: bool,
    provided_similarity: list[dict[str, Any]] | None,
    provided_templates: list[dict[str, Any]] | None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """为一个周期生成候选情景。

    周期内部的相似性搜索与模板匹配按顺序执行，避免细粒度线程切换
    开销；多周期之间由 ``generate_scenarios`` 统一并行调度。

    Returns:
        (period, per_period_metadata, calibrated_candidates)
    """
    state_df: pd.DataFrame | None = None
    if precompute_state and provided_similarity is None:
        state_columns = get_state_columns()
        state_df = compute_state_vector(df, state_columns=state_columns)

    similarity_results = (
        provided_similarity
        if provided_similarity is not None
        else _run_similarity_search(df, n_neighbors, state_df)
    )
    template_results = (
        provided_templates
        if provided_templates is not None
        else _run_template_matching(df, min_confidence)
    )

    fused = fuse_results(
        similarity_results,
        template_results,
        similarity_weight=similarity_weight,
        template_weight=template_weight,
    )
    calibrated = calibrate_probabilities(
        fused, similarity_results, temperature=temperature
    )

    per_period = {
        "similarity_count": len(similarity_results),
        "template_count": len(template_results),
        "candidates": calibrated,
    }
    return period, per_period, calibrated


def generate_scenarios(
    df_by_period: dict[str, pd.DataFrame],
    *,
    sub_index: str | None = None,
    n_neighbors: int = 10,
    min_confidence: float = 0.5,
    similarity_weight: float = 0.45,
    template_weight: float = 0.55,
    temperature: float = 0.8,
    use_adaptive_temperature: bool = True,
    period_weights: dict[str, float] | None = None,
    max_scenarios: int = 4,
    min_scenarios: int = 2,
    similarity_results_by_period: dict[str, list[dict[str, Any]]] | None = None,
    template_results_by_period: dict[str, list[dict[str, Any]]] | None = None,
    enable_parallel: bool = True,
    precompute_state: bool = True,
) -> dict[str, Any]:
    """为给定子指数生成标准情景集合。

    Args:
        df_by_period: 键为周期名称，值为对应 OHLC DataFrame 的字典。
        n_neighbors: 相似性搜索近邻数。
        min_confidence: 模板匹配最小置信度。
        similarity_weight: 相似性轨道融合权重。
        template_weight: 模板轨道融合权重。
        temperature: 多周期融合 softmax 温度。
        period_weights: 多周期权重，默认日线 0.5、4h 0.3、1h 0.2。
        max_scenarios: 最多输出情景数（默认 4）。
        min_scenarios: 最少输出情景数（默认 2）。
        similarity_results_by_period: 可选的预计算相似性搜索结果，用于降低延迟。
        template_results_by_period: 可选的预计算模板匹配结果，用于降低延迟。
        enable_parallel: 是否在线程池中并行处理多个周期的情景生成。
        precompute_state: 是否预先计算一次状态向量并复用，避免重复计算。

    Returns:
        包含 ``scenarios``、``raw_candidates``、``per_period`` 等字段的字典。
    """
    similarity_results_by_period = similarity_results_by_period or {}
    template_results_by_period = template_results_by_period or {}
    per_period: dict[str, dict[str, Any]] = {}
    fused_by_period: dict[str, list[dict[str, Any]]] = {}

    effective_temperature = temperature
    if use_adaptive_temperature and sub_index:
        effective_temperature = load_temperature(sub_index)

    if enable_parallel and len(df_by_period) > 1:
        # 多进程并行：模板匹配是纯 Python 循环，受 GIL 限制，进程级并行
        # 能真正利用多核缩短多周期冷生成时间。
        max_workers = min(4, len(df_by_period))
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for period, df in df_by_period.items():
                future = executor.submit(
                    _generate_single_period,
                    period,
                    df,
                    n_neighbors=n_neighbors,
                    min_confidence=min_confidence,
                    similarity_weight=similarity_weight,
                    template_weight=template_weight,
                    temperature=effective_temperature,
                    precompute_state=precompute_state,
                    provided_similarity=similarity_results_by_period.get(period),
                    provided_templates=template_results_by_period.get(period),
                )
                futures[future] = period
            for future in futures:
                period, period_meta, calibrated = future.result()
                per_period[period] = period_meta
                fused_by_period[period] = calibrated
    else:
        for period, df in df_by_period.items():
            _, period_meta, calibrated = _generate_single_period(
                period,
                df,
                n_neighbors=n_neighbors,
                min_confidence=min_confidence,
                similarity_weight=similarity_weight,
                template_weight=template_weight,
                temperature=effective_temperature,
                precompute_state=precompute_state,
                provided_similarity=similarity_results_by_period.get(period),
                provided_templates=template_results_by_period.get(period),
            )
            per_period[period] = period_meta
            fused_by_period[period] = calibrated

    multi_tf = fuse_timeframes(fused_by_period, period_weights=period_weights, temperature=temperature)

    # 明确以日线作为价格尺度基准；若不存在则取输入的第一个周期。
    base_period = "1day" if "1day" in df_by_period else next(iter(df_by_period))
    base_df = df_by_period[base_period]
    scenarios = [_map_to_standard_scenario(c, base_df) for c in multi_tf]
    scenarios = _select_high_probability_scenarios(
        scenarios, base_df, min_scenarios=min_scenarios, max_scenarios=max_scenarios
    )

    return {
        "scenarios": scenarios,
        "per_period": per_period,
        "multi_timeframe_candidates": multi_tf,
        "base_period": base_period,
    }
