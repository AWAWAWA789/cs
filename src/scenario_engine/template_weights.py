"""根据市场状态动态调整预定义模板的权重。

市场状态可来自 ``src.features.market_regime`` 或 Phase 10 的聚类标签。
权重调整完全基于模板自身的 ``category`` 与 ``direction`` 字段，
不依赖具体板块或成交量。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.scenario_engine.template_matcher import load_templates


DEFAULT_REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "uptrend": {
        "trend_continuation_bullish": 1.4,
        "trend_continuation_bearish": 0.7,
        "consolidation_bullish": 1.0,
        "consolidation_bearish": 0.9,
        "reversal_bullish": 1.1,
        "reversal_bearish": 0.8,
    },
    "downtrend": {
        "trend_continuation_bullish": 0.7,
        "trend_continuation_bearish": 1.4,
        "consolidation_bullish": 0.9,
        "consolidation_bearish": 1.0,
        "reversal_bullish": 0.8,
        "reversal_bearish": 1.1,
    },
    "choppy": {
        "trend_continuation_bullish": 0.7,
        "trend_continuation_bearish": 0.7,
        "consolidation_bullish": 1.3,
        "consolidation_bearish": 1.3,
        "reversal_bullish": 1.2,
        "reversal_bearish": 1.2,
    },
}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {name: 0.0 for name in weights}
    return {name: round(value / total, 6) for name, value in weights.items()}


def compute_template_weights(
    market_state: str,
    templates: str | Path | list[dict] | None = None,
    config: dict[str, dict[str, float]] | None = None,
    normalize: bool = True,
) -> dict[str, float]:
    """根据市场状态计算各模板权重。

    Args:
        market_state: 市场状态标签，支持 ``uptrend``、``downtrend``、
            ``choppy`` 或其他自定义标签（需在 ``config`` 中提供对应规则）。
        templates: 模板目录、文件或已解析模板列表；默认读取
            ``config/scenario_templates``。
        config: 自定义权重调整表。外层键为市场状态，内层键为
            ``{category}_{direction}``，值为权重乘数。
        normalize: 是否将权重归一化到和为 1。

    Returns:
        模板名称到权重的映射。
    """
    template_list = load_templates(templates)
    config = config or DEFAULT_REGIME_WEIGHTS

    regime_table = config.get(market_state)
    if regime_table is None:
        raise ValueError(
            f"Unknown market_state: {market_state!r}. "
            f"Known states: {list(config.keys())}"
        )

    weights: dict[str, float] = {}
    for template in template_list:
        name = template["name"]
        category = template.get("category", "trend_continuation")
        direction = template.get("direction", "both")
        # 方向为 both 时，按类别基础调整处理。
        key = f"{category}_{direction}"
        multiplier = regime_table.get(key, 1.0)
        weights[name] = 1.0 * multiplier

    if normalize:
        weights = _normalize_weights(weights)
    return weights
