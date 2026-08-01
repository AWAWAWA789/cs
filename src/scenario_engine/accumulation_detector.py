"""库存吸货识别引擎。

双轨融合识别主力资金隐蔽建仓行为：

1. 规则引擎：基于吸货特征向量的专家规则评分
   - FULL 模式（真实 OHLC）：量价背离/价格位置/横盘/底部抬高/波动率收缩/量能趋势 6 项
   - CLOSE_ONLY 模式（仅收盘价）：价格位置/收盘波动率/收盘横盘/收盘趋势 4 项
2. 数据源透明化：所有评分必含 feature_mode / data_source / confidence
3. 训练权重接入：启动时加载 trained 产物，可热切换

双轨结果通过加权融合得到最终吸货评分（0-1）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.features.accumulation import compute_accumulation_features, get_latest_features
from src.api.logging import get_logger

LOGGER = get_logger("csqaq.accumulation_detector")


# ── 规则引擎权重（经验值，可被训练产物覆盖）──────────────────
# FULL 模式：6 项规则，权重和 = 1.0
RULE_WEIGHTS_FULL = {
    "price_position": 0.20,
    "volume_price_divergence": 0.25,
    "consolidation": 0.15,
    "bottom_rising": 0.15,
    "volatility_contracting": 0.10,
    "volume_trend": 0.15,
}
# CLOSE_ONLY 模式：4 项规则，权重和 = 1.0（无成交量和 swing）
RULE_WEIGHTS_CLOSE_ONLY = {
    "price_position": 0.30,
    "close_volatility_contracting": 0.25,
    "close_consolidation": 0.25,
    "close_trend_rising": 0.20,
}

# 兼容旧引用
RULE_WEIGHTS = RULE_WEIGHTS_FULL

# ── 训练权重缓存（懒加载，mtime 检测刷新）────────────────────
_TRAINED_WEIGHTS_CACHE: dict[str, Any] = {
    "path": None,
    "mtime": 0.0,
    "data": None,
}


def _resolve_weights(
    cache_root: str | Path | None = None,
    category: str = "rifle",
    mode: str = "FULL",
) -> tuple[dict[str, float], str]:
    """解析当前应使用的规则权重。

    优先级：
    1. cache_root 提供且存在训练产物 → 用 trained 权重（按 mode 匹配）
    2. 否则 → empirical 经验权重

    Returns:
        (weights_dict, source) source ∈ {"trained", "empirical"}
    """
    if cache_root is None:
        return (RULE_WEIGHTS_FULL if mode == "FULL" else RULE_WEIGHTS_CLOSE_ONLY,
                "empirical")

    # 懒加载 + mtime 刷新
    weights_path = Path(cache_root) / "trained" / f"{category}_rule_weights.json"
    if not weights_path.exists():
        return (RULE_WEIGHTS_FULL if mode == "FULL" else RULE_WEIGHTS_CLOSE_ONLY,
                "empirical")

    try:
        mtime = weights_path.stat().st_mtime
        if (_TRAINED_WEIGHTS_CACHE["path"] != str(weights_path)
                or _TRAINED_WEIGHTS_CACHE["mtime"] != mtime):
            import json
            data = json.loads(weights_path.read_text())
            if not data.get("trained", False):
                return (RULE_WEIGHTS_FULL if mode == "FULL" else RULE_WEIGHTS_CLOSE_ONLY,
                        "empirical")
            _TRAINED_WEIGHTS_CACHE.update(
                path=str(weights_path), mtime=mtime, data=data,
            )
    except Exception as exc:
        LOGGER.warning("load trained weights failed: %s", exc)
        return (RULE_WEIGHTS_FULL if mode == "FULL" else RULE_WEIGHTS_CLOSE_ONLY,
                "empirical")

    data = _TRAINED_WEIGHTS_CACHE["data"]
    trained_mode = data.get("feature_mode", "FULL")
    if trained_mode != mode:
        LOGGER.debug(
            "trained mode=%s != requested mode=%s, fall back to empirical",
            trained_mode, mode,
        )
        return (RULE_WEIGHTS_FULL if mode == "FULL" else RULE_WEIGHTS_CLOSE_ONLY,
                "empirical")

    # 从训练产物提取归一化权重作为规则权重
    weights_raw = data.get("weights", {})
    resolved: dict[str, float] = {}
    if mode == "FULL":
        # 训练时特征 keys 与 RULE_WEIGHTS_FULL 的规则名映射
        feature_to_rule = {
            "price_position": "price_position",
            "volume_price_divergence": "volume_price_divergence",
            "consolidation_score": "consolidation",
            "bottom_rising": "bottom_rising",
            "atr_percent": "volatility_contracting",
            "volume_trend": "volume_trend",
        }
        for feat, rule in feature_to_rule.items():
            info = weights_raw.get(feat, {})
            resolved[rule] = float(info.get("normalized", RULE_WEIGHTS_FULL[rule]))
    else:
        # CLOSE_ONLY 模式训练权重映射（待 D 阶段实现，先回退 empirical）
        return RULE_WEIGHTS_CLOSE_ONLY, "empirical"

    return resolved, "trained"


# ── FULL 模式评分函数 ──────────────────────────────────────
def _score_price_position(features: dict[str, float]) -> float:
    """价格位置评分：越接近窗口最低点得分越高。"""
    pos = features.get("price_position", 0.5)
    return max(0.0, 1.0 - pos)


def _score_volume_price_divergence(features: dict[str, float]) -> float:
    """量价背离评分：背离值越大得分越高。"""
    div = features.get("volume_price_divergence", 0.0)
    return min(1.0, max(0.0, div / 3.0))


def _score_consolidation(features: dict[str, float]) -> float:
    """横盘整理评分。"""
    score = features.get("consolidation_score", 0.0)
    bars = features.get("consolidation_bars", 0.0)
    bars_bonus = min(0.3, bars / 50.0)
    return min(1.0, score * 0.7 + bars_bonus)


def _score_bottom_rising(features: dict[str, float]) -> float:
    """底部抬高评分。"""
    return min(1.0, features.get("bottom_rising", 0.0))


def _score_volatility_contracting(features: dict[str, float]) -> float:
    """波动率收缩评分：低波动率体制得分高。"""
    regime = features.get("volatility_regime", 1.0)
    atr_pct = features.get("atr_percent", 2.0)
    regime_score = max(0.0, 1.0 - regime / 2.0)
    atr_score = max(0.0, 1.0 - atr_pct / 5.0)
    return (regime_score + atr_score) / 2.0


def _score_volume_trend(features: dict[str, float]) -> float:
    """成交量趋势评分：成交量温和递增得分高。"""
    trend = features.get("volume_trend", 1.0)
    if trend <= 1.0:
        return 0.3
    elif trend <= 2.0:
        return min(1.0, (trend - 1.0) * 2.0)
    else:
        return max(0.0, 1.0 - (trend - 2.0) * 0.5)


# ── CLOSE_ONLY 模式评分函数（基于收盘价）────────────────────
def _score_close_volatility_contracting(features: dict[str, float]) -> float:
    """收盘价波动率收缩评分：波动率越低得分越高（蓄势特征）。

    close_volatility 已归一化到 [0,1]，越低越像蓄势。
    """
    vol = features.get("close_volatility", 0.5)
    return max(0.0, 1.0 - vol)


def _score_close_consolidation(features: dict[str, float]) -> float:
    """收盘价横盘评分：直接使用 close_consolidation。"""
    return min(1.0, features.get("close_consolidation", 0.0))


def _score_close_trend_rising(features: dict[str, float]) -> float:
    """收盘价底部抬高评分：趋势斜率为正得分高。

    close_trend 已归一化到 [-1,1]，正值表示上升。
    """
    trend = features.get("close_trend", 0.0)
    if trend <= 0:
        return max(0.0, 0.5 + trend * 0.5)  # 下跌轻微扣分
    return min(1.0, 0.5 + trend * 0.5)


def rule_engine_score(
    features: dict[str, float],
    cache_root: str | Path | None = None,
    category: str = "rifle",
) -> dict[str, float]:
    """规则引擎评分（双模式自适应）。

    Args:
        features: 特征字典（来自 get_latest_features，含 feature_mode）
        cache_root: 缓存根目录（用于加载训练权重）
        category: 品类

    Returns:
        包含各规则得分、总分、特征模式、权重来源的字典。
    """
    mode = features.get("feature_mode", "FULL")
    weights, source = _resolve_weights(cache_root, category, mode)

    if mode == "CLOSE_ONLY":
        scores = {
            "price_position": _score_price_position(features),
            "close_volatility_contracting": _score_close_volatility_contracting(features),
            "close_consolidation": _score_close_consolidation(features),
            "close_trend_rising": _score_close_trend_rising(features),
        }
    elif mode == "FULL":
        scores = {
            "price_position": _score_price_position(features),
            "volume_price_divergence": _score_volume_price_divergence(features),
            "consolidation": _score_consolidation(features),
            "bottom_rising": _score_bottom_rising(features),
            "volatility_contracting": _score_volatility_contracting(features),
            "volume_trend": _score_volume_trend(features),
        }
    else:  # DEGRADED
        scores = {"total": 0.0}

    if mode != "DEGRADED":
        total = sum(scores.get(k, 0.0) * w for k, w in weights.items())
        # 权重和可能不为 1（trained 模式），归一化
        weight_sum = sum(weights.values()) or 1.0
        total = total / weight_sum
        scores["total"] = float(np.clip(total, 0.0, 1.0))

    scores["feature_mode"] = mode
    scores["weights_source"] = source
    return scores


def _compute_confidence(
    feature_mode: str,
    case_count: int | None = None,
) -> float:
    """计算评分置信度（0-1）。

    三因子加权：
    - 数据源真实性：FULL=1.0, CLOSE_ONLY=0.6, DEGRADED=0.2
    - 有效特征比例：FULL 6/6=1.0, CLOSE_ONLY 4/4=1.0（在自己的口径内完整）
    - 样本量（可选）：无案例库=0.5，<100=0.5，<500=0.7，≥500=0.9
    """
    source_score = {"FULL": 1.0, "CLOSE_ONLY": 0.6, "DEGRADED": 0.2}.get(feature_mode, 0.3)
    if case_count is None:
        sample_score = 0.5
    elif case_count < 100:
        sample_score = 0.5
    elif case_count < 500:
        sample_score = 0.7
    else:
        sample_score = 0.9
    return round(0.5 * source_score + 0.5 * sample_score, 4)


def _detect_accumulation_phase(
    df: pd.DataFrame,
    window: int = 30,
    cache_root: str | Path | None = None,
    category: str = "rifle",
) -> dict[str, Any]:
    """检测当前是否处于吸货阶段。

    通过滑动窗口分析最近 N 根 K 线的整体吸货特征。

    Args:
        df: 含吸货特征的 DataFrame。
        window: 分析窗口。
        cache_root: 缓存根目录（用于加载训练权重）
        category: 品类

    Returns:
        包含 phase（accumulation/distribution/neutral）、
        duration（持续 K 线数）、strength（强度 0-1）的字典。
    """
    if len(df) < 5:
        return {"phase": "neutral", "duration": 0, "strength": 0.0}

    recent = df.tail(window)
    features_df = compute_accumulation_features(recent)
    features = get_latest_features(features_df)
    rule_scores = rule_engine_score(features, cache_root, category)
    total_score = rule_scores.get("total", 0.0)

    # 吸货阶段判定
    if total_score >= 0.6:
        phase = "accumulation"
    elif total_score <= 0.3:
        phase = "distribution"
    else:
        phase = "neutral"

    # 持续 K 线数：统计连续高分 K 线
    # 兼容 FULL（consolidation_score）和 CLOSE_ONLY（close_consolidation）
    cons_col = "close_consolidation" if "close_consolidation" in df.columns else "consolidation_score"
    if cons_col in df.columns:
        high_score_bars = (df[cons_col] > 0.5).astype(int)
        duration = 0
        for val in reversed(high_score_bars.values):
            if val == 1:
                duration += 1
            else:
                break
    else:
        duration = 0

    return {
        "phase": phase,
        "duration": int(duration),
        "strength": float(total_score),
        "rule_scores": rule_scores,
        "features": features,
    }


def detect_accumulation(
    df: pd.DataFrame,
    sub_index: str = "",
    period: str = "",
    cache_root: str | Path | None = None,
    category: str = "rifle",
    case_count: int | None = None,
) -> dict[str, Any]:
    """吸货检测主入口。

    双轨融合：规则引擎 + （可选）历史模式匹配。

    Args:
        df: OHLCV DataFrame（含 open/high/low/close，可选 volume）。
            CLOSE_ONLY 模式仅需 close 列。
        sub_index: 子指数名称（用于日志和结果标记）。
        period: K 线周期。
        cache_root: 缓存根目录（传入则启用训练权重热加载）。
        category: 品类。
        case_count: 案例库规模（用于置信度计算）。

    Returns:
        吸货分析结果，包含：
        - accumulation_score: 综合吸货评分（0-1）
        - phase: 当前阶段（accumulation/distribution/neutral）
        - signals: 各信号得分明细
        - features: 最新特征值
        - feature_mode: 数据源模式（FULL/CLOSE_ONLY/DEGRADED）
        - weights_source: 权重来源（trained/empirical）
        - confidence: 评分置信度（0-1）
        - description: 人类可读的吸货分析描述
    """
    if len(df) < 10:
        return {
            "sub_index": sub_index,
            "period": period,
            "accumulation_score": 0.0,
            "phase": "neutral",
            "signals": {},
            "features": {"feature_mode": "DEGRADED"},
            "feature_mode": "DEGRADED",
            "weights_source": "empirical",
            "confidence": _compute_confidence("DEGRADED", case_count),
            "description": "数据不足，无法进行吸货分析",
        }

    # 计算吸货特征（自动检测模式）
    feat_df = compute_accumulation_features(df)
    features = get_latest_features(feat_df)
    feature_mode = features.get("feature_mode", "FULL")

    # 规则引擎评分
    rule_scores = rule_engine_score(features, cache_root, category)
    rule_total = rule_scores.get("total", 0.0)
    weights_source = rule_scores.get("weights_source", "empirical")

    # 阶段检测
    phase_info = _detect_accumulation_phase(feat_df, cache_root=cache_root, category=category)
    phase = phase_info["phase"]

    # 描述生成
    description = _generate_description(rule_scores, features, phase)

    # 置信度
    confidence = _compute_confidence(feature_mode, case_count)

    return {
        "sub_index": sub_index,
        "period": period,
        "accumulation_score": round(float(rule_total), 4),
        "phase": phase,
        "signals": {k: round(float(v), 4) for k, v in rule_scores.items()
                    if k not in ("total", "feature_mode", "weights_source")},
        "total_rule_score": round(float(rule_total), 4),
        "features": {k: (round(float(v), 4) if isinstance(v, (int, float)) else v)
                     for k, v in features.items()},
        "feature_mode": feature_mode,
        "weights_source": weights_source,
        "confidence": confidence,
        "duration_bars": phase_info["duration"],
        "description": description,
    }


# ── 双轨融合 ──────────────────────────────────────────────
# K线行为轨 + 库存行为轨的融合阈值与权重
KLINE_HIGH = 0.55
KLINE_LOW = 0.35
INV_HIGH = 0.55
INV_LOW = 0.35


def _classify_fusion_pattern(kline_score: float, inventory_score: float) -> str:
    """判定双轨融合模式。

    返回四种模式之一：
    - strong: 双高（K线吸货 + 库存加仓）→ 明牌吸货
    - weak:   K高库低（可能下跌中继）
    - hidden: K低库高（隐蔽吸货，最稀缺信号）
    - none:   双低（无信号）
    """
    k_high = kline_score >= KLINE_HIGH
    k_low = kline_score <= KLINE_LOW
    i_high = inventory_score >= INV_HIGH
    i_low = inventory_score <= INV_LOW

    if k_high and i_high:
        return "strong"
    if k_high and i_low:
        return "weak"
    if k_low and i_high:
        return "hidden"
    return "none"


def fuse_scores(
    kline_score: float,
    inventory_score: float,
) -> dict[str, Any]:
    """双轨融合评分。

    融合规则（核心）：
    - strong (双高): kline×0.6 + inv×0.4 + 0.10（同向加分）
    - weak   (K高库低): kline×0.6 + inv×0.4 - 0.05（减分，可能误判）
    - hidden (K低库高): kline×0.4 + inv×0.6 + 0.15（隐蔽吸货加成，最稀缺）
    - none   (双低): kline×0.5 + inv×0.5

    Args:
        kline_score: K线行为评分 (0-1)
        inventory_score: 库存行为评分 (0-1)

    Returns:
        融合结果字典：fused_score, pattern, kline_score, inventory_score
    """
    pattern = _classify_fusion_pattern(kline_score, inventory_score)

    if pattern == "strong":
        fused = kline_score * 0.6 + inventory_score * 0.4 + 0.10
    elif pattern == "weak":
        fused = kline_score * 0.6 + inventory_score * 0.4 - 0.05
    elif pattern == "hidden":
        fused = kline_score * 0.4 + inventory_score * 0.6 + 0.15
    else:  # none
        fused = kline_score * 0.5 + inventory_score * 0.5

    fused = float(max(0.0, min(1.0, fused)))

    # 阶段判定
    if fused >= 0.6:
        phase = "accumulation"
    elif fused <= 0.3:
        phase = "distribution"
    else:
        phase = "neutral"

    return {
        "fused_score": round(fused, 4),
        "pattern": pattern,
        "phase": phase,
        "kline_score": round(float(kline_score), 4),
        "inventory_score": round(float(inventory_score), 4),
    }


def _generate_description(
    scores: dict[str, float],
    features: dict[str, float],
    phase: str,
) -> str:
    """生成人类可读的吸货分析描述（双模式自适应）。"""
    parts = []
    mode = features.get("feature_mode", "FULL")

    if phase == "accumulation":
        parts.append("当前处于吸货阶段")
    elif phase == "distribution":
        parts.append("当前处于出货阶段")
    else:
        parts.append("当前无明显吸货/出货信号")

    if mode == "CLOSE_ONLY":
        # CLOSE_ONLY 模式描述（仅收盘价特征）
        if scores.get("price_position", 0) > 0.6:
            parts.append("价格处于近期低位区间")
        if scores.get("close_volatility_contracting", 0) > 0.6:
            parts.append("收盘价波动率持续收缩")
        if scores.get("close_consolidation", 0) > 0.6:
            parts.append("价格窄幅横盘整理")
        elif scores.get("close_consolidation", 0) > 0.3:
            parts.append("价格在较小区间内震荡")
        if scores.get("close_trend_rising", 0) > 0.6:
            parts.append("收盘价底部逐步抬高")
        if not parts[1:]:
            parts.append("各项指标均不明显（仅收盘价数据）")
    else:
        # FULL 模式描述（完整 OHLC）
        if scores.get("volume_price_divergence", 0) > 0.6:
            parts.append("量价背离明显（放量但价格波动缩小）")
        elif scores.get("volume_price_divergence", 0) > 0.3:
            parts.append("存在轻度量价背离")
        if scores.get("price_position", 0) > 0.6:
            parts.append("价格处于近期低位区间")
        if scores.get("consolidation", 0) > 0.6:
            parts.append("价格窄幅横盘整理")
        elif scores.get("consolidation", 0) > 0.3:
            parts.append("价格在较小区间内震荡")
        if scores.get("bottom_rising", 0) > 0.5:
            parts.append("底部逐步抬高（higher lows）")
        if scores.get("volume_trend", 0) > 0.6:
            parts.append("成交量温和递增")
        if scores.get("volatility_contracting", 0) > 0.6:
            parts.append("波动率持续收缩")
        if not parts[1:]:
            parts.append("各项指标均不明显")

    return "，".join(parts) + "。"
