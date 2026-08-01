"""Tests for buy-and-hold benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.buy_and_hold import compute_buy_and_hold


def test_buy_and_hold_basic() -> None:
    n = 10
    price = 100.0 * np.ones(n)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        "open": price,
        "high": price,
        "low": price,
        "close": price * (1 + np.arange(n) * 0.01),
    })
    result = compute_buy_and_hold(df)
    assert result["total_return"] == pytest.approx(0.09, abs=1e-6)
    assert result["max_drawdown"] == pytest.approx(0.0, abs=1e-6)
    assert "sharpe" in result
    assert result["start_price"] == pytest.approx(100.0, abs=1e-6)
    assert result["end_price"] == pytest.approx(109.0, abs=1e-6)


def test_buy_and_hold_empty_or_single_row() -> None:
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01"]).tz_localize("UTC"),
        "open": [100.0],
        "high": [101.0],
        "low": [99.0],
        "close": [100.0],
    })
    result = compute_buy_and_hold(df)
    assert result["total_return"] == 0.0
