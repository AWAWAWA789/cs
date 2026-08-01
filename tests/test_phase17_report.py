from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate_phase17_report import build_phase17_report


def test_report_contains_per_sub_index_and_summary():
    rng = np.random.default_rng(21)
    n = 60
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price,
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.01, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.01, n))),
            "close": price,
        }
    )
    df["signal_long"] = False
    df["signal_swing_low"] = df["low"]
    df["signal_swing_high"] = df["high"]
    df.loc[10, "signal_long"] = True

    report = build_phase17_report({"test_index": df})
    assert "generated_at" in report
    assert "per_sub_index" in report
    assert "summary" in report
    assert "test_index" in report["per_sub_index"]
    entry = report["per_sub_index"]["test_index"]
    assert "strategy" in entry
    assert "benchmark" in entry
    assert "excess_return" in entry
    assert "beat_buy_and_hold" in entry


def test_report_summary_counts_beating_indices():
    rng = np.random.default_rng(22)
    n = 60
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price,
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.01, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.01, n))),
            "close": price,
        }
    )
    df["signal_long"] = False
    df["signal_swing_low"] = df["low"]
    df["signal_swing_high"] = df["high"]
    df.loc[10, "signal_long"] = True

    report = build_phase17_report({"a": df, "b": df})
    summary = report["summary"]
    assert summary["sub_index_count"] == 2
    assert 0 <= summary["beat_buy_and_hold_count"] <= 2
    assert 0.0 <= summary["beat_buy_and_hold_ratio"] <= 1.0
