"""Price-structure confirmation helpers.

These functions use only swing points and price levels to determine trend
direction, validate breakouts and detect pullbacks. No volume information is
used.
"""

from __future__ import annotations

import pandas as pd

from src.features.swing import identify_swing_points


def _last_n_values(series: pd.Series, n: int) -> list:
    """Return the last ``n`` non-null values of a series in order."""
    return series.dropna().iloc[-n:].tolist()


def trend_direction(
    df: pd.DataFrame,
    swing_high_col: str = "swing_high",
    swing_low_col: str = "swing_low",
    high_col: str = "high",
    low_col: str = "low",
    confirmations: int = 2,
) -> pd.Series:
    """Return a rolling trend label for each row based on recent swing points.

    The label is:
    - ``1`` (uptrend): the last ``confirmations`` swing highs and lows are
      higher.
    - ``-1`` (downtrend): the last ``confirmations`` swing highs and lows are
      lower.
    - ``0`` (unclear): anything else or insufficient swing points.

    The trend is recomputed at every bar using only the swing points observed
    up to that bar, making the label usable in a backtest.
    """
    high_prices = df[high_col].where(df[swing_high_col])
    low_prices = df[low_col].where(df[swing_low_col])

    result = pd.Series(0, index=df.index, dtype=int)

    for i in range(len(df)):
        highs = _last_n_values(high_prices.iloc[: i + 1], confirmations + 1)
        lows = _last_n_values(low_prices.iloc[: i + 1], confirmations + 1)

        if len(highs) < confirmations + 1 or len(lows) < confirmations + 1:
            trend = 0
        elif all(highs[j] < highs[j + 1] for j in range(confirmations)) and all(
            lows[j] < lows[j + 1] for j in range(confirmations)
        ):
            trend = 1
        elif all(highs[j] > highs[j + 1] for j in range(confirmations)) and all(
            lows[j] > lows[j + 1] for j in range(confirmations)
        ):
            trend = -1
        else:
            trend = 0

        result.iloc[i] = trend

    return result


def add_structure_features(
    df: pd.DataFrame,
    swing_order: int = 2,
    high_col: str = "high",
    low_col: str = "low",
) -> pd.DataFrame:
    """Add swing points and trend labels to ``df``.

    Adds ``swing_high``, ``swing_low`` and ``trend`` columns.
    """
    result = identify_swing_points(df, high_col=high_col, low_col=low_col, order=swing_order)
    result["trend"] = trend_direction(result)
    return result


def breakout_follow_through(
    df: pd.DataFrame,
    level: float,
    close_col: str = "close",
    direction: str = "bullish",
) -> pd.Series:
    """Return True on bars where a breakout above/below ``level`` is followed
    through by the close.

    A bullish follow-through requires the current close to be above ``level``
    while the previous close was at or below it. A bearish follow-through is
    the inverse.
    """
    close = df[close_col]
    prev_close = close.shift(1)

    if direction == "bullish":
        return (close > level) & (prev_close <= level)
    return (close < level) & (prev_close >= level)
