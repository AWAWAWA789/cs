"""Standalone scanner for the trend-following strategy.

Evaluates every combination of trend-following filters and reports the best
standalone parameter sets per sub-index. This is used in phase 8 to find a
configuration where trend-following contributes non-negative returns on its own.

Example:
    CSQAQ_API_TOKEN=your_token python run_trend_scan.py --sub-index 手套 --period 1day
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.metrics import summarize
from src.api.client import CSQAQClient
from src.backtest.engine import BacktestParams, run_backtest
from src.config import Settings
from src.data.pipeline import load_or_fetch
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan trend-following parameters for a single sub-index."
    )
    parser.add_argument(
        "--sub-index",
        dest="sub_index_name",
        default=os.getenv("SUB_INDEX_NAME", "手套"),
        help="Sub-index name to scan (default: 手套).",
    )
    parser.add_argument(
        "--period",
        default=os.getenv("DEFAULT_PERIOD", "1day"),
        help="K-line period (default: 1day).",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional path to write the JSON scan report.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cache and refetch data from the API.",
    )
    return parser.parse_args()


def _param_grid() -> list[dict[str, Any]]:
    """Return trend-following parameter combinations to evaluate."""
    grid: list[dict[str, Any]] = []
    for (
        swing_order,
        confirmations,
        trend_strength_threshold,
        use_di_filter,
        use_volatility_filter,
        volatility_atr_multiplier,
        use_pullback_confirmation,
        pullback_lookback,
        pullback_buffer,
    ) in itertools.product(
        (1, 2),
        (1, 2),
        (None, 20.0, 25.0, 30.0),
        (False, True),
        (False, True),
        (0.3, 0.5, 1.0),
        (False, True),
        (3, 5, 8),
        (0.003, 0.005, 0.01),
    ):
        grid.append(
            {
                "swing_order": swing_order,
                "confirmations": confirmations,
                "trend_strength_threshold": trend_strength_threshold,
                "adx_period": 14,
                "use_higher_high_breakout": False,
                "require_uptrend": True,
                "use_di_filter": use_di_filter,
                "use_volatility_filter": use_volatility_filter,
                "volatility_atr_multiplier": volatility_atr_multiplier,
                "use_pullback_confirmation": use_pullback_confirmation,
                "pullback_lookback": pullback_lookback,
                "pullback_buffer": pullback_buffer,
            }
        )
    return grid


def _evaluate(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    """Run trend-following signals and backtest for one parameter set."""
    trend_params = TrendFollowingParams(**params)
    signal_df = generate_trend_following_signals(df, trend_params)
    signal_count = int(signal_df["signal_long"].sum())
    result = run_backtest(signal_df, BacktestParams())
    metrics = summarize(result)
    return {
        "params": params,
        "signal_count": signal_count,
        "metrics": metrics,
    }


def _scan_report(
    results: list[dict[str, Any]],
    sub_index_name: str,
    period: str,
    bars: int,
) -> dict[str, Any]:
    """Build a structured scan report."""
    results.sort(key=lambda r: r["metrics"]["total_return"], reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_index_name": sub_index_name,
        "period": period,
        "bars": bars,
        "combinations": len(results),
        "top_10": results[:10],
        "bottom_10": results[-10:],
        "non_negative": [r for r in results if r["metrics"]["total_return"] >= 0],
        "all_results": results,
    }


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

    grid = _param_grid()
    results = [_evaluate(df, params) for params in grid]
    report = _scan_report(
        results,
        sub_index_name=args.sub_index_name,
        period=args.period,
        bars=len(df),
    )

    print(f"Scanned {len(results)} trend-following combinations.")
    top = report["top_10"][0]
    print(
        f"Best return: {top['metrics']['total_return']:.2%} "
        f"(signals={top['signal_count']}, trades={top['metrics']['total_trades']})"
    )
    print(f"Best params: {top['params']}")
    print(f"Non-negative combinations: {len(report['non_negative'])}")

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"Report saved to: {path}")


if __name__ == "__main__":
    main()
