"""Tests for the generic backtest engine."""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.engine import BacktestParams, Trade, run_backtest


def _make_bars(signal_index: int | None, n: int = 10) -> pd.DataFrame:
    """Return a simple upward-sloping OHLC DataFrame.

    The series starts at 100 and rises by 1 each bar. A signal is injected
    at ``signal_index`` if provided.
    """
    base = pd.DataFrame(
        {
            "open": [100.0 + i for i in range(n)],
            "high": [100.5 + i for i in range(n)],
            "low": [99.5 + i for i in range(n)],
            "close": [100.0 + i for i in range(n)],
        }
    )
    base["signal_long"] = False
    base["signal_swing_low"] = pd.NA
    base["signal_swing_high"] = pd.NA
    if signal_index is not None:
        base.loc[signal_index, "signal_long"] = True
        base.loc[signal_index, "signal_swing_low"] = 99.0
        base.loc[signal_index, "signal_swing_high"] = 101.0
    return base


def test_entry_and_take_profit():
    """A signal followed by a bar that hits take profit should close the trade."""
    df = _make_bars(signal_index=0, n=6)
    # Entry at bar 1 open = 101. Stop loss below swing low 99 -> ~98.8.
    # Take profit target 1.272 from low=99, high=101 -> 101 + 0.272*2 = 101.544.
    # Make bar 1 hit TP.
    df.loc[1, "high"] = 102.0
    df.loc[1, "low"] = 102.0
    df.loc[1, "close"] = 102.0

    result = run_backtest(df, BacktestParams(tp_target="1.272"))

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.exit_reason == "take_profit"
    assert trade.exit_price == pytest.approx(101.544)
    assert trade.pnl > 0
    assert result.equity_curve.iloc[-1] > result.params.initial_capital


def test_entry_and_stop_loss():
    """A signal followed by a bar that hits stop loss should close the trade."""
    df = _make_bars(signal_index=0, n=6)
    # Entry at bar 1 open = 101. Stop loss below swing low 99 -> ~98.8.
    # Make bar 1 hit stop loss.
    df.loc[1, "high"] = 99.0
    df.loc[1, "low"] = 98.0
    df.loc[1, "close"] = 98.0

    result = run_backtest(df, BacktestParams(tp_target="1.272"))

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price < trade.entry_price
    assert trade.pnl < 0
    assert result.equity_curve.iloc[-1] < result.params.initial_capital


def test_no_signal_no_trades():
    """Without any signal the equity curve stays flat."""
    df = _make_bars(signal_index=None, n=5)

    result = run_backtest(df)

    assert len(result.trades) == 0
    assert result.equity_curve.iloc[-1] == result.params.initial_capital


def test_stop_loss_takes_precedence_over_take_profit():
    """If both SL and TP are hit on the same bar, stop loss is used."""
    df = _make_bars(signal_index=0, n=6)
    # Entry at bar 1 open = 101. SL ~98.8, TP 101.544.
    # Make bar 1 span both levels.
    df.loc[1, "high"] = 110.0
    df.loc[1, "low"] = 95.0

    result = run_backtest(df, BacktestParams(tp_target="1.272"))

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "stop_loss"


def test_trade_dataclass_defaults():
    trade = Trade(entry_index=0, entry_time=0, entry_price=100.0, size=1.0, stop_loss=99.0, take_profit=105.0)
    assert trade.exit_index is None
    assert trade.pnl == 0.0
