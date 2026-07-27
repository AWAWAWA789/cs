"""Tests for trend-following features."""

from __future__ import annotations

import pandas as pd

from src.features.trend_following import (
    add_trend_following_features,
    breakout_with_follow_through,
    higher_high_breakout,
)


def test_breakout_with_follow_through_detects_breakout():
    """A bullish candle that breaks and closes above the recent swing high."""
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 2.5, 2.4],
            "high": [1.2, 2.2, 1.8, 2.8, 2.6],
            "low": [0.8, 1.8, 1.4, 2.2, 2.3],
            "close": [1.0, 2.0, 1.5, 2.7, 2.5],
        }
    )
    # Bar 1 is a swing high (high=2.2). Bar 3 breaks above it.
    df["swing_high"] = [False, True, False, False, False]

    result = breakout_with_follow_through(df)
    assert result.iloc[3]
    assert not result.iloc[4]


def test_breakout_ignores_bearish_bar():
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 2.7],
            "high": [1.2, 2.2, 1.8, 2.8],
            "low": [0.8, 1.8, 1.4, 2.2],
            "close": [1.0, 2.0, 1.5, 2.5],
        }
    )
    df["swing_high"] = [False, True, False, False]

    result = breakout_with_follow_through(df)
    assert not result.iloc[3]


def test_breakout_ignores_already_extended_price():
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 2.6, 2.7],
            "high": [1.2, 2.2, 1.8, 2.8, 2.9],
            "low": [0.8, 1.8, 1.4, 2.5, 2.6],
            "close": [1.0, 2.0, 1.5, 2.7, 2.8],
        }
    )
    df["swing_high"] = [False, True, False, False, False]

    result = breakout_with_follow_through(df)
    assert result.iloc[3]
    assert not result.iloc[4]


def test_higher_high_breakout_requires_multiple_swing_highs():
    df = pd.DataFrame(
        {
            "open": [1.0, 1.5, 2.0, 2.2, 2.5, 2.7, 3.0],
            "high": [1.2, 1.7, 2.2, 2.3, 2.7, 2.8, 3.2],
            "low": [0.8, 1.3, 1.8, 2.0, 2.3, 2.5, 2.8],
            "close": [1.0, 1.5, 2.0, 2.2, 2.5, 2.7, 3.1],
        }
    )
    df["swing_high"] = [False, True, False, False, True, False, False]

    result = higher_high_breakout(df, lookback=2)
    # Bar 6 breaks above the two previous swing highs (1.7 and 2.7) on a bullish bar.
    assert result.iloc[6]


def test_add_trend_following_features_adds_columns():
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 2.5, 2.4],
            "high": [1.2, 2.2, 1.8, 2.8, 2.6],
            "low": [0.8, 1.8, 1.4, 2.2, 2.3],
            "close": [1.0, 2.0, 1.5, 2.7, 2.5],
        }
    )
    df["swing_high"] = [False, True, False, False, False]

    result = add_trend_following_features(df)
    assert "breakout_follow_through" in result.columns
    assert "higher_high_breakout" in result.columns
