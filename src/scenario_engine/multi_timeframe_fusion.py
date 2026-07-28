"""多时间框架情景融合。

接受日线、4 小时、1 小时三个周期的情景候选集合，按周期可靠性加权（日线最高）
融合为统一的情景集合。所有输入均为算法生成的概率、方向与情景类型，不使用成交量。

关键价位（support/resistance/target/stop_loss）不参与跨周期平均，统一由上游
基于日线（或请求周期）的价格尺度重新计算，从而避免不同周期或历史模板价位
混入导致当前价与支撑/阻力倒挂的异常。
"""

from __future__ import annotations

from typing import Any

import numpy as np


DEFAULT_PERIOD_WEIGHTS = {
    "1day": 0.5,
    "4hour": 0.3,
    "1hour": 0.2,
}

PERIOD_ALIASES = {
    "1d": "1day",
    "d": "1day",
    "day": "1day",
    "daily": "1day",
    "4h": "4hour",
    "h4": "4hour",
    "1h": "1hour",
    "h1": "1hour",
    "hour": "1hour",
}

# 当同一签名由多个周期贡献时，source 的优先级。
_SOURCE_PRIORITY = {
    "fusion": 3,
    "fused": 3,
    "template": 2,
    "similarity": 1,
    "fallback": 0,
}


def _normalize_period(period: str) -> str:
    """将周期别名统一为内部命名。"""
    return PERIOD_ALIASES.get(str(period).lower(), str(period).lower())


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


def _scenario_signature(candidate: dict[str, Any]) -> str:
    """生成用于聚合的统一签名：方向 + 可选模板名。"""
    direction = _label_for_direction(_direction_to_int(candidate.get("direction", 0)))
    tmpl = candidate.get("template_name") or candidate.get("name", "")
    if tmpl:
        return f"{tmpl}_{direction}"
    return direction


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    """计算加权均值。"""
    total = sum(weights)
    if total <= 0:
        return float(np.mean(values)) if values else 0.0
    return sum(v * w for v, w in zip(values, weights)) / total


def _pick_source(sources: list[str]) -> str:
    """从多个 source 中按优先级挑选一个，并将内部 'fused' 归一化为 'fusion'。"""
    if not sources:
        return "fallback"
    normalized = ["fusion" if str(s).lower() == "fused" else str(s).lower() for s in sources]
    ranked = sorted(normalized, key=lambda s: _SOURCE_PRIORITY.get(s, -1), reverse=True)
    return ranked[0]


def fuse_timeframes(
    timeframe_scenarios: dict[str, list[dict[str, Any]]],
    period_weights: dict[str, float] | None = None,
    temperature: float = 0.8,
) -> list[dict[str, Any]]:
    """融合多周期情景集合。

    Args:
        timeframe_scenarios: 键为周期名称，值为该周期情景候选列表的字典。
            支持 ``1day``、``4hour``、``1hour`` 及其别名。
        period_weights: 各周期权重。默认日线 0.5、4h 0.3、1h 0.2。
        temperature: 最终概率 softmax 温度。

    Returns:
        统一情景候选列表，按概率降序排列。每个元素包含 ``name``、
        ``probability``、``direction``、``period_weights``、``contributing_periods``
        与 ``source``。关键价位字段统一置为 ``None``，由 ``scenario_generator``
        根据日线（或请求周期）价格尺度重新计算。
    """
    weights = {**DEFAULT_PERIOD_WEIGHTS, **(period_weights or {})}

    # 归一化权重。
    provided_periods = {_normalize_period(p) for p in timeframe_scenarios.keys()}
    active_weights = {
        p: w for p, w in weights.items() if p in provided_periods
    }
    total = sum(active_weights.values())
    if total <= 0:
        active_weights = {p: 1.0 for p in provided_periods}
        total = sum(active_weights.values())
    active_weights = {p: w / total for p, w in active_weights.items()}

    grouped: dict[str, dict[str, Any]] = {}
    for raw_period, scenarios in timeframe_scenarios.items():
        period = _normalize_period(raw_period)
        w = active_weights.get(period, 0.0)
        for cand in scenarios:
            sig = _scenario_signature(cand)
            if sig not in grouped:
                grouped[sig] = {
                    "probabilities": [],
                    "confidences": [],
                    "weights": [],
                    "directions": [],
                    "periods": set(),
                    "sources": [],
                    "candidates_by_period": {},
                    "template_name": cand.get("template_name") or cand.get("name", ""),
                    "suggestion": cand.get("suggestion", "neutral"),
                }
            g = grouped[sig]
            g["probabilities"].append(float(cand.get("probability", 0.0)))
            g["confidences"].append(float(cand.get("confidence", 0.0)))
            g["weights"].append(w)
            g["directions"].append(_direction_to_int(cand.get("direction", 0)))
            g["periods"].add(period)
            g["sources"].append(cand.get("source", "unknown"))
            g["candidates_by_period"][period] = cand

    fused: list[dict[str, Any]] = []
    for sig, g in grouped.items():
        direction = int(np.sign(sum(g["directions"]))) if g["directions"] else 0
        probability = _weighted_mean(g["probabilities"], g["weights"])
        confidence = _weighted_mean(g["confidences"], g["weights"])

        # 主周期：权重最高的贡献周期，用于确定 source。
        primary_period = max(
            g["periods"],
            key=lambda p: active_weights.get(p, 0.0),
        )
        source = _pick_source(g["sources"])

        record: dict[str, Any] = {
            "name": sig,
            "direction": direction,
            "probability": round(probability, 6),
            "confidence": round(confidence, 6),
            # 关键价位不在多周期之间融合，统一由上游按日线价格尺度重新计算。
            "support": None,
            "resistance": None,
            "target": None,
            "stop_loss": None,
            "suggestion": g["suggestion"],
            "template_name": g["template_name"],
            "contributing_periods": sorted(g["periods"]),
            "period_weights": active_weights,
            "primary_period": primary_period,
            "source": source,
        }
        fused.append(record)

    if not fused:
        return []

    scores = np.array([c["probability"] for c in fused], dtype=float)
    if temperature <= 0:
        temperature = 1e-6
    scaled = scores / temperature
    max_val = np.max(scaled)
    exps = np.exp(scaled - max_val)
    probs = exps / (np.sum(exps) + 1e-12)

    for cand, prob in zip(fused, probs):
        cand["probability"] = round(float(prob), 6)

    fused.sort(key=lambda x: x["probability"], reverse=True)
    return fused
