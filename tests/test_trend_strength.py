"""Tests for trend-strength features."""

from __future__ import annotations

import pandas as pd

from src.features.trend_strength import (
    add_trend_strength_features,
    average_directional_index,
)


def test_adx_is_zero_for_flat_prices():
    df = pd.DataFrame(
        {
            "open": [100.0] * 20,
            "high": [100.0] * 20,
            "low": [100.0] * 20,
            "close": [100.0] * 20,
        }
    )
    adx, di_plus, di_minus, atr = average_directional_index(df, period=14)
    assert adx.iloc[-1] == 0
    assert di_plus.iloc[-1] == 0
    assert di_minus.iloc[-1] == 0
    assert atr.iloc[-1] == 0


def test_adx_rises_in_strong_uptrend():
    df = pd.DataFrame(
        {
            "open": list(range(1, 31)),
            "high": list(range(2, 32)),
            "low": list(range(0, 30)),
            "close": list(range(2, 32)),
        },
        dtype=float,
    )
    adx, di_plus, di_minus, atr = average_directional_index(df, period=14)
    # In a steady rising market DI+ should dominate and ADX should be elevated.
    assert di_plus.iloc[-1] > di_minus.iloc[-1]
    assert adx.iloc[-1] > 20
    assert atr.iloc[-1] > 0


def test_add_trend_strength_features_adds_columns():
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [2.0, 3.0, 4.0],
            "low": [0.5, 1.5, 2.5],
            "close": [1.5, 2.5, 3.5],
        }
    )
    result = add_trend_strength_features(df, period=2)
    assert "adx" in result.columns
    assert "di_plus" in result.columns
    assert "di_minus" in result.columns
    assert "atr" in result.columns
