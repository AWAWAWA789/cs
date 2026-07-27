"""Tests for visualization helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.analysis.visualize import (
    generate_report_plots,
    plot_equity_curve,
    plot_price_with_trades,
)
from src.backtest.engine import BacktestResult, Trade


def _make_result() -> BacktestResult:
    """Create a minimal backtest result with two trades."""
    equity = pd.Series(
        [10000.0, 10100.0, 10050.0, 10200.0],
        index=pd.date_range("2024-01-01", periods=4, freq="D"),
    )
    trades = [
        Trade(
            entry_index=1,
            entry_time=equity.index[1],
            entry_price=100.0,
            size=10.0,
            stop_loss=95.0,
            take_profit=110.0,
            exit_index=2,
            exit_time=equity.index[2],
            exit_price=105.0,
            exit_reason="take_profit",
            pnl=50.0,
            return_pct=0.05,
        ),
    ]
    return BacktestResult(
        params=None,  # type: ignore[arg-type]
        trades=trades,
        equity_curve=equity,
        final_equity=equity.iloc[-1],
    )


def _make_df() -> pd.DataFrame:
    """Create a minimal OHLC DataFrame with one signal."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=4, freq="D"),
            "open": [100.0, 101.0, 100.0, 102.0],
            "high": [102.0, 103.0, 106.0, 104.0],
            "low": [99.0, 100.0, 99.0, 101.0],
            "close": [101.0, 102.0, 105.0, 103.0],
            "signal_long": [False, True, False, False],
            "signal_reason": ["", "test", "", ""],
        }
    )


def test_plot_equity_curve_returns_figure():
    result = _make_result()
    fig = plot_equity_curve(result)
    assert fig is not None


def test_plot_equity_curve_saves_png(tmp_path: Path):
    result = _make_result()
    output = tmp_path / "equity.png"
    plot_equity_curve(result, output_path=output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_price_with_trades_returns_figure():
    df = _make_df()
    result = _make_result()
    fig = plot_price_with_trades(df, result)
    assert fig is not None


def test_plot_price_with_trades_saves_png(tmp_path: Path):
    df = _make_df()
    result = _make_result()
    output = tmp_path / "trades.png"
    plot_price_with_trades(df, result, output_path=output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_generate_report_plots_creates_files(tmp_path: Path):
    df = _make_df()
    result = _make_result()
    paths = generate_report_plots(df, result, tmp_path, prefix="test_")
    assert paths["equity_curve"].exists()
    assert paths["trades"].exists()
    assert paths["equity_curve"].name == "test_equity_curve.png"
    assert paths["trades"].name == "test_trades.png"


def test_plot_price_with_trades_draws_swing_points(tmp_path: Path):
    df = _make_df()
    df["swing_high"] = [False, True, False, False]
    df["swing_low"] = [True, False, False, False]
    result = _make_result()
    output = tmp_path / "trades_with_swings.png"
    fig = plot_price_with_trades(df, result, output_path=output)
    assert fig is not None
    assert output.exists()
