"""Multi-timeframe alignment helpers.

Provides a simple way to use a higher timeframe trend to filter lower timeframe
signals. The higher timeframe trend is forward-filled onto every lower timeframe
bar whose timestamp falls within the higher timeframe candle.
"""

from __future__ import annotations

import pandas as pd

from src.features.structure import add_structure_features


def align_higher_trend(
    lower_df: pd.DataFrame,
    higher_df: pd.DataFrame,
    higher_trend_col: str = "trend",
    timestamp_col: str = "timestamp",
) -> pd.Series:
    """Return a Series with the higher timeframe trend mapped to each lower bar.

    For each lower timeframe row, the trend is taken from the most recent higher
    timeframe bar whose timestamp is less than or equal to the lower bar's
    timestamp. NaN values are filled forward.
    """
    if higher_df.empty:
        return pd.Series(pd.NA, index=lower_df.index, dtype=object)

    # Use pandas Series to preserve timezone information during comparison.
    higher_ts = pd.Series(higher_df[timestamp_col])
    higher_trend = higher_df[higher_trend_col].values

    mapped: list[int | None] = []
    for lower_time in lower_df[timestamp_col]:
        # Find the latest higher bar that started at or before the lower bar.
        idx = int((higher_ts <= lower_time).sum()) - 1
        if idx >= 0:
            mapped.append(int(higher_trend[idx]))
        else:
            mapped.append(None)

    return pd.Series(mapped, index=lower_df.index).ffill()


def add_higher_trend(
    lower_df: pd.DataFrame,
    higher_df: pd.DataFrame,
    col_name: str = "higher_trend",
    **kwargs,
) -> pd.DataFrame:
    """Add ``col_name`` to ``lower_df`` with the aligned higher timeframe trend.

    Args:
        lower_df: Lower timeframe OHLC DataFrame.
        higher_df: Higher timeframe OHLC DataFrame. Trend labels are computed
            with ``add_structure_features`` if ``trend`` is not present.
        col_name: Name of the column to add.
        **kwargs: Passed to ``add_structure_features`` when computing trend.

    Returns:
        A copy of ``lower_df`` with the additional trend column.
    """
    result = lower_df.copy()
    if "trend" not in higher_df.columns:
        higher_df = add_structure_features(higher_df, **kwargs)
    result[col_name] = align_higher_trend(result, higher_df)
    return result
