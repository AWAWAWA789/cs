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
from src.features.structure import add_structure_features


class SignalParams:
    """Parameters controlling signal detection."""

    def __init__(
        self,
        swing_order: int = 2,
        fib_tolerance: float = 0.03,
        target_levels: tuple[str, ...] = ("0.5", "0.618"),
        confirmations: int = 2,
    ) -> None:
        self.swing_order = swing_order
        self.fib_tolerance = fib_tolerance
        self.target_levels = target_levels
        self.confirmations = confirmations


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


def generate_signals(df: pd.DataFrame, params: SignalParams | None = None) -> pd.DataFrame:
    """Add long-signal columns to ``df``.

    Adds:
    - ``signal_long``: boolean flag for a long entry signal.
    - ``signal_reason``: human-readable reason when a signal fires.
    - ``swing_low_price``, ``swing_high_price``: anchors used for the signal.
    """
    params = params or SignalParams()

    result = add_structure_features(
        df, swing_order=params.swing_order, confirmations=params.confirmations
    )
    result = identify_candlestick_patterns(result)

    signal_long = pd.Series(False, index=result.index)
    signal_reason = pd.Series("", index=result.index, dtype=object)
    swing_low_prices = pd.Series(dtype=float, index=result.index)
    swing_high_prices = pd.Series(dtype=float, index=result.index)

    for i in range(len(result)):
        if result["trend"].iloc[i] != 1:
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

        if near and has_pattern:
            signal_long.iloc[i] = True
            pattern_name = ""
            if result["pin_bar_bull"].iloc[i]:
                pattern_name = "pin_bar"
            elif result["engulfing_bull"].iloc[i]:
                pattern_name = "engulfing"
            signal_reason.iloc[i] = (
                f"uptrend_pullback_fib_{level_name}_{pattern_name}"
            )
            swing_low_prices.iloc[i] = low_price
            swing_high_prices.iloc[i] = high_price

    result["signal_long"] = signal_long
    result["signal_reason"] = signal_reason
    result["signal_swing_low"] = swing_low_prices
    result["signal_swing_high"] = swing_high_prices
    return result
