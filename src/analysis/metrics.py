"""Performance and risk metrics for backtest results.

All functions work with simple primitives (equity curves, trade lists) so they
can be reused across strategies and timeframes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult, Trade


def cumulative_return(equity_curve: pd.Series) -> float:
    """Return the total return over the equity curve."""
    if equity_curve.empty or equity_curve.iloc[0] == 0:
        return 0.0
    return float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)


def max_drawdown(equity_curve: pd.Series) -> float:
    """Return the maximum peak-to-trough drawdown as a negative fraction."""
    if equity_curve.empty:
        return 0.0
    running_peak = equity_curve.cummax()
    drawdown = (equity_curve - running_peak) / running_peak
    return float(drawdown.min())


def sharpe_ratio(
    returns: pd.Series,
    periods_per_year: float = 6 * 365,
    risk_free_rate: float = 0.0,
) -> float:
    """Return the annualized Sharpe ratio for a per-bar return series.

    Args:
        returns: Per-bar returns (e.g. from ``equity_curve.pct_change()``).
        periods_per_year: Number of bars per year. The default ``6 * 365``
            assumes 4-hour bars.
        risk_free_rate: Annual risk-free rate. A per-bar rate is subtracted
            from each return before scaling.
    """
    if returns.empty or returns.std() == 0:
        return 0.0
    per_period_rf = risk_free_rate / periods_per_year
    excess = returns - per_period_rf
    return float(
        (excess.mean() * periods_per_year)
        / (excess.std() * np.sqrt(periods_per_year))
    )


def win_rate(trades: list[Trade]) -> float:
    """Fraction of trades with positive PnL."""
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl > 0)
    return wins / len(trades)


def profit_factor(trades: list[Trade]) -> float:
    """Gross profit divided by gross loss."""
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def total_trades(trades: list[Trade]) -> int:
    """Total number of closed trades."""
    return len(trades)


def average_trade_return(trades: list[Trade]) -> float:
    """Average per-trade return."""
    if not trades:
        return 0.0
    return sum(t.return_pct for t in trades) / len(trades)


def summarize(result: BacktestResult) -> dict[str, object]:
    """Return a dictionary of common performance metrics."""
    equity = result.equity_curve
    returns = equity.pct_change().dropna()
    return {
        "initial_capital": result.params.initial_capital,
        "final_equity": result.final_equity,
        "total_return": cumulative_return(equity),
        "max_drawdown": max_drawdown(equity),
        "sharpe_ratio": sharpe_ratio(returns),
        "total_trades": total_trades(result.trades),
        "win_rate": win_rate(result.trades),
        "profit_factor": profit_factor(result.trades),
        "avg_trade_return": average_trade_return(result.trades),
    }
