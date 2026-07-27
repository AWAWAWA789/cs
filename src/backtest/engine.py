"""Generic event-driven backtest engine for long-only price-action signals.

The engine simulates trades using the next-bar open as the entry price and
checks stop-loss / take-profit levels against each bar's high and low. It is
intentionally simple: one position at a time, fixed-fractional position sizing,
and no slippage or commission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.strategy import risk


@dataclass
class Trade:
    """A single simulated trade."""

    entry_index: int
    entry_time: object
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    exit_index: Optional[int] = None
    exit_time: Optional[object] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    return_pct: float = 0.0


@dataclass
class BacktestParams:
    """Parameters controlling the backtest simulation."""

    initial_capital: float = 10_000.0
    risk_fraction: float = 0.02
    stop_loss_buffer: float = 0.002
    tp_target: str = "1.272"


@dataclass
class BacktestResult:
    """Container for backtest output."""

    params: BacktestParams
    trades: list[Trade]
    equity_curve: pd.Series
    final_equity: float


def _close_trade(
    trade: Trade,
    exit_price: float,
    exit_reason: str,
    exit_index: int,
    exit_time: object,
    equity: list[float],
) -> None:
    """Finalize a trade and append the updated equity value."""
    trade.exit_index = exit_index
    trade.exit_time = exit_time
    trade.exit_price = exit_price
    trade.exit_reason = exit_reason
    trade.pnl = (exit_price - trade.entry_price) * trade.size
    trade.return_pct = (exit_price - trade.entry_price) / trade.entry_price
    equity.append(equity[-1] + trade.pnl)


def run_backtest(
    df: pd.DataFrame,
    params: BacktestParams | None = None,
) -> BacktestResult:
    """Run a long-only backtest on ``df``.

    Required columns in ``df``:
    - ``open``, ``high``, ``low``, ``close``: OHLC prices.
    - ``signal_long``: boolean flag; a True value at bar ``i`` triggers an
      entry at the open of bar ``i + 1``.
    - ``signal_swing_low``: recent swing low price used for stop loss.
    - ``signal_swing_high``: recent swing high price used for take profit.

    Args:
        df: Bar data with signal columns.
        params: Backtest parameters.

    Returns:
        A ``BacktestResult`` with the list of trades and the equity curve.
    """
    params = params or BacktestParams()

    if df.empty:
        equity = pd.Series([params.initial_capital], index=pd.RangeIndex(0))
        return BacktestResult(
            params=params,
            trades=[],
            equity_curve=equity,
            final_equity=params.initial_capital,
        )

    equity_values: list[float] = [params.initial_capital]
    trades: list[Trade] = []
    open_trade: Trade | None = None

    for i in range(1, len(df)):
        bar = df.iloc[i]
        prev = df.iloc[i - 1]

        # Open a new position if the previous bar fired a signal and we are flat.
        if open_trade is None and prev["signal_long"]:
            swing_low = float(prev["signal_swing_low"])
            swing_high = float(prev["signal_swing_high"])
            entry_price = float(bar["open"])
            stop_price = risk.stop_loss(entry_price, swing_low, params.stop_loss_buffer)
            tp_levels = risk.take_profit_levels(
                swing_low, swing_high, targets=(params.tp_target,)
            )
            tp_price = tp_levels.get(params.tp_target)
            if tp_price is None:
                raise ValueError(
                    f"Take-profit target '{params.tp_target}' not found in extension levels"
                )
            size = risk.position_size(
                equity_values[-1], params.risk_fraction, entry_price, stop_price
            )
            if size > 0:
                open_trade = Trade(
                    entry_index=i,
                    entry_time=df.index[i],
                    entry_price=entry_price,
                    size=size,
                    stop_loss=stop_price,
                    take_profit=float(tp_price),
                )

        # Manage the open position on the current bar.
        if open_trade is not None:
            if bar["low"] <= open_trade.stop_loss:
                _close_trade(
                    open_trade,
                    open_trade.stop_loss,
                    "stop_loss",
                    i,
                    df.index[i],
                    equity_values,
                )
                trades.append(open_trade)
                open_trade = None
            elif bar["high"] >= open_trade.take_profit:
                _close_trade(
                    open_trade,
                    open_trade.take_profit,
                    "take_profit",
                    i,
                    df.index[i],
                    equity_values,
                )
                trades.append(open_trade)
                open_trade = None
            else:
                equity_values.append(equity_values[-1])
        else:
            equity_values.append(equity_values[-1])

    # If a position is still open at the end, close it at the final close price.
    if open_trade is not None:
        final_close = float(df["close"].iloc[-1])
        _close_trade(
            open_trade,
            final_close,
            "end_of_data",
            len(df) - 1,
            df.index[-1],
            equity_values,
        )
        trades.append(open_trade)

    equity_curve = pd.Series(equity_values, index=df.index)
    return BacktestResult(
        params=params,
        trades=trades,
        equity_curve=equity_curve,
        final_equity=equity_values[-1],
    )
