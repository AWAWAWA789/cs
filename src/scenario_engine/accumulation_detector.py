"""库存吸货识别引擎。

双轨融合识别主力资金隐蔽建仓行为：

1. 规则引擎：基于吸货特征向量的专家规则评分
   - 量价背离（放量+价格不动）
   - 底部位置（价格在低位区间）
   - 波动率收缩（低波动横盘）
   - 底部抬高（higher lows）
   - 横盘持续时间

2. 历史模式匹配：基于 DTW/KNN 相似性搜索
   - 在历史"已确认主力吸货"的案例库中匹配当前走势
   - 复用项目已有的相似性搜索能力

双轨结果通过加权融合得到最终吸货评分（0-1）。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.features.accumulation import compute_accumulation_features, get_latest_features
from src.api.logging import get_logger

LOGGER = get_logger("csqaq.accumulation_detector")


# ── 规则引擎权重 ────────────────────────────────────────────
# 每条规则的权重，总和 = 1.0。可根据回测结果调整。
RULE_WEIGHTS = {
    "price_position": 0.20,      # 价格处于低位
    "volume_price_divergence": 0.25,  # 量价背离（核心信号）
    "consolidation": 0.15,        # 横盘整理
    "bottom_rising": 0.15,        # 底部抬高
    "volatility_contracting": 0.10,  # 波动率收缩
    "volume_trend": 0.15,         # 成交量温和递增
}


def _score_price_position(features: dict[str, float]) -> float:
    """价格位置评分：越接近窗口最低点得分越高。"""
    pos = features.get("price_position", 0.5)
    # pos=0 (最低) → 1.0 分；pos=1 (最高) → 0.0 分
    return max(0.0, 1.0 - pos)


def _score_volume_price_divergence(features: dict[str, float]) -> float:
    """量价背离评分：背离值越大得分越高。"""
    div = features.get("volume_price_divergence", 0.0)
    # div 通常在 -5 到 5 之间，正值表示量价背离
    return min(1.0, max(0.0, div / 3.0))


def _score_consolidation(features: dict[str, float]) -> float:
    """横盘整理评分。"""
    score = features.get("consolidation_score", 0.0)
    bars = features.get("consolidation_bars", 0.0)
    # 横盘评分 + 持续时间加权
    bars_bonus = min(0.3, bars / 50.0)  # 最多加 0.3
    return min(1.0, score * 0.7 + bars_bonus)


def _score_bottom_rising(features: dict[str, float]) -> float:
    """底部抬高评分。"""
    return min(1.0, features.get("bottom_rising", 0.0))


def _score_volatility_contracting(features: dict[str, float]) -> float:
    """波动率收缩评分：低波动率体制得分高。"""
    regime = features.get("volatility_regime", 1.0)
    atr_pct = features.get("atr_percent", 2.0)
    # regime 0=低波动 → 1.0 分；1=中 → 0.5；2=高 → 0.0
    regime_score = max(0.0, 1.0 - regime / 2.0)
    # ATR 百分比越低得分越高
    atr_score = max(0.0, 1.0 - atr_pct / 5.0)
    return (regime_score + atr_score) / 2.0


def _score_volume_trend(features: dict[str, float]) -> float:
    """成交量趋势评分：成交量温和递增得分高。"""
    trend = features.get("volume_trend", 1.0)
    # trend=1.0 表示无明显变化；>1 表示递增
    # 温和递增（1.0-2.0）得分最高，急增（>2.0）可能是出货
    if trend <= 1.0:
        return 0.3
    elif trend <= 2.0:
        return min(1.0, (trend - 1.0) * 2.0)  # 1.0→0, 1.5→1.0
    else:
        return max(0.0, 1.0 - (trend - 2.0) * 0.5)  # 递减


def rule_engine_score(features: dict[str, float]) -> dict[str, float]:
    """规则引擎评分。

    Args:
        features: 特征字典（来自 get_latest_features）。

    Returns:
        包含各规则得分和总分的字典：
        - 每条规则的单独得分（0-1）
        - total: 加权总分（0-1）
    """
    scores = {
        "price_position": _score_price_position(features),
        "volume_price_divergence": _score_volume_price_divergence(features),
        "consolidation": _score_consolidation(features),
        "bottom_rising": _score_bottom_rising(features),
        "volatility_contracting": _score_volatility_contracting(features),
        "volume_trend": _score_volume_trend(features),
    }

    total = sum(scores.get(k, 0.0) * w for k, w in RULE_WEIGHTS.items())
    scores["total"] = float(np.clip(total, 0.0, 1.0))
    return scores


def _detect_accumulation_phase(
    df: pd.DataFrame,
    window: int = 30,
) -> dict[str, Any]:
    """检测当前是否处于吸货阶段。

    通过滑动窗口分析最近 N 根 K 线的整体吸货特征。

    Args:
        df: 含吸货特征的 DataFrame。
        window: 分析窗口。

    Returns:
        包含 phase（accumulation/distribution/neutral）、
        duration（持续 K 线数）、strength（强度 0-1）的字典。
    """
    if len(df) < 5:
        return {"phase": "neutral", "duration": 0, "strength": 0.0}

    recent = df.tail(window)
    features_df = compute_accumulation_features(recent)
    features = get_latest_features(features_df)
    rule_scores = rule_engine_score(features)
    total_score = rule_scores["total"]

    # 吸货阶段判定
    if total_score >= 0.6:
        phase = "accumulation"
    elif total_score <= 0.3:
        phase = "distribution"
    else:
        phase = "neutral"

    # 持续 K 线数：统计连续高分 K 线
    if "consolidation_score" in df.columns:
        high_score_bars = (df["consolidation_score"] > 0.5).astype(int)
        # 从最后一根往回数连续高分
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
) -> dict[str, Any]:
    """吸货检测主入口。

    双轨融合：规则引擎 + （可选）历史模式匹配。

    Args:
        df: OHLCV DataFrame（含 open/high/low/close，可选 volume）。
        sub_index: 子指数名称（用于日志和结果标记）。
        period: K 线周期。

    Returns:
        吸货分析结果，包含：
        - accumulation_score: 综合吸货评分（0-1）
        - phase: 当前阶段（accumulation/distribution/neutral）
        - signals: 各信号得分明细
        - features: 最新特征值
        - description: 人类可读的吸货分析描述
    """
    if len(df) < 10:
        return {
            "sub_index": sub_index,
            "period": period,
            "accumulation_score": 0.0,
            "phase": "neutral",
            "signals": {},
            "features": {},
            "description": "数据不足，无法进行吸货分析",
        }

    # 计算吸货特征
    feat_df = compute_accumulation_features(df)
    features = get_latest_features(feat_df)

    # 规则引擎评分
    rule_scores = rule_engine_score(features)
    rule_total = rule_scores["total"]

    # 阶段检测
    phase_info = _detect_accumulation_phase(feat_df)
    phase = phase_info["phase"]

    # 描述生成
    description = _generate_description(rule_scores, features, phase)

    return {
        "sub_index": sub_index,
        "period": period,
        "accumulation_score": round(float(rule_total), 4),
        "phase": phase,
        "signals": {k: round(float(v), 4) for k, v in rule_scores.items() if k != "total"},
        "total_rule_score": round(float(rule_total), 4),
        "features": {k: round(float(v), 4) for k, v in features.items()},
        "duration_bars": phase_info["duration"],
        "description": description,
    }


def _generate_description(
    scores: dict[str, float],
    features: dict[str, float],
    phase: str,
) -> str:
    """生成人类可读的吸货分析描述。"""
    parts = []

    if phase == "accumulation":
        parts.append("当前处于吸货阶段")
    elif phase == "distribution":
        parts.append("当前处于出货阶段")
    else:
        parts.append("当前无明显吸货/出货信号")

    # 量价背离
    if scores.get("volume_price_divergence", 0) > 0.6:
        parts.append("量价背离明显（放量但价格波动缩小）")
    elif scores.get("volume_price_divergence", 0) > 0.3:
        parts.append("存在轻度量价背离")

    # 价格位置
    if scores.get("price_position", 0) > 0.6:
        parts.append("价格处于近期低位区间")

    # 横盘
    if scores.get("consolidation", 0) > 0.6:
        parts.append("价格窄幅横盘整理")
    elif scores.get("consolidation", 0) > 0.3:
        parts.append("价格在较小区间内震荡")

    # 底部抬高
    if scores.get("bottom_rising", 0) > 0.5:
        parts.append("底部逐步抬高（higher lows）")

    # 成交量趋势
    if scores.get("volume_trend", 0) > 0.6:
        parts.append("成交量温和递增")

    # 波动率
    if scores.get("volatility_contracting", 0) > 0.6:
        parts.append("波动率持续收缩")

    if not parts[1:]:
        parts.append("各项指标均不明显")

    return "，".join(parts) + "。"
