"""Tests for KNN similarity search over state vectors."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.knn_search import knn_search
from src.scenario_engine.state_vector import compute_state_vector


def _make_state_df(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )
    return compute_state_vector(df)


def test_knn_search_returns_requested_number_of_neighbors():
    df = _make_state_df(150)
    results = knn_search(df, n_neighbors=8)
    assert len(results) == 8


def test_knn_search_distances_are_sorted():
    df = _make_state_df(150)
    results = knn_search(df, n_neighbors=10)
    distances = [r["distance"] for r in results]
    assert distances == sorted(distances)


def test_knn_search_excludes_query_index():
    df = _make_state_df(150)
    query_index = len(df) - 10
    results = knn_search(df, query_index=query_index, n_neighbors=10)
    neighbor_indices = {r["neighbor_index"] for r in results}
    assert query_index not in neighbor_indices


def test_knn_search_result_has_future_returns_and_timestamps():
    df = _make_state_df(150)
    results = knn_search(df, n_neighbors=5)
    assert all("future_return_5" in r for r in results)
    assert all("future_return_7" in r for r in results)
    assert all("neighbor_timestamp" in r for r in results)


def test_knn_search_weighted_euclidean_uses_schema_weights_by_default():
    df = _make_state_df(150)
    results = knn_search(df, n_neighbors=5, metric="weighted_euclidean")
    assert len(results) == 5
    assert all("distance" in r for r in results)


def test_knn_search_query_index_out_of_bounds():
    df = _make_state_df(50)
    with pytest.raises(ValueError, match="out of bounds"):
        knn_search(df, query_index=100)
