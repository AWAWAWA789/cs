"""Signal-quality scoring without volume data.

These helpers score pullback, Smart Money and trend-following signals along
three dimensions:

1. **Trend consistency** – ADX magnitude and +DI > -DI alignment.
2. **Structure resonance** – proximity to the recent swing low (for longs).
3. **Confluence** – whether multiple independent concepts fire on the same bar.

A low composite score indicates a marginal setup that should be filtered out.
"""

from __future__ import annotations

import pandas as pd

from src.features.trend_strength import add_trend_strength_features


def _trend_quality(df: pd.DataFrame) -> pd.Series:
    """Return a 0-1 score based on trend strength and direction."""
    adx = df.get("adx")
    if adx is None:
        df = add_trend_strength_features(df)
        adx = df["adx"]

    di_plus = df.get("di_plus", pd.Series(0.0, index=df.index))
    di_minus = df.get("di_minus", pd.Series(0.0, index=df.index))

    # Normalize ADX to [0, 1] using a 50-point scale.
    adx_score = (adx / 50.0).clip(lower=0.0, upper=1.0)
    di_aligned = (di_plus > di_minus).astype(float)

    return (adx_score * 0.6 + di_aligned * 0.4).fillna(0.0)


def _structure_resonance(
    df: pd.DataFrame,
    swing_low_col: str = "signal_swing_low",
    price_col: str = "close",
    buffer: float = 0.03,
) -> pd.Series:
    """Return a 0-1 score based on proximity to the signal's swing anchor.

    For long signals the anchor is the recent swing low.  A score of 1 means
    price is exactly at the anchor; it decays linearly to 0 at ``buffer`` away.
    """
    anchor = df[swing_low_col]
    price = df[price_col]
    distance = (price - anchor).abs() / anchor
    return (1.0 - (distance / buffer)).clip(lower=0.0, upper=1.0).fillna(0.0)


def _confluence_quality(df: pd.DataFrame) -> pd.Series:
    """Return a 0-1 score based on how many independent concepts align.

    Combines pullback/Fibonacci, Smart Money and trend-following concepts into
    a simple count and normalizes it.
    """
    score = pd.Series(0.0, index=df.index)

    # Pullback concept: a Fibonacci-aligned bar with a bullish candlestick pattern.
    has_fib = df.get("near_fib") is not None and df.get("has_bullish_pattern") is not None
    if has_fib:
        score += (df["near_fib"] & df["has_bullish_pattern"]).astype(float)

    # Smart Money concepts.
    for col in ("liquidity_grab", "order_block", "fair_value_gap"):
        if col in df.columns:
            score += df[col].astype(float)

    # Trend-following concept.
    has_breakout = (
        df.get("breakout_follow_through") is not None
        or df.get("breakout_pullback") is not None
        or df.get("higher_high_breakout") is not None
    )
    if has_breakout:
        breakout_signal = (
            df.get("breakout_follow_through", False)
            | df.get("breakout_pullback", False)
            | df.get("higher_high_breakout", False)
        )
        score += breakout_signal.astype(float)

    # Normalize by the maximum possible independent concepts (3).
    return (score / 3.0).clip(upper=1.0).fillna(0.0)


def add_signal_quality_features(
    df: pd.DataFrame,
    trend_weight: float = 0.4,
    structure_weight: float = 0.4,
    confluence_weight: float = 0.2,
    swing_low_col: str = "signal_swing_low",
    price_col: str = "close",
    resonance_buffer: float = 0.03,
) -> pd.DataFrame:
    """Add a ``signal_quality`` column to ``df``.

    The composite score ranges from 0 (low quality) to 1 (high quality) and is
    computed only for bars where ``signal_long`` is True.  Non-signal bars
    receive a score of 0.

    Args:
        df: DataFrame containing signal columns.
        trend_weight: Weight for trend-consistency component.
        structure_weight: Weight for structure-resonance component.
        confluence_weight: Weight for confluence component.
        swing_low_col: Column with the swing-low anchor price.
        price_col: Price column used for resonance calculation.
        resonance_buffer: Maximum relative distance that still scores above 0.
    """
    result = df.copy()
    result = add_trend_strength_features(result)

    trend_score = _trend_quality(result)
    structure_score = _structure_resonance(
        result, swing_low_col=swing_low_col, price_col=price_col, buffer=resonance_buffer
    )
    confluence_score = _confluence_quality(result)

    total_weight = trend_weight + structure_weight + confluence_weight
    composite = (
        trend_weight * trend_score
        + structure_weight * structure_score
        + confluence_weight * confluence_score
    ) / total_weight

    # Only score actual signal bars; everything else is 0.
    signal_mask = result.get("signal_long", pd.Series(False, index=result.index))
    result["signal_quality"] = composite.where(signal_mask, 0.0).fillna(0.0)
    return result


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
