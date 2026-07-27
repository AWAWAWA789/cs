"""MVP signal generation logic.

The long signal combines three price-action concepts:
1. Uptrend confirmed by higher swing highs and higher swing lows.
2. Price pulling back to a key Fibonacci retracement zone (0.5 or 0.618).
3. A bullish reversal candlestick pattern (Pin Bar or Engulfing).

No volume data is used.
"""

from __future__ import annotations

import pandas as pd

from src.features.candlestick import identify_candlestick_patterns
from src.features.fibonacci import is_near_level, retracement_levels
from src.features.smart_money import add_smart_money_features
from src.features.structure import add_structure_features
from src.features.trend_following import add_trend_following_features


class SignalParams:
    """Parameters controlling signal detection."""

    def __init__(
        self,
        swing_order: int = 2,
        fib_tolerance: float = 0.03,
        target_levels: tuple[str, ...] = ("0.5", "0.618"),
        confirmations: int = 2,
        use_smart_money: bool = True,
        liquidity_grab_buffer: float = 0.005,
        use_trend_following: bool = True,
    ) -> None:
        self.swing_order = swing_order
        self.fib_tolerance = fib_tolerance
        self.target_levels = target_levels
        self.confirmations = confirmations
        self.use_smart_money = use_smart_money
        self.liquidity_grab_buffer = liquidity_grab_buffer
        self.use_trend_following = use_trend_following


def _last_swing_price(
    series: pd.Series, mask: pd.Series, index: int
) -> float | None:
    """Return the most recent price at or before ``index`` where ``mask`` is True."""
    subset = series.where(mask).iloc[: index + 1]
    if subset.dropna().empty:
        return None
    return float(subset.dropna().iloc[-1])


def _last_swing_index(mask: pd.Series, index: int) -> int | None:
    """Return the index of the most recent True value at or before ``index``."""
    positions = mask.iloc[: index + 1]
    true_positions = positions[positions].index
    if len(true_positions) == 0:
        return None
    return int(true_positions[-1])


def generate_signals(
    df: pd.DataFrame,
    params: SignalParams | None = None,
    *,
    trend_col: str = "trend",
) -> pd.DataFrame:
    """Add long-signal columns to ``df``.

    Adds:
    - ``signal_long``: boolean flag for a long entry signal.
    - ``signal_reason``: human-readable reason when a signal fires.
    - ``swing_low_price``, ``swing_high_price``: anchors used for the signal.

    Args:
        df: OHLC DataFrame. Trend labels are computed with
            ``add_structure_features`` unless ``trend_col`` already exists.
        params: Signal parameters.
        trend_col: Column name to use for trend filtering. Defaults to ``trend``.
            Useful for multi-timeframe analysis where the column may be named
            ``higher_trend``.
    """
    params = params or SignalParams()

    # Always compute swing points on the input timeframe; they are needed by
    # candlestick, Smart Money and risk calculations regardless of whether the
    # trend label comes from a higher timeframe.
    result = add_structure_features(
        df, swing_order=params.swing_order, confirmations=params.confirmations
    )
    # If a higher timeframe trend column is provided, keep it alongside the
    # locally computed swing points.
    if trend_col in df.columns and trend_col != "trend":
        result[trend_col] = df[trend_col].values
    result = identify_candlestick_patterns(result)
    if params.use_smart_money:
        result = add_smart_money_features(
            result, liquidity_grab_buffer=params.liquidity_grab_buffer
        )
    if params.use_trend_following:
        result = add_trend_following_features(result)

    signal_long = pd.Series(False, index=result.index)
    signal_reason = pd.Series("", index=result.index, dtype=object)
    swing_low_prices = pd.Series(dtype=float, index=result.index)
    swing_high_prices = pd.Series(dtype=float, index=result.index)

    for i in range(len(result)):
        if result[trend_col].iloc[i] != 1:
            continue

        low_price = _last_swing_price(result["low"], result["swing_low"], i)
        high_price = _last_swing_price(result["high"], result["swing_high"], i)

        if low_price is None or high_price is None:
            continue

        levels = retracement_levels(low_price, high_price)
        close = result["close"].iloc[i]

        near, level_name, _ = is_near_level(
            close,
            levels,
            tolerance=params.fib_tolerance,
            target_levels=params.target_levels,
        )

        has_pattern = (
            result["pin_bar_bull"].iloc[i] or result["engulfing_bull"].iloc[i]
        )

        smart_money = False
        smart_money_reason = ""
        if params.use_smart_money:
            if result["liquidity_grab"].iloc[i]:
                smart_money = True
                smart_money_reason = "smart_money_liquidity_grab"
            elif result["order_block"].iloc[i]:
                smart_money = True
                smart_money_reason = "smart_money_order_block"
            elif result["fair_value_gap"].iloc[i]:
                smart_money = True
                smart_money_reason = "smart_money_fvg"

        trend_following = False
        trend_following_reason = ""
        if params.use_trend_following:
            if result["higher_high_breakout"].iloc[i]:
                trend_following = True
                trend_following_reason = "trend_following_higher_high"
            elif result["breakout_follow_through"].iloc[i]:
                trend_following = True
                trend_following_reason = "trend_following_breakout"

        if (near and has_pattern) or smart_money or trend_following:
            signal_long.iloc[i] = True
            swing_low_prices.iloc[i] = low_price
            swing_high_prices.iloc[i] = high_price

            if near and has_pattern:
                if result["pin_bar_bull"].iloc[i]:
                    pattern_name = "pin_bar"
                else:
                    pattern_name = "engulfing"
                signal_reason.iloc[i] = (
                    f"uptrend_pullback_fib_{level_name}_{pattern_name}"
                )
            elif smart_money:
                signal_reason.iloc[i] = smart_money_reason
            elif trend_following:
                signal_reason.iloc[i] = trend_following_reason

    result["signal_long"] = signal_long
    result["signal_reason"] = signal_reason
    result["signal_swing_low"] = swing_low_prices
    result["signal_swing_high"] = swing_high_prices
    return result
