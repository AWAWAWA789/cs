"""Tests for scenario-engine normalizers and distance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.normalization import (
    compute_distance,
    cosine_distance,
    euclidean_distance,
    min_max_scale,
    robust_scale,
    weighted_euclidean_distance,
    z_score,
)


def test_z_score_zero_mean_unit_std():
    arr = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    scaled = z_score(arr)
    np.testing.assert_allclose(np.mean(scaled, axis=0), 0.0, atol=1e-12)
    np.testing.assert_allclose(np.std(scaled, axis=0), 1.0, atol=1e-12)


def test_z_score_one_d():
    series = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    scaled = z_score(series)
    assert scaled.shape == (5,)
    np.testing.assert_allclose(np.mean(scaled), 0.0, atol=1e-12)


def test_min_max_scale_range():
    arr = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])
    scaled = min_max_scale(arr)
    np.testing.assert_allclose(np.min(scaled, axis=0), 0.0)
    np.testing.assert_allclose(np.max(scaled, axis=0), 1.0)


def test_min_max_scale_custom_range():
    series = np.array([0.0, 5.0, 10.0])
    scaled = min_max_scale(series, feature_range=(-1.0, 1.0))
    np.testing.assert_allclose(np.min(scaled), -1.0)
    np.testing.assert_allclose(np.max(scaled), 1.0)


def test_robust_scale_median_zero():
    arr = np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 100.0], [4.0, 4.0], [5.0, 5.0]])
    scaled = robust_scale(arr)
    # Median row (3, 4) should be mapped close to zero.
    assert abs(scaled[2, 0]) < 1e-9


def test_euclidean_distance_identical_vectors():
    assert euclidean_distance([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_euclidean_distance_known_value():
    assert euclidean_distance([0.0, 0.0], [3.0, 4.0]) == 5.0


def test_weighted_euclidean_with_equal_weights_scales_by_norm():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 0.0, 2.0])
    weights = np.array([1.0, 1.0, 1.0])
    # Equal weights are normalised to sum to 1, so distance = euclidean / sqrt(3).
    assert weighted_euclidean_distance(a, b, weights) == pytest.approx(
        euclidean_distance(a, b) / np.sqrt(3)
    )


def test_weighted_euclidean_higher_weight_increases_influence():
    a = np.array([0.0, 0.0])
    b = np.array([1.0, 10.0])
    low_weight = weighted_euclidean_distance(a, b, [1.0, 0.0])
    high_weight = weighted_euclidean_distance(a, b, [0.0, 1.0])
    assert low_weight < high_weight


def test_cosine_distance_identical():
    assert cosine_distance([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 0.0


def test_cosine_distance_opposite():
    assert cosine_distance([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(2.0)


def test_compute_distance_dispatcher():
    assert compute_distance([0.0, 0.0], [3.0, 4.0], metric="euclidean") == 5.0
    with pytest.raises(ValueError, match="Unsupported metric"):
        compute_distance([0.0], [1.0], metric="unknown")


def test_normalizers_accept_pandas():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10.0, 20.0, 30.0]})
    z = z_score(df)
    assert z.shape == (3, 2)
    assert np.isfinite(z).all()
