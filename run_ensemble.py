"""End-to-end runner for the dual-strategy ensemble.

This script wires together data loading, ensemble signal generation, backtesting
and metric reporting. It also reports the standalone pullback and trend-following
strategies so that the contribution of the ensemble can be evaluated.

Example:
    CSQAQ_API_TOKEN=your_token python run_ensemble.py --sub-index 手套 --period 1day
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
from src.data.pipeline import load_or_fetch
from src.strategy.ensemble import EnsembleParams, generate_ensemble_signals
from src.strategy.signal import SignalParams, generate_signals
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the CSQAQ price-action dual-strategy ensemble."
    )
    parser.add_argument(
        "--sub-index",
        dest="sub_index_name",
        default=os.getenv("SUB_INDEX_NAME", "手套"),
        help="Sub-index name to backtest (default: 手套).",
    )
    parser.add_argument(
        "--period",
        default=os.getenv("DEFAULT_PERIOD", "1day"),
        choices=["1hour", "4hour", "1day", "7day"],
        help="K-line period (default: 1day).",
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
        "--mode",
        default="regime_switch",
        choices=["regime_switch", "union", "dynamic_weight"],
        help="Ensemble mode (default: regime_switch).",
    )
    parser.add_argument(
        "--adx-threshold",
        type=float,
        default=25.0,
        help="ADX threshold for regime_switch mode (default: 25.0).",
    )
    parser.add_argument(
        "--regime-confirmations",
        type=int,
        default=4,
        help="Confirmations for market regime detection (default: 4).",
    )
    parser.add_argument(
        "--trend-strength-threshold",
        type=float,
        default=25.0,
        help="ADX threshold for trend-following signals (default: 25.0).",
    )
    parser.add_argument(
        "--trend-use-di-filter",
        action="store_true",
        help="Require +DI > -DI for trend-following signals.",
    )
    parser.add_argument(
        "--trend-use-volatility-filter",
        action="store_true",
        help="Require breakout size to exceed ATR * multiplier.",
    )
    parser.add_argument(
        "--trend-volatility-atr-multiplier",
        type=float,
        default=0.5,
        help="ATR multiplier for volatility filter (default: 0.5).",
    )
    parser.add_argument(
        "--trend-use-pullback-confirmation",
        action="store_true",
        help="Wait for a pullback retest before entering breakouts.",
    )
    parser.add_argument(
        "--trend-pullback-lookback",
        type=int,
        default=5,
        help="Lookback bars for pullback confirmation (default: 5).",
    )
    parser.add_argument(
        "--trend-pullback-buffer",
        type=float,
        default=0.005,
        help="Buffer around breakout level for pullback confirmation (default: 0.005).",
    )
    parser.add_argument(
        "--use-signal-quality",
        action="store_true",
        help="Enable signal quality scoring and filtering.",
    )
    parser.add_argument(
        "--min-signal-quality",
        type=float,
        default=0.0,
        help="Minimum signal quality score [0, 1] (default: 0.0).",
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


def _run_strategy(name: str, df: pd.DataFrame, params: BacktestParams) -> dict[str, object]:
    """Run backtest and return metrics plus signal count."""
    result = run_backtest(df, params)
    metrics = summarize(result)
    metrics["signal_count"] = int(df["signal_long"].sum())
    return {"name": name, "metrics": metrics, "result": result}


def _print_report(
    sub_index_name: str,
    sub_index_id: str,
    period: str,
    df: pd.DataFrame,
    strategies: list[dict[str, object]],
    benchmark: dict[str, object],
) -> None:
    start_date = df["timestamp"].iloc[0]
    end_date = df["timestamp"].iloc[-1]

    print("\nCSQAQ Dual-Strategy Ensemble Backtest")
    print("=" * 40)
    print(f"Sub-index:     {sub_index_name} (id: {sub_index_id})")
    print(f"Period:        {period}")
    print(f"Date range:    {start_date} -> {end_date}")
    print(f"Bars:          {len(df)}")

    for strategy in strategies:
        metrics = strategy["metrics"]
        print(f"\n{strategy['name']} Performance")
        print("-" * 40)
        print(f"Signals:          {metrics['signal_count']}")
        print(f"Total return:     {_format_percent(metrics['total_return'])}")
        print(f"Max drawdown:     {_format_percent(metrics['max_drawdown'])}")
        print(f"Sharpe ratio:     {metrics['sharpe_ratio']:.3f}")
        print(f"Total trades:     {metrics['total_trades']}")
        print(f"Win rate:         {_format_percent(metrics['win_rate'])}")
        print(f"Profit factor:    {metrics['profit_factor']:.3f}")

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

    df = load_or_fetch(
        settings,
        client,
        sub_index_name=args.sub_index_name,
        period=args.period,
        force_refresh=args.force_refresh,
    )
    sub_index_id = settings.sub_index_id or "resolved"

    pullback_params = SignalParams(
        swing_order=2,
        fib_tolerance=0.03,
        confirmations=1,
        use_smart_money=True,
        use_trend_following=False,
        use_signal_quality=args.use_signal_quality,
        min_signal_quality=args.min_signal_quality,
    )
    trend_params = TrendFollowingParams(
        swing_order=2,
        confirmations=1,
        trend_strength_threshold=args.trend_strength_threshold,
        use_higher_high_breakout=False,
        require_uptrend=True,
        use_di_filter=args.trend_use_di_filter,
        use_volatility_filter=args.trend_use_volatility_filter,
        volatility_atr_multiplier=args.trend_volatility_atr_multiplier,
        use_pullback_confirmation=args.trend_use_pullback_confirmation,
        pullback_lookback=args.trend_pullback_lookback,
        pullback_buffer=args.trend_pullback_buffer,
    )
    ensemble_params = EnsembleParams(
        pullback_params=pullback_params,
        trend_params=trend_params,
        mode=args.mode,
        adx_threshold=args.adx_threshold,
        regime_confirmations=args.regime_confirmations,
        use_signal_quality=args.use_signal_quality,
        min_signal_quality=args.min_signal_quality,
    )

    pullback_df = generate_signals(df, pullback_params)
    trend_df = generate_trend_following_signals(df, trend_params)
    ensemble_df = generate_ensemble_signals(df, ensemble_params)

    backtest_params = BacktestParams()

    strategies = [
        _run_strategy("Pullback", pullback_df, backtest_params),
        _run_strategy("Trend-Following", trend_df, backtest_params),
        _run_strategy("Ensemble", ensemble_df, backtest_params),
    ]

    benchmark = _buy_and_hold_benchmark(ensemble_df)

    _print_report(
        args.sub_index_name,
        sub_index_id,
        args.period,
        ensemble_df,
        strategies,
        benchmark,
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_index_name": args.sub_index_name,
        "sub_index_id": sub_index_id,
        "period": args.period,
        "bars": len(ensemble_df),
        "date_range": {
            "start": str(ensemble_df["timestamp"].iloc[0]),
            "end": str(ensemble_df["timestamp"].iloc[-1]),
        },
        "ensemble_params": {
            "mode": args.mode,
            "adx_threshold": args.adx_threshold,
            "regime_confirmations": args.regime_confirmations,
            "trend_strength_threshold": args.trend_strength_threshold,
        },
        "strategies": [
            {
                "name": s["name"],
                "metrics": s["metrics"],
            }
            for s in strategies
        ],
        "benchmark": benchmark,
    }

    if args.output:
        _write_report(args.output, report)

    if args.charts:
        prefix = f"ensemble_{args.sub_index_name}_{args.period}_"
        plot_paths = generate_report_plots(
            ensemble_df, strategies[-1]["result"], args.charts_dir, prefix=prefix
        )
        print(f"\nCharts saved:")
        for name, path in plot_paths.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
