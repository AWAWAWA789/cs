"""Tests for Phase 15 report generator."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate_phase15_report import build_phase15_report


def test_report_contains_buy_and_hold_benchmark(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("generate_phase15_report.DEFAULT_OUTPUT_DIR", tmp_path)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC"),
        "open": np.ones(10) * 100,
        "high": np.ones(10) * 101,
        "low": np.ones(10) * 99,
        "close": np.linspace(100, 109, 10),
    })
    report = build_phase15_report({"test": df})
    assert "buy_and_hold" in report["per_sub_index"]["test"]
    assert report["per_sub_index"]["test"]["buy_and_hold"]["total_return"] == pytest.approx(
        0.09, abs=1e-6
    )
