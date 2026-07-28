"""Tests for state-vector construction."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.state_vector import (
    compute_state_vector,
    get_state_columns,
    get_state_weights,
    load_state_vector_schema,
)


def _make_ohlc(n: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))
    return pd.DataFrame(
        {
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )


def test_schema_loads_and_has_expected_fields():
    schema = load_state_vector_schema()
    assert "fields" in schema
    cols = get_state_columns(schema)
    assert "adx_normalized" in cols
    assert "signal_quality" in cols
    assert "price_vs_sma50" in cols


def test_state_weights_match_schema_order():
    schema = load_state_vector_schema()
    cols = get_state_columns(schema)
    weights = get_state_weights(schema)
    assert len(weights) == len(cols)
    assert all(w > 0 for w in weights)


def test_compute_state_vector_adds_all_columns():
    df = _make_ohlc(150)
    result = compute_state_vector(df)
    cols = get_state_columns()
    for col in cols:
        assert col in result.columns


def test_compute_state_vector_no_nans():
    df = _make_ohlc(150)
    result = compute_state_vector(df)
    cols = get_state_columns()
    assert result[cols].isna().sum().sum() == 0


def test_compute_state_vector_no_volume_column():
    df = _make_ohlc(100)
    result = compute_state_vector(df)
    assert "volume" not in result.columns


def test_compute_state_vector_invalid_input():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="open, high, low and close"):
        compute_state_vector(df)


def test_state_vector_ranges_are_sensible():
    df = _make_ohlc(200)
    result = compute_state_vector(df)
    assert result["adx_normalized"].between(0.0, 1.0).all()
    assert result["bb_position"].between(0.0, 1.0).all()
    assert result["swing_position_ratio"].between(0.0, 1.0).all()
    assert result["signal_quality"].between(0.0, 1.0).all()
    assert result["trend_quality"].between(0.0, 1.0).all()
