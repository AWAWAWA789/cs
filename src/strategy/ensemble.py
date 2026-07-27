"""Dual-strategy ensemble that combines pullback and trend-following signals.

The ensemble decides which sub-strategy to trust based on market regime and
trend strength (ADX).  In strong uptrends it follows breakouts; in weaker or
choppier conditions it falls back to the pullback / Smart Money strategy.

No volume data is used.
"""

from __future__ import annotations

import pandas as pd

from src.features.market_regime import add_market_regime_feature
from src.features.signal_quality import add_signal_quality_features
from src.features.trend_strength import add_trend_strength_features
from src.strategy.signal import SignalParams, generate_signals
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)


class EnsembleParams:
    """Parameters controlling the dual-strategy ensemble."""

    def __init__(
        self,
        pullback_params: SignalParams | None = None,
        trend_params: TrendFollowingParams | None = None,
        mode: str = "regime_switch",
        adx_threshold: float = 25.0,
        regime_confirmations: int = 4,
        dynamic_weight_adx_scale: float = 25.0,
        dynamic_weight_min: float = 0.2,
        dynamic_weight_max: float = 0.8,
        use_signal_quality: bool = False,
        min_signal_quality: float = 0.0,
        quality_trend_weight: float = 0.4,
        quality_structure_weight: float = 0.4,
        quality_confluence_weight: float = 0.2,
    ) -> None:
        self.pullback_params = pullback_params or SignalParams()
        self.trend_params = trend_params or TrendFollowingParams()
        self.mode = mode
        self.adx_threshold = adx_threshold
        self.regime_confirmations = regime_confirmations
        self.dynamic_weight_adx_scale = dynamic_weight_adx_scale
        self.dynamic_weight_min = dynamic_weight_min
        self.dynamic_weight_max = dynamic_weight_max
        self.use_signal_quality = use_signal_quality
        self.min_signal_quality = min_signal_quality
        self.quality_trend_weight = quality_trend_weight
        self.quality_structure_weight = quality_structure_weight
        self.quality_confluence_weight = quality_confluence_weight


def _trend_weight(
    adx_value: float,
    regime: str,
    adx_scale: float,
    weight_min: float,
    weight_max: float,
) -> float:
    """Return the trend-following weight given trend strength and regime.

    The weight scales linearly with ADX once the regime is uptrend.  In non-
    uptrend regimes the weight is pinned to the minimum so that pullback logic
    dominates.
    """
    if pd.isna(adx_value) or regime != "uptrend":
        return weight_min
    normalized = min(1.0, max(0.0, adx_value / adx_scale))
    return weight_min + normalized * (weight_max - weight_min)


def _select_signal(
    pullback_signal: bool,
    trend_signal: bool,
    mode: str,
    trend_weight: float,
) -> tuple[bool, str]:
    """Choose which sub-strategy signal to emit.

    Returns:
        Tuple of (signal_active, source_label). ``source_label`` is one of
        ``pullback``, ``trend`` or ``both``.
    """
    if mode == "union":
        if pullback_signal and trend_signal:
            return True, "both"
        if trend_signal:
            return True, "trend"
        if pullback_signal:
            return True, "pullback"
        return False, ""

    if mode == "dynamic_weight":
        # Both signals must pass quality filters before weighting.
        if pullback_signal and trend_signal:
            return True, "trend" if trend_weight >= 0.5 else "pullback"
        if trend_signal and trend_weight >= 0.5:
            return True, "trend"
        if pullback_signal and trend_weight < 0.5:
            return True, "pullback"
        return False, ""

    # regime_switch: prefer trend when conditions are met, otherwise pullback.
    if trend_signal:
        return True, "trend"
    if pullback_signal:
        return True, "pullback"
    return False, ""


def generate_ensemble_signals(
    df: pd.DataFrame,
    params: EnsembleParams | None = None,
) -> pd.DataFrame:
    """Add ensemble long-signal columns to ``df``.

    Adds:
    - ``signal_long``: boolean flag for a long entry signal.
    - ``signal_reason``: reason tagged with the originating sub-strategy.
    - ``signal_swing_low``, ``signal_swing_high``: anchors used for risk management.
    - ``ensemble_trend_weight``: weight assigned to trend-following (for diagnostics).
    - ``signal_quality``: quality score when quality filtering is enabled.

    Args:
        df: OHLC DataFrame.
        params: Ensemble parameters.
    """
    params = params or EnsembleParams()

    pullback_df = generate_signals(df, params.pullback_params)
    trend_df = generate_trend_following_signals(df, params.trend_params)

    features_df = add_trend_strength_features(df.copy())
    features_df = add_market_regime_feature(
        features_df,
        swing_order=params.pullback_params.swing_order + 1,
        confirmations=params.regime_confirmations,
    )

    if params.use_signal_quality:
        pullback_df = add_signal_quality_features(
            pullback_df,
            trend_weight=params.quality_trend_weight,
            structure_weight=params.quality_structure_weight,
            confluence_weight=params.quality_confluence_weight,
        )
        trend_df = add_signal_quality_features(
            trend_df,
            trend_weight=params.quality_trend_weight,
            structure_weight=params.quality_structure_weight,
            confluence_weight=params.quality_confluence_weight,
        )

    signal_long = pd.Series(False, index=df.index)
    signal_reason = pd.Series("", index=df.index, dtype=object)
    swing_low_prices = pd.Series(dtype=float, index=df.index)
    swing_high_prices = pd.Series(dtype=float, index=df.index)
    trend_weights = pd.Series(dtype=float, index=df.index)
    quality_scores = pd.Series(dtype=float, index=df.index)

    for i in range(len(df)):
        adx_value = features_df["adx"].iloc[i]
        regime = features_df["market_regime"].iloc[i]
        regime_ok = regime == "uptrend"

        trend_weight = _trend_weight(
            adx_value,
            regime,
            params.dynamic_weight_adx_scale,
            params.dynamic_weight_min,
            params.dynamic_weight_max,
        )
        trend_weights.iloc[i] = trend_weight

        use_trend = False
        if params.mode == "regime_switch":
            adx_ok = pd.notna(adx_value) and adx_value >= params.adx_threshold
            use_trend = adx_ok and regime_ok

        pullback_signal = bool(pullback_df["signal_long"].iloc[i])
        trend_signal = bool(trend_df["signal_long"].iloc[i])

        if params.use_signal_quality:
            p_quality = float(pullback_df["signal_quality"].iloc[i])
            t_quality = float(trend_df["signal_quality"].iloc[i])
            if pullback_signal and p_quality < params.min_signal_quality:
                pullback_signal = False
            if trend_signal and t_quality < params.min_signal_quality:
                trend_signal = False
            quality_scores.iloc[i] = max(p_quality, t_quality)

        active, source = _select_signal(
            pullback_signal,
            trend_signal,
            params.mode,
            trend_weight if params.mode == "dynamic_weight" else (1.0 if use_trend else 0.0),
        )

        if not active:
            continue

        if source == "trend":
            signal_long.iloc[i] = True
            reason = trend_df["signal_reason"].iloc[i]
            signal_reason.iloc[i] = f"ensemble_trend_{reason}"
            swing_low_prices.iloc[i] = trend_df["signal_swing_low"].iloc[i]
            swing_high_prices.iloc[i] = trend_df["signal_swing_high"].iloc[i]
        elif source == "pullback":
            signal_long.iloc[i] = True
            reason = pullback_df["signal_reason"].iloc[i]
            signal_reason.iloc[i] = f"ensemble_pullback_{reason}"
            swing_low_prices.iloc[i] = pullback_df["signal_swing_low"].iloc[i]
            swing_high_prices.iloc[i] = pullback_df["signal_swing_high"].iloc[i]
        elif source == "both":
            # Prefer trend label and trend anchors when both fire.
            signal_long.iloc[i] = True
            reason = trend_df["signal_reason"].iloc[i]
            signal_reason.iloc[i] = f"ensemble_trend_{reason}"
            swing_low_prices.iloc[i] = trend_df["signal_swing_low"].iloc[i]
            swing_high_prices.iloc[i] = trend_df["signal_swing_high"].iloc[i]

    result = df.copy()
    result["signal_long"] = signal_long
    result["signal_reason"] = signal_reason
    result["signal_swing_low"] = swing_low_prices
    result["signal_swing_high"] = swing_high_prices
    result["ensemble_trend_weight"] = trend_weights
    if params.use_signal_quality:
        result["signal_quality"] = quality_scores
    return result
