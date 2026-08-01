"""Swing High / Swing Low detection.

A swing point is a local extremum in price. The implementation scans a
configurable number of bars on each side of a candidate bar and marks it
only when it is strictly higher (for highs) or lower (for lows) than every
bar in that window.
"""

from __future__ import annotations

import pandas as pd


def _is_local_max(series: pd.Series, order: int) -> pd.Series:
    """Return a boolean mask where ``series`` is a strict local maximum."""
    max_left = series.shift(1).rolling(window=order, min_periods=order).max()
    max_right = (
        series.iloc[::-1]
        .shift(1)
        .rolling(window=order, min_periods=order)
        .max()
        .iloc[::-1]
    )
    return (series > max_left) & (series > max_right)


def _is_local_min(series: pd.Series, order: int) -> pd.Series:
    """Return a boolean mask where ``series`` is a strict local minimum."""
    min_left = series.shift(1).rolling(window=order, min_periods=order).min()
    min_right = (
        series.iloc[::-1]
        .shift(1)
        .rolling(window=order, min_periods=order)
        .min()
        .iloc[::-1]
    )
    return (series < min_left) & (series < min_right)


def identify_swing_points(
    df: pd.DataFrame, high_col: str = "high", low_col: str = "low", order: int = 2
) -> pd.DataFrame:
    """Add ``swing_high`` and ``swing_low`` boolean columns to ``df``.

    Args:
        df: DataFrame containing price data.
        high_col: Name of the high-price column.
        low_col: Name of the low-price column.
        order: Number of bars on each side that must be lower/higher.

    Returns:
        A copy of ``df`` with two additional boolean columns:
        ``swing_high`` and ``swing_low``.
    """
    result = df.copy()
    result["swing_high"] = _is_local_max(df[high_col], order)
    result["swing_low"] = _is_local_min(df[low_col], order)
    return result


def swing_highs(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows marked as swing highs."""
    return df[df["swing_high"]].copy()


def swing_lows(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows marked as swing lows."""
    return df[df["swing_low"]].copy()
