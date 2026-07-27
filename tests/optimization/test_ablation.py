"""Tests for the ablation study framework."""

from __future__ import annotations

import pandas as pd

from src.optimization.ablation import (
    AblationCase,
    ablation_report,
    default_ablation_cases,
    run_ablation,
)
from src.strategy.signal import SignalParams
from src.backtest.engine import BacktestParams


def _sample_df() -> pd.DataFrame:
    """Return a small OHLC DataFrame with an uptrend and pullback."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=20, freq="D"),
            "open": [100, 102, 101, 104, 103, 106, 105, 108, 107, 110, 109, 112, 111, 114, 113, 116, 115, 118, 117, 120],
            "high": [103, 104, 103, 106, 105, 108, 107, 110, 109, 112, 111, 114, 113, 116, 115, 118, 117, 120, 119, 122],
            "low": [99, 100, 99, 102, 101, 104, 103, 106, 105, 108, 107, 110, 109, 112, 111, 114, 113, 116, 115, 118],
            "close": [100, 103, 102, 105, 104, 107, 106, 109, 108, 111, 110, 113, 112, 115, 114, 117, 116, 119, 118, 121],
        }
    )


def test_default_ablation_cases_cover_modules():
    cases = default_ablation_cases()
    names = {c.name for c in cases}
    expected = {
        "full",
        "no_smart_money",
        "no_trend_following",
        "fib_pattern_only",
        "smart_money_only",
        "trend_following_only",
    }
    assert names == expected


def test_run_ablation_returns_all_cases():
    df = _sample_df()
    results = run_ablation(df)
    cases = {r["case"] for r in results}
    assert "full" in cases
    assert len(results) == len(default_ablation_cases())


def test_ablation_report_has_baseline_and_contributions():
    df = _sample_df()
    results = run_ablation(df)
    report = ablation_report(results, sub_index_name="手套", period="1day")

    assert report["sub_index_name"] == "手套"
    assert report["period"] == "1day"
    assert "baseline_return" in report
    assert len(report["cases"]) == len(results)

    full_row = next(r for r in report["cases"] if r["case"] == "full")
    assert full_row["contribution"] == 0.0


def test_custom_ablation_case():
    df = _sample_df()
    params = SignalParams(swing_order=1, fib_tolerance=0.05, confirmations=1)
    bt_params = BacktestParams()
    cases = [AblationCase("custom", "Custom case", params, bt_params)]
    results = run_ablation(df, cases=cases)

    assert len(results) == 1
    assert results[0]["case"] == "custom"
