"""Tests for visualization helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.analysis.visualize import (
    _signal_source_color,
    _signal_source_label,
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


def test_signal_source_label_and_color():
    assert _signal_source_label("ensemble_breakout") == "ensemble"
    assert _signal_source_color("ensemble_breakout") == "purple"
    assert _signal_source_label("trend_following_breakout") == "trend_following"
    assert _signal_source_color("trend_following_breakout") == "green"
    assert _signal_source_label("smart_money_liquidity_grab") == "smart_money"
    assert _signal_source_color("smart_money_liquidity_grab") == "orange"
    assert _signal_source_label("pullback_fib") == "pullback"
    assert _signal_source_color("pullback_fib") == "blue"
    assert _signal_source_label("") == "pullback"


def test_plot_price_with_trades_uses_signal_source_colors(tmp_path: Path):
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=8, freq="D"),
            "open": [100.0] * 8,
            "high": [102.0] * 8,
            "low": [99.0] * 8,
            "close": [101.0] * 8,
            "signal_long": [True, True, True, True, False, False, False, False],
            "signal_reason": [
                "pullback_fib",
                "smart_money_liquidity_grab",
                "trend_following_breakout",
                "ensemble_breakout",
                "",
                "",
                "",
                "",
            ],
        }
    )
    result = _make_result()
    output = tmp_path / "trades_with_sources.png"
    fig = plot_price_with_trades(df, result, output_path=output)
    assert fig is not None
    assert output.exists()

    ax = fig.axes[0]
    labels = {text.get_text() for text in ax.get_legend().get_texts()}
    assert "pullback" in labels
    assert "smart_money" in labels
    assert "trend_following" in labels
    assert "ensemble" in labels
