"""Independent trend-following strategy module.

This strategy generates long signals from price-action breakouts without relying
on pullback or Smart Money concepts.  It is designed to complement the callback
strategy in strong trending markets.

No volume data is used.
"""

from __future__ import annotations

import pandas as pd

from src.features.structure import add_structure_features
from src.features.trend_following import add_trend_following_features


class TrendFollowingParams:
    """Parameters controlling the trend-following strategy."""

    def __init__(
        self,
        swing_order: int = 2,
        confirmations: int = 1,
        trend_strength_threshold: float | None = 25.0,
        adx_period: int = 14,
        use_higher_high_breakout: bool = False,
        require_uptrend: bool = True,
        use_di_filter: bool = False,
        use_volatility_filter: bool = False,
        volatility_atr_multiplier: float = 0.5,
        use_pullback_confirmation: bool = False,
        pullback_lookback: int = 5,
        pullback_buffer: float = 0.005,
    ) -> None:
        self.swing_order = swing_order
        self.confirmations = confirmations
        self.trend_strength_threshold = trend_strength_threshold
        self.adx_period = adx_period
        self.use_higher_high_breakout = use_higher_high_breakout
        self.require_uptrend = require_uptrend
        self.use_di_filter = use_di_filter
        self.use_volatility_filter = use_volatility_filter
        self.volatility_atr_multiplier = volatility_atr_multiplier
        self.use_pullback_confirmation = use_pullback_confirmation
        self.pullback_lookback = pullback_lookback
        self.pullback_buffer = pullback_buffer


def _last_swing_price(
    series: pd.Series, mask: pd.Series, index: int
) -> float | None:
    """Return the most recent price at or before ``index`` where ``mask`` is True."""
    subset = series.where(mask).iloc[: index + 1]
    if subset.dropna().empty:
        return None
    return float(subset.dropna().iloc[-1])


def generate_trend_following_signals(
    df: pd.DataFrame,
    params: TrendFollowingParams | None = None,
) -> pd.DataFrame:
    """Add trend-following long-signal columns to ``df``.

    Adds:
    - ``signal_long``: boolean flag for a long entry signal.
    - ``signal_reason``: human-readable reason when a signal fires.
    - ``signal_swing_low``, ``signal_swing_high``: anchors used for risk management.

    Args:
        df: OHLC DataFrame.
        params: Trend-following parameters.
    """
    params = params or TrendFollowingParams()

    result = add_structure_features(
        df, swing_order=params.swing_order, confirmations=params.confirmations
    )
    result = add_trend_following_features(
        result,
        trend_strength_threshold=params.trend_strength_threshold,
        adx_period=params.adx_period,
        use_di_filter=params.use_di_filter,
        use_volatility_filter=params.use_volatility_filter,
        volatility_atr_multiplier=params.volatility_atr_multiplier,
        use_pullback_confirmation=params.use_pullback_confirmation,
        pullback_lookback=params.pullback_lookback,
        pullback_buffer=params.pullback_buffer,
    )

    signal_long = pd.Series(False, index=result.index)
    signal_reason = pd.Series("", index=result.index, dtype=object)
    swing_low_prices = pd.Series(dtype=float, index=result.index)
    swing_high_prices = pd.Series(dtype=float, index=result.index)

    for i in range(len(result)):
        if params.require_uptrend and result["trend"].iloc[i] != 1:
            continue

        signal = False
        reason = ""
        if params.use_pullback_confirmation:
            if result["breakout_pullback"].iloc[i]:
                signal = True
                reason = "trend_following_breakout_pullback"
        elif params.use_higher_high_breakout:
            if result["higher_high_breakout"].iloc[i]:
                signal = True
                reason = "trend_following_higher_high"
        else:
            if result["breakout_follow_through"].iloc[i]:
                signal = True
                reason = "trend_following_breakout"

        if not signal:
            continue

        low_price = _last_swing_price(result["low"], result["swing_low"], i)
        high_price = _last_swing_price(result["high"], result["swing_high"], i)
        if low_price is None or high_price is None:
            continue

        signal_long.iloc[i] = True
        signal_reason.iloc[i] = reason
        swing_low_prices.iloc[i] = low_price
        swing_high_prices.iloc[i] = high_price

    result["signal_long"] = signal_long
    result["signal_reason"] = signal_reason
    result["signal_swing_low"] = swing_low_prices
    result["signal_swing_high"] = swing_high_prices
    return result
