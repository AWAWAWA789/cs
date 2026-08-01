"""Trend-following price-action features without volume data.

These features capture breakout and momentum opportunities that complement the
callback-oriented Smart Money and Fibonacci signals. They are designed to
perform better in strong trending markets where pullbacks are shallow and
short-lived.
"""

from __future__ import annotations

import pandas as pd

from src.features.trend_strength import add_trend_strength_features


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


def breakout_pullback_confirmation(
    df: pd.DataFrame,
    breakout_col: str = "breakout_follow_through",
    swing_high_col: str = "swing_high",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    open_col: str = "open",
    lookback: int = 5,
    buffer: float = 0.005,
) -> pd.Series:
    """Return True after a breakout when price pulls back to the breakout zone
    and confirms support with a bullish close.

    Logic:
    - Identify raw breakout bars from ``breakout_col``.
    - The breakout level is the most recent swing high price at the breakout bar.
    - Within the next ``lookback`` bars, look for a bar whose low touches or
      drops slightly below the breakout level (within ``buffer``) but whose
      close holds at or above the breakout level.
    - Enter on the confirming bar if it is bullish.

    This reduces buying at the top of a breakout that immediately reverses.
    """
    swing_high_prices = df[high_col].where(df[swing_high_col]).ffill()
    breakout = df[breakout_col].fillna(False)

    low = df[low_col]
    close = df[close_col]
    open_ = df[open_col]

    result = pd.Series(False, index=df.index)
    breakout_levels = pd.Series(dtype=float, index=df.index)

    # Record the breakout level for each breakout bar.
    for i in range(len(df)):
        if breakout.iloc[i]:
            breakout_levels.iloc[i] = swing_high_prices.iloc[i]

    for j in range(len(df)):
        if not breakout.iloc[j]:
            continue
        level = breakout_levels.iloc[j]
        if pd.isna(level):
            continue

        # Search within the lookback window after the breakout bar.
        end = min(len(df), j + lookback + 1)
        for k in range(j + 1, end):
            lower_bound = level * (1 - buffer)
            touched = low.iloc[k] <= level * (1 + buffer)
            held = close.iloc[k] >= lower_bound
            bullish = close.iloc[k] > open_.iloc[k]
            if touched and held and bullish:
                result.iloc[k] = True
                break

    return result


def add_trend_following_features(
    df: pd.DataFrame,
    trend_strength_threshold: float | None = None,
    adx_period: int = 14,
    use_di_filter: bool = False,
    use_volatility_filter: bool = False,
    volatility_atr_multiplier: float = 0.5,
    use_pullback_confirmation: bool = False,
    pullback_lookback: int = 5,
    pullback_buffer: float = 0.005,
    **kwargs,
) -> pd.DataFrame:
    """Add trend-following feature columns to ``df``.

    Adds:
    - ``breakout_follow_through``: basic swing-high breakout signal.
    - ``higher_high_breakout``: multi-swing-high breakout signal.
    - ``breakout_pullback``: breakout followed by a pullback retest.

    Filtering options:
    - ``trend_strength_threshold``: when provided, breakout signals are AND-ed
      with ``adx >= threshold``.
    - ``use_di_filter``: additionally require ``di_plus > di_minus`` so that
      only upward directional movement is accepted.
    - ``use_volatility_filter``: require the breakout magnitude (high - swing
      high) to exceed ``volatility_atr_multiplier * atr``.
    - ``use_pullback_confirmation``: generate a separate pullback-confirmed
      breakout column instead of the immediate breakout.
    """
    result = df.copy()
    result["breakout_follow_through"] = breakout_with_follow_through(result, **kwargs)
    result["higher_high_breakout"] = higher_high_breakout(result, **kwargs)

    if use_pullback_confirmation:
        result["breakout_pullback"] = breakout_pullback_confirmation(
            result,
            breakout_col="breakout_follow_through",
            lookback=pullback_lookback,
            buffer=pullback_buffer,
        )

    if trend_strength_threshold is not None or use_di_filter or use_volatility_filter:
        result = add_trend_strength_features(result, period=adx_period)

        if trend_strength_threshold is not None:
            strength_ok = result["adx"] >= trend_strength_threshold
            result["breakout_follow_through"] = result["breakout_follow_through"] & strength_ok
            result["higher_high_breakout"] = result["higher_high_breakout"] & strength_ok

        if use_di_filter:
            di_ok = result["di_plus"] > result["di_minus"]
            result["breakout_follow_through"] = result["breakout_follow_through"] & di_ok
            result["higher_high_breakout"] = result["higher_high_breakout"] & di_ok

        if use_volatility_filter:
            swing_high_prices = result[kwargs.get("high_col", "high")].where(
                result[kwargs.get("swing_high_col", "swing_high")]
            ).ffill()
            breakout_size = result[kwargs.get("high_col", "high")] - swing_high_prices
            volatility_ok = breakout_size >= volatility_atr_multiplier * result["atr"]
            result["breakout_follow_through"] = result["breakout_follow_through"] & volatility_ok
            result["higher_high_breakout"] = result["higher_high_breakout"] & volatility_ok

    return result
