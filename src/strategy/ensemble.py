"""Dual-strategy ensemble that combines pullback and trend-following signals.

The ensemble decides which sub-strategy to trust based on market regime and
trend strength (ADX).  In strong uptrends it follows breakouts; in weaker or
choppier conditions it falls back to the pullback / Smart Money strategy.

No volume data is used.
"""

from __future__ import annotations

import pandas as pd

from src.features.market_regime import add_market_regime_feature
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
    ) -> None:
        self.pullback_params = pullback_params or SignalParams()
        self.trend_params = trend_params or TrendFollowingParams()
        self.mode = mode
        self.adx_threshold = adx_threshold
        self.regime_confirmations = regime_confirmations


def generate_ensemble_signals(
    df: pd.DataFrame,
    params: EnsembleParams | None = None,
) -> pd.DataFrame:
    """Add ensemble long-signal columns to ``df``.

    Adds:
    - ``signal_long``: boolean flag for a long entry signal.
    - ``signal_reason``: reason tagged with the originating sub-strategy.
    - ``signal_swing_low``, ``signal_swing_high``: anchors used for risk management.

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

    signal_long = pd.Series(False, index=df.index)
    signal_reason = pd.Series("", index=df.index, dtype=object)
    swing_low_prices = pd.Series(dtype=float, index=df.index)
    swing_high_prices = pd.Series(dtype=float, index=df.index)

    for i in range(len(df)):
        use_trend = False
        if params.mode == "regime_switch":
            adx_value = features_df["adx"].iloc[i]
            adx_ok = pd.notna(adx_value) and adx_value >= params.adx_threshold
            regime_ok = features_df["market_regime"].iloc[i] == "uptrend"
            use_trend = adx_ok and regime_ok

        # In regime-switch mode we prefer trend-following when conditions are met;
        # in union mode we accept either signal, preferring trend-following labels.
        if (use_trend or params.mode == "union") and trend_df["signal_long"].iloc[i]:
            signal_long.iloc[i] = True
            reason = trend_df["signal_reason"].iloc[i]
            signal_reason.iloc[i] = f"ensemble_trend_{reason}"
            swing_low_prices.iloc[i] = trend_df["signal_swing_low"].iloc[i]
            swing_high_prices.iloc[i] = trend_df["signal_swing_high"].iloc[i]
            continue

        if pullback_df["signal_long"].iloc[i]:
            signal_long.iloc[i] = True
            reason = pullback_df["signal_reason"].iloc[i]
            signal_reason.iloc[i] = f"ensemble_pullback_{reason}"
            swing_low_prices.iloc[i] = pullback_df["signal_swing_low"].iloc[i]
            swing_high_prices.iloc[i] = pullback_df["signal_swing_high"].iloc[i]

    result = df.copy()
    result["signal_long"] = signal_long
    result["signal_reason"] = signal_reason
    result["signal_swing_low"] = swing_low_prices
    result["signal_swing_high"] = swing_high_prices
    return result
