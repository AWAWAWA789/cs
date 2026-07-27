"""Tests for candlestick pattern recognition."""

import pandas as pd

from src.features.candlestick import (
    identify_candlestick_patterns,
    identify_engulfing,
    identify_pin_bar,
)


def _df(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


def test_bullish_pin_bar():
    # Small body at the high, long lower wick, minimal upper wick.
    df = _df([[100.0, 100.5, 96.0, 100.5]])
    result = identify_pin_bar(df)

    assert result["pin_bar_bull"].iloc[0] == True
    assert result["pin_bar_bear"].iloc[0] == False


def test_bearish_pin_bar():
    # Small body at the low, long upper wick, minimal lower wick.
    df = _df([[100.0, 104.0, 99.5, 99.5]])
    result = identify_pin_bar(df)

    assert result["pin_bar_bear"].iloc[0] == True
    assert result["pin_bar_bull"].iloc[0] == False


def test_no_pin_bar_when_body_too_large():
    df = _df([[100.0, 102.0, 99.0, 101.5]])
    result = identify_pin_bar(df)

    assert not result["pin_bar_bull"].iloc[0]
    assert not result["pin_bar_bear"].iloc[0]


def test_bullish_engulfing():
    df = _df(
        [
            [100.0, 100.5, 99.5, 99.0],  # bearish previous
            [98.5, 100.8, 98.0, 100.5],  # bullish engulfing
        ]
    )
    result = identify_engulfing(df)

    assert result["engulfing_bull"].iloc[0] == False
    assert result["engulfing_bull"].iloc[1] == True
    assert result["engulfing_bear"].iloc[1] == False


def test_bearish_engulfing():
    df = _df(
        [
            [100.0, 100.5, 99.5, 101.0],  # bullish previous
            [101.5, 101.8, 99.0, 99.5],  # bearish engulfing
        ]
    )
    result = identify_engulfing(df)

    assert result["engulfing_bear"].iloc[0] == False
    assert result["engulfing_bear"].iloc[1] == True
    assert result["engulfing_bull"].iloc[1] == False


def test_combined_patterns():
    df = _df(
        [
            [100.0, 100.5, 99.5, 99.0],
            [98.5, 100.8, 98.0, 100.5],
        ]
    )
    result = identify_candlestick_patterns(df)

    assert "pin_bar_bull" in result.columns
    assert "engulfing_bull" in result.columns
    assert result["engulfing_bull"].iloc[1] == True
