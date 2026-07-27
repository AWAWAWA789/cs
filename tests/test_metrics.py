"""Tests for performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.metrics import (
    average_trade_return,
    cumulative_return,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    summarize,
    total_trades,
    win_rate,
)
from src.backtest.engine import BacktestParams, BacktestResult, Trade


def test_cumulative_return():
    equity = pd.Series([100.0, 105.0, 110.0])
    assert cumulative_return(equity) == pytest.approx(0.10)


def test_cumulative_return_zero():
    equity = pd.Series([100.0, 100.0, 100.0])
    assert cumulative_return(equity) == pytest.approx(0.0)


def test_max_drawdown():
    equity = pd.Series([100.0, 90.0, 95.0, 80.0, 120.0])
    assert max_drawdown(equity) == pytest.approx(-0.20)


def test_max_drawdown_no_decline():
    equity = pd.Series([100.0, 110.0, 120.0])
    assert max_drawdown(equity) == pytest.approx(0.0)


def test_sharpe_ratio_positive():
    returns = pd.Series([0.001, 0.002, 0.0015, 0.001, 0.002])
    # Mean ~0.0015, std small, annualized with 6*365 periods.
    ratio = sharpe_ratio(returns, periods_per_year=6 * 365)
    assert ratio > 0


def test_sharpe_ratio_zero_volatility():
    returns = pd.Series([0.0, 0.0, 0.0])
    assert sharpe_ratio(returns) == pytest.approx(0.0)


def test_win_rate():
    trades = [
        Trade(entry_index=0, entry_time=0, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=5.0),
        Trade(entry_index=1, entry_time=1, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=-2.0),
        Trade(entry_index=2, entry_time=2, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=3.0),
    ]
    assert win_rate(trades) == pytest.approx(2 / 3)


def test_win_rate_empty():
    assert win_rate([]) == pytest.approx(0.0)


def test_profit_factor():
    trades = [
        Trade(entry_index=0, entry_time=0, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=10.0),
        Trade(entry_index=1, entry_time=1, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=-5.0),
    ]
    assert profit_factor(trades) == pytest.approx(2.0)


def test_profit_factor_no_losses():
    trades = [
        Trade(entry_index=0, entry_time=0, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=10.0),
    ]
    assert profit_factor(trades) == float("inf")


def test_total_trades():
    trades = [Trade(entry_index=i, entry_time=i, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0) for i in range(3)]
    assert total_trades(trades) == 3


def test_average_trade_return():
    trades = [
        Trade(entry_index=0, entry_time=0, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, return_pct=0.05),
        Trade(entry_index=1, entry_time=1, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, return_pct=-0.02),
    ]
    assert average_trade_return(trades) == pytest.approx(0.015)


def test_summarize():
    trades = [
        Trade(entry_index=0, entry_time=0, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=10.0, return_pct=0.1),
        Trade(entry_index=1, entry_time=1, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0, pnl=-5.0, return_pct=-0.05),
    ]
    equity = pd.Series([100.0, 105.0, 110.0])
    result = BacktestResult(
        params=BacktestParams(initial_capital=100.0),
        trades=trades,
        equity_curve=equity,
        final_equity=110.0,
    )
    summary = summarize(result)

    assert summary["total_return"] == pytest.approx(0.10)
    assert summary["total_trades"] == 2
    assert summary["win_rate"] == pytest.approx(0.5)
    assert summary["profit_factor"] == pytest.approx(2.0)
