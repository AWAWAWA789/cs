"""Tests for the walk-forward validation framework."""

from __future__ import annotations

import pandas as pd

from src.optimization.param_scan import ScanPoint
from src.optimization.walk_forward import (
    WalkForwardWindow,
    walk_forward,
    walk_forward_report,
)


def _sample_df(rows: int = 30) -> pd.DataFrame:
    """Return a small OHLC DataFrame."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="D"),
            "open": [100.0 + i * 0.1 for i in range(rows)],
            "high": [101.0 + i * 0.1 for i in range(rows)],
            "low": [99.0 + i * 0.1 for i in range(rows)],
            "close": [100.5 + i * 0.1 for i in range(rows)],
        }
    )


def test_walk_forward_returns_windows():
    df = _sample_df(rows=30)
    grid = [
        ScanPoint(swing_order=1, fib_tolerance=0.05, confirmations=1),
        ScanPoint(swing_order=2, fib_tolerance=0.05, confirmations=1),
    ]
    windows = walk_forward(df, grid=grid, train_size=10, test_size=5)

    assert len(windows) >= 3
    assert all(isinstance(w, WalkForwardWindow) for w in windows)


def test_walk_forward_window_has_best_params_and_metrics():
    df = _sample_df(rows=30)
    grid = [ScanPoint(swing_order=1, fib_tolerance=0.05, confirmations=1)]
    windows = walk_forward(df, grid=grid, train_size=10, test_size=5)

    assert len(windows) > 0
    w = windows[0]
    assert w.train_start >= 0
    assert w.train_end > w.train_start
    assert w.test_start == w.train_end
    assert w.test_end > w.test_start
    assert "swing_order" in w.best_params
    assert "total_return" in w.test_metrics


def test_walk_forward_report_structure():
    df = _sample_df(rows=30)
    grid = [ScanPoint(swing_order=1, fib_tolerance=0.05, confirmations=1)]
    windows = walk_forward(df, grid=grid, train_size=10, test_size=5)
    report = walk_forward_report(windows, sub_index_name="手套", period="1day")

    assert report["sub_index_name"] == "手套"
    assert report["period"] == "1day"
    assert report["windows"] == len(windows)
    assert "avg_test_return" in report
    assert "window_details" in report


def test_walk_forward_returns_empty_when_data_too_short():
    df = _sample_df(rows=10)
    grid = [ScanPoint(swing_order=1, fib_tolerance=0.05, confirmations=1)]
    windows = walk_forward(df, grid=grid, train_size=10, test_size=5)

    assert windows == []
