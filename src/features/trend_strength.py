"""Trend-strength indicators without volume data.

Provides a price-only ADX-style oscillator using directional movement and
average true range. This helps filter out weak breakouts and choppy markets
when combined with trend-following signals.
"""

from __future__ import annotations

import pandas as pd


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """Apply Wilder's smoothing (RMA) to a series."""
    return series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def average_directional_index(
    df: pd.DataFrame,
    period: int = 14,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Return ADX, +DI, -DI and ATR series.

    The implementation follows the classic Wilder recipe but uses pandas
    ``ewm`` for the smoothing step, which is equivalent when ``alpha=1/period``.
    ADX/DI values are scaled 0-100.  The first ``period`` rows are NaN.
    """
    high = df[high_col]
    low = df[low_col]
    close = df[close_col]

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr = _wilder_smooth(true_range, period)
    smoothed_plus = _wilder_smooth(plus_dm, period)
    smoothed_minus = _wilder_smooth(minus_dm, period)

    di_plus = (100 * smoothed_plus / atr).fillna(0.0)
    di_minus = (100 * smoothed_minus / atr).fillna(0.0)

    dx = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus)).fillna(0.0)
    adx = _wilder_smooth(dx, period).fillna(0.0)

    return adx, di_plus, di_minus, atr


def add_trend_strength_features(
    df: pd.DataFrame,
    period: int = 14,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> pd.DataFrame:
    """Add trend-strength columns to ``df``.

    Adds:
    - ``adx``: average directional index (0-100).
    - ``di_plus``: positive directional indicator.
    - ``di_minus``: negative directional indicator.
    - ``atr``: average true range.
    """
    result = df.copy()
    adx, di_plus, di_minus, atr = average_directional_index(
        result, period=period, high_col=high_col, low_col=low_col, close_col=close_col
    )
    result["adx"] = adx
    result["di_plus"] = di_plus
    result["di_minus"] = di_minus
    result["atr"] = atr
    return result
