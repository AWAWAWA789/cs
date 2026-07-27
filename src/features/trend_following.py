"""Trend-following price-action features without volume data.

These features capture breakout and momentum opportunities that complement the
callback-oriented Smart Money and Fibonacci signals. They are designed to
perform better in strong trending markets where pullbacks are shallow and
short-lived.
"""

from __future__ import annotations

import pandas as pd


def breakout_with_follow_through(
    df: pd.DataFrame,
    swing_high_col: str = "swing_high",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    open_col: str = "open",
) -> pd.Series:
    """Return True when price breaks above the most recent swing high with
    bullish follow-through.

    A valid breakout requires:
    - The current bar trades above the most recent swing high.
    - The current bar closes above that swing high.
    - The current bar is bullish (close > open).
    - The previous close was at or below the swing high, avoiding repeated
      signals while price is already extended.
    """
    # Forward-filled price of the most recent swing high.
    swing_high_prices = df[high_col].where(df[swing_high_col]).ffill()

    high = df[high_col]
    low = df[low_col]
    close = df[close_col]
    open_ = df[open_col]
    prev_close = close.shift(1)

    bullish = close > open_
    broke_above = high > swing_high_prices
    close_above = close > swing_high_prices
    not_already_extended = prev_close <= swing_high_prices

    return bullish & broke_above & close_above & not_already_extended


def higher_high_breakout(
    df: pd.DataFrame,
    swing_high_col: str = "swing_high",
    high_col: str = "high",
    close_col: str = "close",
    open_col: str = "open",
    lookback: int = 2,
) -> pd.Series:
    """Return True when the current bar makes a new high relative to the last
    ``lookback`` swing highs and closes strongly.

    This is a stricter breakout that requires the price to exceed multiple
    prior swing highs, indicating a stronger trend continuation.
    """
    swing_high_indices = df.index[df[swing_high_col]].tolist()

    result = pd.Series(False, index=df.index)
    if len(swing_high_indices) < lookback:
        return result

    high = df[high_col]
    close = df[close_col]
    open_ = df[open_col]
    prev_close = close.shift(1)

    for j in range(len(df)):
        # Swing highs strictly before the current bar.
        prior_indices = [s for s in swing_high_indices if s < df.index[j]]
        if len(prior_indices) < lookback:
            continue

        prev_highs = [df.loc[s, high_col] for s in prior_indices[-lookback:]]
        max_prev_high = max(prev_highs)

        broke_above = high.iloc[j] > max_prev_high
        close_above = close.iloc[j] > max_prev_high
        bullish = close.iloc[j] > open_.iloc[j]
        # Avoid repeated signals while price is already trading above the zone.
        not_already_extended = prev_close.iloc[j] <= max_prev_high

        if broke_above and close_above and bullish and not_already_extended:
            result.iloc[j] = True

    return result


def add_trend_following_features(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Add trend-following feature columns to ``df``.

    Adds:
    - ``breakout_follow_through``: basic swing-high breakout signal.
    - ``higher_high_breakout``: multi-swing-high breakout signal.
    """
    result = df.copy()
    result["breakout_follow_through"] = breakout_with_follow_through(result, **kwargs)
    result["higher_high_breakout"] = higher_high_breakout(result, **kwargs)
    return result
