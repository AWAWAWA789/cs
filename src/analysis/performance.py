from __future__ import annotations

from typing import Any

import pandas as pd

from src.analysis.buy_and_hold import compute_buy_and_hold
from src.analysis.metrics import summarize
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.signal import SignalParams, generate_signals


def compare_strategy_vs_benchmark(
    df: pd.DataFrame,
    signal_params: SignalParams | None = None,
    backtest_params: BacktestParams | None = None,
) -> dict[str, Any]:
    """Run strategy backtest and compare with buy-and-hold benchmark.

    Args:
        df: OHLC DataFrame. If ``signal_long`` is not present, signals are
            generated using ``signal_params``.
        signal_params: Parameters for signal generation.
        backtest_params: Parameters for the backtest engine.

    Returns:
        Dictionary with strategy metrics, benchmark metrics, excess return,
        and a boolean flag indicating whether the strategy beat buy-and-hold.
    """
    signal_params = signal_params or SignalParams()
    backtest_params = backtest_params or BacktestParams()

    if "signal_long" not in df.columns:
        df = generate_signals(df, signal_params)

    backtest_result = run_backtest(df, backtest_params)
    strategy_metrics = summarize(backtest_result)
    benchmark_metrics = compute_buy_and_hold(df)

    excess_return = float(strategy_metrics["total_return"] - benchmark_metrics["total_return"])

    return {
        "strategy": strategy_metrics,
        "benchmark": benchmark_metrics,
        "excess_return": round(excess_return, 6),
        "beat_buy_and_hold": excess_return > 0,
    }
