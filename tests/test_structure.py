"""Tests for price structure confirmation helpers."""

import pandas as pd

from src.features.structure import (
    add_structure_features,
    breakout_follow_through,
    trend_direction,
)


def _df(highs, lows):
    return pd.DataFrame({"high": highs, "low": lows, "close": lows})


def test_trend_direction_uptrend():
    # Higher highs and higher lows: clear uptrend.
    highs = [1, 2, 3, 2, 4, 3, 5]
    lows = [0, 1, 2, 1, 3, 2, 4]
    df = _df(highs, lows)
    df["swing_high"] = [False, False, True, False, True, False, True]
    df["swing_low"] = [True, False, False, True, False, True, False]

    trend = trend_direction(df)
    assert trend.iloc[-1] == 1


def test_trend_direction_downtrend():
    highs = [5, 4, 3, 4, 2, 3, 1]
    lows = [4, 3, 2, 2.5, 1, 1.5, 0]
    df = _df(highs, lows)
    df["swing_high"] = [True, False, True, False, True, False, True]
    df["swing_low"] = [False, True, False, True, False, True, False]

    trend = trend_direction(df)
    assert trend.iloc[-1] == -1


def test_trend_direction_unclear():
    highs = [3, 4, 3, 4, 3]
    lows = [2, 3, 2, 3, 2]
    df = _df(highs, lows)
    df["swing_high"] = [False, True, False, True, False]
    df["swing_low"] = [True, False, True, False, True]

    trend = trend_direction(df)
    assert trend.iloc[-1] == 0


def test_add_structure_features():
    # Data chosen so that order=1 swing detection yields higher highs/lows.
    highs = [1, 3, 2, 4, 3, 5, 4, 6]
    lows = [0, 2, 1, 3, 2, 4, 3, 5]
    df = _df(highs, lows)

    result = add_structure_features(df, swing_order=1)

    assert "swing_high" in result.columns
    assert "swing_low" in result.columns
    assert "trend" in result.columns
    assert result["trend"].iloc[-1] == 1


def test_breakout_follow_through_bullish():
    df = pd.DataFrame({"close": [99.0, 100.5, 101.0]})
    signal = breakout_follow_through(df, level=100.0, direction="bullish")

    assert signal.tolist() == [False, True, False]


def test_breakout_follow_through_bearish():
    df = pd.DataFrame({"close": [101.0, 99.5, 98.0]})
    signal = breakout_follow_through(df, level=100.0, direction="bearish")

    assert signal.tolist() == [False, True, False]
