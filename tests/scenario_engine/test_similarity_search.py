"""Tests for the unified similarity-search entry point."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.similarity_search import find_similar_states


def _make_ohlc(n: int = 150) -> pd.DataFrame:
    rng = np.random.default_rng(33)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )


def test_find_similar_states_knn():
    df = _make_ohlc(150)
    results = find_similar_states(df, method="knn", n_neighbors=5)
    assert isinstance(results, list)
    assert len(results) == 5
    assert all("distance" in r and "future_return_5" in r for r in results)


def test_find_similar_states_dtw():
    df = _make_ohlc(150)
    results = find_similar_states(df, method="dtw", n_neighbors=5, window=20)
    assert isinstance(results, list)
    assert len(results) == 5
    assert all("candidate_start" in r and "future_return_5" in r for r in results)


def test_find_similar_states_cluster():
    df = _make_ohlc(150)
    result = find_similar_states(df, method="cluster", n_neighbors=3)
    assert isinstance(result, dict)
    assert result["n_clusters"] == 3
    assert "labels" in result


def test_find_similar_states_unsupported_method():
    df = _make_ohlc(50)
    with pytest.raises(ValueError, match="method must be one of"):
        find_similar_states(df, method="unknown")
