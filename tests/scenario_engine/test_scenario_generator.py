"""Tests for the scenario generator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.scenario_generator import generate_scenarios


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


def test_generate_scenarios_returns_four_to_six():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    scenarios = result["scenarios"]
    assert 4 <= len(scenarios) <= 6


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
    assert 4 <= len(result["scenarios"]) <= 6
    assert result["per_period"]


def test_position_size_is_within_bounds():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    for s in result["scenarios"]:
        assert 0.0 <= s["position_size"] <= 1.0


def test_standard_scenario_names_present():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    names = {s["name"] for s in result["scenarios"]}
    required = {"上涨延续", "下跌反转", "先跌后涨", "区间震荡"}
    assert required.issubset(names)
