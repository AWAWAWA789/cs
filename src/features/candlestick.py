"""Candlestick pattern recognition without volume data.

Currently implements Pin Bar and Engulfing patterns, which are the two most
relevant reversal patterns for the MVP. Patterns are defined using only OHLC
and are designed to be evaluated bar-by-bar without future information.
"""

from __future__ import annotations

import pandas as pd


def _body(open_: pd.Series, close: pd.Series) -> pd.Series:
    """Return the absolute body size."""
    return (close - open_).abs()


def _is_bullish(open_: pd.Series, close: pd.Series) -> pd.Series:
    """Return True for bullish candles (close > open)."""
    return close > open_


def _is_bearish(open_: pd.Series, close: pd.Series) -> pd.Series:
    """Return True for bearish candles (close < open)."""
    return close < open_


def identify_pin_bar(
    df: pd.DataFrame,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    body_to_wick_ratio: float = 2.0,
    max_opposite_wick_ratio: float = 0.5,
) -> pd.DataFrame:
    """Add bullish and bearish Pin Bar columns to ``df``.

    A Pin Bar is defined by:
    - A small body relative to the total range.
    - A long wick in the direction opposite to the expected reversal.
    - A short wick on the opposite side.

    Args:
        body_to_wick_ratio: The dominant wick must be at least this many
            times the body size.
        max_opposite_wick_ratio: The opposite wick must be at most this
            fraction of the body size.
    """
    result = df.copy()
    open_ = df[open_col]
    high = df[high_col]
    low = df[low_col]
    close = df[close_col]

    body = _body(open_, close)
    bullish = _is_bullish(open_, close)
    bearish = _is_bearish(open_, close)

    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low

    # A zero-body candle cannot be a pin bar; enforce body > 0.
    has_body = body > 0

    result["pin_bar_bull"] = (
        bullish
        & has_body
        & (lower_wick >= body * body_to_wick_ratio)
        & (upper_wick <= body * max_opposite_wick_ratio)
    )
    result["pin_bar_bear"] = (
        bearish
        & has_body
        & (upper_wick >= body * body_to_wick_ratio)
        & (lower_wick <= body * max_opposite_wick_ratio)
    )
    return result


def identify_engulfing(
    df: pd.DataFrame,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> pd.DataFrame:
    """Add bullish and bearish Engulfing pattern columns to ``df``.

    A bullish engulfing candle fully consumes the previous candle's body from
    below, while a bearish engulfing candle consumes it from above.
    """
    result = df.copy()
    open_ = df[open_col]
    close = df[close_col]

    prev_open = open_.shift(1)
    prev_close = close.shift(1)
    prev_bullish = prev_close > prev_open
    prev_bearish = prev_close < prev_open

    curr_bullish = close > open_
    curr_bearish = close < open_

    curr_body = (close - open_).abs()
    prev_body = (prev_close - prev_open).abs()

    result["engulfing_bull"] = (
        curr_bullish
        & prev_bearish
        & (open_ <= prev_close)
        & (close >= prev_open)
        & (curr_body > prev_body)
    )
    result["engulfing_bear"] = (
        curr_bearish
        & prev_bullish
        & (open_ >= prev_close)
        & (close <= prev_open)
        & (curr_body > prev_body)
    )

    result["engulfing_bull"] = result["engulfing_bull"].fillna(False)
    result["engulfing_bear"] = result["engulfing_bear"].fillna(False)
    return result


def identify_candlestick_patterns(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Run all available candlestick pattern detectors on ``df``.

    Adds ``pin_bar_bull``, ``pin_bar_bear``, ``engulfing_bull`` and
    ``engulfing_bear`` columns.
    """
    df = identify_pin_bar(df, **kwargs)
    df = identify_engulfing(df)
    return df
