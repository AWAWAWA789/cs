"""Tests for the Phase 18 scenario quality validation report."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate_phase18_report import (
    _evaluate_scenario_quality,
    build_phase18_report,
)


def test_evaluate_scenario_quality_flags_oligopoly():
    scenarios = [
        {"probability": 0.97, "direction": 1},
        {"probability": 0.01, "direction": -1},
        {"probability": 0.01, "direction": 0},
        {"probability": 0.01, "direction": 1},
    ]
    quality = _evaluate_scenario_quality(scenarios)
    assert quality["count"] == 4
    assert quality["min_probability"] == pytest.approx(0.01, abs=1e-6)
    assert quality["max_probability"] == pytest.approx(0.97, abs=1e-6)
    assert quality["has_oligopoly"] is True
    assert quality["unique_directions"] == 3


def test_report_contains_quality_fields():
    rng = np.random.default_rng(31)
    n = 200
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )
    report = build_phase18_report({"test_index": df})
    assert "generated_at" in report
    assert "per_sub_index" in report
    assert "summary" in report
    assert "test_index" in report["per_sub_index"]
    entry = report["per_sub_index"]["test_index"]
    assert "quality" in entry
    assert "scenarios" in entry
