"""Tests for K-Means state-vector clustering."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.state_clustering import cluster_states
from src.scenario_engine.state_vector import compute_state_vector


def _make_state_df(n: int = 150) -> pd.DataFrame:
    rng = np.random.default_rng(21)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))
    df = pd.DataFrame(
        {
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )
    return compute_state_vector(df)


def test_cluster_states_returns_expected_keys():
    df = _make_state_df(150)
    result = cluster_states(df, n_clusters=3)
    assert result["n_clusters"] == 3
    assert "labels" in result
    assert "centers" in result
    assert "cluster_sizes" in result
    assert "inertia" in result


def test_cluster_state_labels_aligned_to_df():
    df = _make_state_df(150)
    result = cluster_states(df, n_clusters=3)
    assert len(result["labels"]) == len(df)


def test_cluster_state_sizes_sum_to_valid_count():
    df = _make_state_df(150)
    result = cluster_states(df, n_clusters=3)
    total = sum(result["cluster_sizes"].values())
    assert total == len(result["valid_indices"])


def test_cluster_states_too_many_clusters_raises():
    df = _make_state_df(20)
    with pytest.raises(ValueError, match="Not enough valid state vectors"):
        cluster_states(df, n_clusters=30)
