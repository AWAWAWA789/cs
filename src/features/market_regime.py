"""Market-regime classification without volume data.

The regime is derived from price structure alone: a slower swing/trend lookback
classifies the market as uptrend, downtrend or choppy.  This can be used as a
filter to reduce long entries during sustained bear markets.
"""

from __future__ import annotations

import pandas as pd

from src.features.structure import add_structure_features


def classify_market_regime(
    df: pd.DataFrame,
    swing_order: int = 3,
    confirmations: int = 3,
    high_col: str = "high",
    low_col: str = "low",
) -> pd.Series:
    """Return a regime label for each bar based on a slow price structure.

    Labels:
    - ``uptrend``: higher swing highs and higher swing lows.
    - ``downtrend``: lower swing highs and lower swing lows.
    - ``choppy``: anything else or insufficient swing points.

    The slower parameters (larger ``swing_order`` and ``confirmations``) make
    this a long-term regime indicator rather than an entry signal.
    """
    structure = add_structure_features(
        df,
        swing_order=swing_order,
        confirmations=confirmations,
        high_col=high_col,
        low_col=low_col,
    )
    trend = structure["trend"]
    return trend.map({1: "uptrend", -1: "downtrend", 0: "choppy"}).astype("string")


def add_market_regime_feature(
    df: pd.DataFrame,
    swing_order: int = 3,
    confirmations: int = 3,
    high_col: str = "high",
    low_col: str = "low",
) -> pd.DataFrame:
    """Add a ``market_regime`` column to ``df``."""
    result = df.copy()
    result["market_regime"] = classify_market_regime(
        result,
        swing_order=swing_order,
        confirmations=confirmations,
        high_col=high_col,
        low_col=low_col,
    )
    return result
