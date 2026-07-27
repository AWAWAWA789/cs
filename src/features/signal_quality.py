"""Signal-quality filters without volume data.

These helpers add structure-based resonance checks to Smart Money and other
price-action signals, reducing low-probability entries that occur far from key
support/resistance levels.
"""

from __future__ import annotations

import pandas as pd


def structure_resonance(
    df: pd.DataFrame,
    anchor_col: str = "signal_swing_low",
    price_col: str = "close",
    buffer: float = 0.03,
) -> pd.Series:
    """Return True when ``price_col`` is within ``buffer`` of ``anchor_col``.

    For long signals the anchor is typically the recent swing low; for short
    signals it would be the recent swing high.  A ``buffer`` of 0.03 means the
    price must be within ±3% of the anchor level.
    """
    anchor = df[anchor_col]
    price = df[price_col]
    return (price - anchor).abs() / anchor <= buffer
