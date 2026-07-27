"""End-to-end MVP runner for the CSQAQ price-action strategy.

This script wires together data loading, signal generation, backtesting and
metric reporting. It is sub-index agnostic: the target index is selected via
command-line argument or environment variable.

Example:
    CSQAQ_API_TOKEN=your_token python run_mvp.py --sub-index 手套 --period 4hour
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analysis.metrics import summarize
from src.analysis.visualize import generate_report_plots
from src.api.client import CSQAQClient
from src.backtest.engine import BacktestParams, run_backtest
from src.config import Settings
from src.api.endpoints import bind_local_ip
from src.data.pipeline import load_or_fetch
from src.features.multi_timeframe import add_higher_trend
from src.strategy.signal import SignalParams, generate_signals


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the CSQAQ price-action strategy MVP."
    )
    parser.add_argument(
        "--sub-index",
        dest="sub_index_name",
        default=os.getenv("SUB_INDEX_NAME", "手套"),
        help="Sub-index name to backtest (default: 手套).",
    )
    parser.add_argument(
        "--period",
        default=os.getenv("DEFAULT_PERIOD", "4hour"),
        choices=["1hour", "4hour", "1day", "7day"],
        help="K-line period (default: 4hour).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cache and refetch data from the API.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional path to write the JSON report.",
    )
    parser.add_argument(
        "--bind-ip",
        action="store_true",
        help="Bind the current IP to the ApiToken whitelist before fetching data.",
    )
    parser.add_argument(
        "--confirmations",
        type=int,
        default=int(os.getenv("TREND_CONFIRMATIONS", "2")),
        help="Swing points required to confirm a trend (default: 2).",
    )
    parser.add_argument(
        "--higher-period",
        default=os.getenv("HIGHER_PERIOD"),
        choices=["1hour", "4hour", "1day", "7day"],
        help="Higher timeframe used to determine trend. Lower timeframe signals "
        "must align with this trend. Omit to use the same timeframe.",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Generate equity curve and trade annotation charts.",
    )
    parser.add_argument(
        "--charts-dir",
        type=str,
        default=os.getenv("CHARTS_DIR", "reports"),
        help="Directory to write chart PNGs (default: reports).",
    )
    return parser.parse_args()


def _buy_and_hold_benchmark(df: pd.DataFrame) -> dict[str, object]:
    """Return buy-and-hold performance over the same date range."""
    start_price = float(df["close"].iloc[0])
    end_price = float(df["close"].iloc[-1])
    return {
        "start_price": start_price,
        "end_price": end_price,
        "total_return": (end_price - start_price) / start_price,
    }


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _print_report(
    sub_index_name: str,
    sub_index_id: str,
    period: str,
    df: pd.DataFrame,
    metrics: dict[str, object],
    benchmark: dict[str, object],
) -> None:
    start_date = df["timestamp"].iloc[0]
    end_date = df["timestamp"].iloc[-1]

    print("\nCSQAQ Price-Action MVP Backtest")
    print("=" * 40)
    print(f"Sub-index:     {sub_index_name} (id: {sub_index_id})")
    print(f"Period:        {period}")
    print(f"Date range:    {start_date} -> {end_date}")
    print(f"Bars:          {len(df)}")

    print("\nStrategy Performance")
    print("-" * 40)
    print(f"Initial capital:  {metrics['initial_capital']:.2f}")
    print(f"Final equity:     {metrics['final_equity']:.2f}")
    print(f"Total return:     {_format_percent(metrics['total_return'])}")
    print(f"Max drawdown:     {_format_percent(metrics['max_drawdown'])}")
    print(f"Sharpe ratio:     {metrics['sharpe_ratio']:.3f}")
    print(f"Total trades:     {metrics['total_trades']}")
    print(f"Win rate:         {_format_percent(metrics['win_rate'])}")
    print(f"Profit factor:    {metrics['profit_factor']:.3f}")
    print(f"Avg trade return: {_format_percent(metrics['avg_trade_return'])}")

    print("\nBenchmark (Buy & Hold)")
    print("-" * 40)
    print(f"Start price:      {benchmark['start_price']:.2f}")
    print(f"End price:        {benchmark['end_price']:.2f}")
    print(f"Total return:     {_format_percent(benchmark['total_return'])}")


def _write_report(output_path: str, report: dict[str, object]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport saved to: {path}")


def main() -> None:
    args = _parse_args()
    settings = Settings()
    settings.validate()

    client = CSQAQClient(settings)

    if args.bind_ip:
        bind_local_ip(client)

    df = load_or_fetch(
        settings,
        client,
        sub_index_name=args.sub_index_name,
        period=args.period,
        force_refresh=args.force_refresh,
    )
    sub_index_id = settings.sub_index_id or "resolved"

    trend_col = "trend"
    if args.higher_period and args.higher_period != args.period:
        higher_df = load_or_fetch(
            settings,
            client,
            sub_index_name=args.sub_index_name,
            period=args.higher_period,
            force_refresh=args.force_refresh,
        )
        df = add_higher_trend(
            df,
            higher_df,
            col_name="higher_trend",
            swing_order=2,
            confirmations=args.confirmations,
        )
        trend_col = "higher_trend"
        print(f"Higher timeframe trend: {args.higher_period}")

    signal_df = generate_signals(
        df,
        SignalParams(
            swing_order=2,
            fib_tolerance=0.03,
            confirmations=args.confirmations,
        ),
        trend_col=trend_col,
    )
    signal_count = int(signal_df["signal_long"].sum())
    print(f"Trend confirmations: {args.confirmations}")
    print(f"Long signals generated: {signal_count}")

    backtest_result = run_backtest(signal_df, BacktestParams())
    metrics = summarize(backtest_result)
    benchmark = _buy_and_hold_benchmark(signal_df)

    _print_report(
        args.sub_index_name,
        sub_index_id,
        args.period,
        signal_df,
        metrics,
        benchmark,
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_index_name": args.sub_index_name,
        "sub_index_id": sub_index_id,
        "period": args.period,
        "higher_period": args.higher_period,
        "bars": len(signal_df),
        "date_range": {
            "start": str(signal_df["timestamp"].iloc[0]),
            "end": str(signal_df["timestamp"].iloc[-1]),
        },
        "strategy": metrics,
        "benchmark": benchmark,
    }

    if args.output:
        _write_report(args.output, report)

    if args.charts:
        prefix = f"{args.sub_index_name}_{args.period}_"
        plot_paths = generate_report_plots(
            signal_df, backtest_result, args.charts_dir, prefix=prefix
        )
        print(f"\nCharts saved:")
        for name, path in plot_paths.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
