"""Tests for Fibonacci level helpers."""

import pytest

from src.features.fibonacci import (
    extension_levels,
    is_near_level,
    nearest_level,
    retracement_levels,
)


def test_retracement_levels_basic():
    levels = retracement_levels(low=100.0, high=200.0)

    assert levels["0.0"] == pytest.approx(200.0)
    assert levels["0.5"] == pytest.approx(150.0)
    assert levels["0.618"] == pytest.approx(138.2, rel=1e-3)
    assert levels["1.0"] == pytest.approx(100.0)


def test_extension_levels_basic():
    levels = extension_levels(low=100.0, high=200.0)

    assert levels["1.0"] == pytest.approx(200.0)
    assert levels["1.272"] == pytest.approx(227.2, rel=1e-3)
    assert levels["1.618"] == pytest.approx(261.8, rel=1e-3)


def test_nearest_level():
    levels = retracement_levels(low=100.0, high=200.0)
    name, distance = nearest_level(149.0, levels)

    assert name == "0.5"
    assert distance == pytest.approx(1.0)


def test_nearest_level_empty_raises():
    with pytest.raises(ValueError, match="levels must not be empty"):
        nearest_level(100.0, {})


def test_is_near_level_detects_proximity():
    levels = retracement_levels(low=100.0, high=200.0)

    near, name, distance = is_near_level(150.5, levels, tolerance=0.02)
    assert near is True
    assert name == "0.5"
    assert distance == pytest.approx(0.5)


def test_is_near_level_respects_target_subset():
    levels = retracement_levels(low=100.0, high=200.0)

    near, name, _ = is_near_level(
        138.5, levels, tolerance=0.05, target_levels=("0.618", "0.786")
    )
    assert near is True
    assert name == "0.618"


def test_is_near_level_false_when_far():
    levels = retracement_levels(low=100.0, high=200.0)

    near, name, _ = is_near_level(180.0, levels, tolerance=0.001)
    assert near is False
    assert name is None
