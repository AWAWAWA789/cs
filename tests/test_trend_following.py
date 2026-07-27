"""Tests for trend-following features."""

from __future__ import annotations

import pandas as pd

from src.features.trend_following import (
    add_trend_following_features,
    breakout_with_follow_through,
    higher_high_breakout,
)
from src.features.trend_strength import add_trend_strength_features


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


def test_trend_strength_filter_removes_weak_breakout():
    """A valid breakout is suppressed when ADX is below the threshold."""
    df = pd.DataFrame(
        {
            "open": [100.0] * 20,
            "high": [100.0] * 20,
            "low": [100.0] * 20,
            "close": [100.0] * 20,
        }
    )
    # Mark an earlier bar as a swing high, then inject a breakout bar after a
    # flat market (ADX ~= 0).
    swing_highs = [False] * 20
    swing_highs[10] = True
    df["swing_high"] = swing_highs
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [100.0, 105.0, 100.0, 105.0]

    unfiltered = add_trend_following_features(df)
    assert unfiltered["breakout_follow_through"].iloc[-1]

    filtered = add_trend_following_features(df, trend_strength_threshold=10.0)
    assert not filtered["breakout_follow_through"].iloc[-1]


def test_trend_strength_filter_keeps_strong_breakout():
    """A breakout in a trending market survives the ADX filter."""
    df = pd.DataFrame(
        {
            "open": list(range(1, 31)),
            "high": list(range(2, 32)),
            "low": list(range(0, 30)),
            "close": list(range(2, 32)),
        },
        dtype=float,
    )
    # Mark the second-to-last bar as a swing high; last bar breaks above it.
    swing_highs = [False] * 30
    swing_highs[-2] = True
    df["swing_high"] = swing_highs

    filtered = add_trend_following_features(df, trend_strength_threshold=20.0)
    assert filtered["breakout_follow_through"].iloc[-1]
