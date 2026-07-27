"""Tests for the parameter sensitivity scanner."""

import pandas as pd
import pytest

from src.optimization.param_scan import (
    ScanPoint,
    default_grid,
    evaluate_point,
    run_scan,
    scan_report,
)


def _sample_df() -> pd.DataFrame:
    """Return a small OHLC DataFrame with an engulfing pullback pattern."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=12, freq="D"),
            "open": [100, 102, 101, 103, 102, 105, 103, 104, 103, 106, 104, 105],
            "high": [102, 103, 102, 104, 103, 106, 105, 105, 104, 107, 106, 106],
            "low": [99, 101, 100, 102, 101, 104, 102, 103, 102, 105, 103, 104],
            "close": [101, 102, 101, 103, 102, 105, 104, 104, 103, 106, 105, 105],
        }
    )


def test_default_grid_has_multiple_points():
    grid = default_grid()
    assert len(grid) >= 20
    assert len(set(grid)) == len(grid)


def test_scan_point_to_dict():
    point = ScanPoint(swing_order=1, fib_tolerance=0.05)
    d = point.to_dict()
    assert d["swing_order"] == 1
    assert d["fib_tolerance"] == 0.05
    assert d["target_levels"] == ["0.5", "0.618"]


def test_evaluate_point_returns_expected_keys():
    df = _sample_df()
    point = ScanPoint(
        swing_order=1,
        fib_tolerance=0.05,
        confirmations=1,
        target_levels=("0.5", "0.618"),
    )
    result = evaluate_point(df, point)

    assert "params" in result
    assert "signal_count" in result
    assert "metrics" in result
    assert "total_return" in result["metrics"]
    assert "max_drawdown" in result["metrics"]


def test_run_scan_sorts_by_return():
    df = _sample_df()
    grid = [
        ScanPoint(swing_order=1, fib_tolerance=0.05, confirmations=1),
        ScanPoint(swing_order=2, fib_tolerance=0.01, confirmations=2),
    ]
    results = run_scan(df, grid=grid)

    returns = [r["metrics"]["total_return"] for r in results]
    assert returns == sorted(returns, reverse=True)


def test_scan_report_structure():
    df = _sample_df()
    results = run_scan(df, grid=[ScanPoint()])
    report = scan_report(results, sub_index_name="手套", period="1day", bars=len(df))

    assert report["sub_index_name"] == "手套"
    assert report["period"] == "1day"
    assert report["bars"] == len(df)
    assert report["combinations"] == 1
    assert "top_10" in report
