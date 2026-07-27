"""Smart Money price-action features without volume data.

Implements a minimal but usable set of Smart Money concepts:
- Liquidity Grab (stop hunt)
- Order Block (OB)
- Fair Value Gap (FVG)

All features are computed bar-by-bar using only OHLC data and swing points.
"""

from __future__ import annotations

import pandas as pd


def liquidity_grab(
    df: pd.DataFrame,
    swing_low_col: str = "swing_low",
    low_col: str = "low",
    close_col: str = "close",
    open_col: str = "open",
    buffer: float = 0.005,
) -> pd.Series:
    """Return True on bars with a bullish liquidity grab.

    A bullish liquidity grab occurs when price briefly trades at or below a
    recent swing low but the candle closes back above it, suggesting that
    sell-side liquidity was swept before a reversal.
    """
    # Most recent swing low price observed up to and including the current bar.
    swing_low_prices = df[low_col].where(df[swing_low_col]).ffill()

    low = df[low_col]
    close = df[close_col]
    open_ = df[open_col]
    bullish = close > open_

    # Price must touch or break the recent swing low (with a small buffer).
    swept = low <= swing_low_prices * (1 + buffer)
    # The candle must recover and close above the swing low.
    recovered = close > swing_low_prices

    return bullish & swept & recovered


def order_block(
    df: pd.DataFrame,
    swing_low_col: str = "swing_low",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    open_col: str = "open",
) -> pd.Series:
    """Return True when price revisits the zone of the last bearish candle
    before a swing low.

    This is a simplified Order Block model: the last down candle immediately
    preceding a swing low defines a demand zone. A revisit occurs when the
    current close falls inside that zone.
    """
    result = pd.Series(False, index=df.index)
    swing_low_indices = df.index[df[swing_low_col]].tolist()

    for swing_idx in swing_low_indices:
        # Find the most recent bearish candle before the swing low.
        pos = df.index.get_loc(swing_idx)
        ob_idx = None
        for i in range(pos - 1, -1, -1):
            if df[close_col].iloc[i] < df[open_col].iloc[i]:
                ob_idx = i
                break
        if ob_idx is None:
            continue

        ob_low = min(df[open_col].iloc[ob_idx], df[close_col].iloc[ob_idx])
        ob_high = max(df[open_col].iloc[ob_idx], df[close_col].iloc[ob_idx])

        # Mark all later bars whose close falls inside the OB zone as a revisit.
        for j in range(ob_idx + 1, len(df)):
            close = df[close_col].iloc[j]
            if ob_low <= close <= ob_high:
                result.iloc[j] = True

    return result


def fair_value_gap(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    open_col: str = "open",
) -> pd.Series:
    """Return True on bars that revisit a bullish Fair Value Gap.

    A bullish FVG is a three-candle sequence where the low of the middle candle
    is above the high of the first candle, creating an unfilled gap. The signal
    fires when the current candle's close falls back into the gap.
    """
    result = pd.Series(False, index=df.index)
    if len(df) < 3:
        return result

    high = df[high_col]
    low = df[low_col]
    close = df[close_col]

    for i in range(2, len(df)):
        gap_low = low.iloc[i - 1]
        gap_high = high.iloc[i - 2]
        if gap_low > gap_high:
            # A bullish gap exists between candle i-2 and candle i-1.
            for j in range(i, len(df)):
                if gap_high <= close.iloc[j] <= gap_low:
                    result.iloc[j] = True

    return result


def add_smart_money_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add Smart Money feature columns to ``df``.

    Adds:
    - ``liquidity_grab``: boolean bullish liquidity grab signal.
    - ``order_block``: boolean Order Block revisit signal.
    - ``fair_value_gap``: boolean FVG revisit signal.
    """
    result = df.copy()
    result["liquidity_grab"] = liquidity_grab(result)
    result["order_block"] = order_block(result)
    result["fair_value_gap"] = fair_value_gap(result)
    return result
