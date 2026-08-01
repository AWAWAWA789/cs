from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.performance import compare_strategy_vs_benchmark


def _make_ohlc_with_signal(n: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.005, n)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price,
            "high": price * 1.02,
            "low": price * 0.98,
            "close": price,
        }
    )
    # Force one long signal near the start so the strategy participates.
    df["signal_long"] = False
    df["signal_swing_low"] = df["low"]
    df["signal_swing_high"] = df["high"]
    df.loc[5, "signal_long"] = True
    return df


def test_compare_returns_required_fields():
    df = _make_ohlc_with_signal()
    result = compare_strategy_vs_benchmark(df)
    assert "strategy" in result
    assert "benchmark" in result
    assert "excess_return" in result
    assert "beat_buy_and_hold" in result
    assert isinstance(result["beat_buy_and_hold"], bool)


def test_compare_with_signal_generation():
    rng = np.random.default_rng(18)
    n = 100
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price,
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )
    result = compare_strategy_vs_benchmark(df)
    assert "strategy" in result
    assert "benchmark" in result
    assert isinstance(result["excess_return"], float)
