"""Tests for the scenario generator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.scenario_generator import (
    _compute_probability_threshold,
    _select_high_probability_scenarios,
    generate_scenarios,
)


def _make_ohlc(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )


def test_compute_probability_threshold_dynamic_floor():
    probs = [0.5, 0.3, 0.15, 0.05]
    threshold = _compute_probability_threshold(probs)
    # relative floor = max(1/4, 0.10) = 0.25
    # dynamic floor = 0.15 * 0.5 = 0.075
    # absolute floor = 0.05
    assert threshold == pytest.approx(0.25, abs=1e-6)


def test_select_high_probability_scenarios_enforces_min_and_max():
    scenarios = [
        {"scenario_key": "bullish_continuation", "probability": 0.5, "direction": 1},
        {"scenario_key": "bearish_reversal", "probability": 0.3, "direction": -1},
        {"scenario_key": "dip_then_rise", "probability": 0.15, "direction": 1},
        {"scenario_key": "range_bound", "probability": 0.05, "direction": 0},
    ]
    selected = _select_high_probability_scenarios(scenarios)
    assert 2 <= len(selected) <= 4
    total = sum(s["probability"] for s in selected)
    assert abs(total - 1.0) < 1e-6


def test_generate_scenarios_returns_two_to_four():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    scenarios = result["scenarios"]
    assert 2 <= len(scenarios) <= 4


def test_scenario_probabilities_sum_to_one():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    total = sum(s["probability"] for s in result["scenarios"])
    assert abs(total - 1.0) < 0.01


def test_scenarios_have_required_fields():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    for s in result["scenarios"]:
        for key in (
            "name",
            "probability",
            "direction",
            "support",
            "resistance",
            "target",
            "stop_loss",
            "position_size",
            "wave_sketch",
        ):
            assert key in s


def test_multi_timeframe_input_generates_scenarios():
    df = _make_ohlc(250)
    result = generate_scenarios(
        {
            "1day": df,
            "4hour": df.iloc[::4].reset_index(drop=True),
            "1hour": df,
        }
    )
    assert 2 <= len(result["scenarios"]) <= 4
    assert result["per_period"]


def test_position_size_is_within_bounds():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    for s in result["scenarios"]:
        assert 0.0 <= s["position_size"] <= 1.0


def test_generate_scenarios_uses_adaptive_temperature():
    df = _make_ohlc(250)
    result = generate_scenarios(
        {"1day": df},
        sub_index="test_glove",
        use_adaptive_temperature=True,
    )
    assert 2 <= len(result["scenarios"]) <= 4
