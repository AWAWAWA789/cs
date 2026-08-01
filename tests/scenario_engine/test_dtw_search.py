"""Tests for DTW shape-aligned similarity search."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.scenario_engine.dtw_search import dtw_distance, dtw_search


def _make_price_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(13)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "close": price,
        }
    )


def test_dtw_distance_of_identical_series_is_zero():
    series = np.sin(np.linspace(0, 4 * np.pi, 30))
    assert dtw_distance(series, series) == 0.0


def test_dtw_search_returns_requested_number():
    df = _make_price_df(120)
    results = dtw_search(df, window=20, n_neighbors=5)
    assert len(results) == 5


def test_dtw_search_distances_sorted_and_have_returns():
    df = _make_price_df(120)
    results = dtw_search(df, window=20, n_neighbors=5)
    distances = [r["distance"] for r in results]
    assert distances == sorted(distances)
    assert all(r["future_return_5"] is not None for r in results)
    assert all(r["future_return_7"] is not None for r in results)


def test_dtw_search_is_robust_to_small_offset():
    """A shape shifted by 1-3 bars should be ranked near the top."""
    rng = np.random.default_rng(99)
    n = 120
    base = np.sin(np.linspace(0, 6 * np.pi, n)) + rng.normal(0.0, 0.05, n)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "close": 100.0 + base * 5.0,
        }
    )
    # The query window is the last 20 bars. Embed an earlier shifted copy.
    offset = 2
    query_start = n - 20
    shifted = df["close"].to_numpy().copy()
    shifted[30:50] = df["close"].iloc[query_start - offset : query_start - offset + 20].to_numpy()
    df["close"] = shifted

    results = dtw_search(df, window=20, n_neighbors=10, radius=3)
    top_starts = {r["candidate_start"] for r in results}
    # The shifted copy starting at 30 should be among the top matches.
    assert 30 in top_starts


def test_dtw_search_excludes_overlapping_query_window():
    df = _make_price_df(120)
    results = dtw_search(df, window=20, n_neighbors=10)
    query_start = len(df) - 20
    for r in results:
        assert not (r["candidate_start"] <= query_start <= r["candidate_end"])
