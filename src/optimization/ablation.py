"""Ablation study framework for the price-action strategy.

The framework evaluates the marginal contribution of each feature module by
systematically disabling one or more components and comparing the resulting
performance to the full model.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.signal import SignalParams, generate_signals
from src.analysis.metrics import summarize


@dataclass(frozen=True)
class AblationCase:
    """A single ablation configuration."""

    name: str
    description: str
    signal_params: SignalParams
    backtest_params: BacktestParams


def _base_signal_params() -> SignalParams:
    """Return the default base signal parameters for ablation studies."""
    return SignalParams(
        swing_order=2,
        fib_tolerance=0.03,
        target_levels=("0.5", "0.618"),
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.005,
        use_trend_following=True,
    )


def _base_backtest_params() -> BacktestParams:
    """Return the default base backtest parameters for ablation studies."""
    return BacktestParams(tp_target="2.0", stop_loss_buffer=0.002)


def default_ablation_cases() -> list[AblationCase]:
    """Return the standard set of ablation cases.

    Cases:
    - ``full``: all feature modules enabled.
    - ``no_smart_money``: Smart Money features disabled.
    - ``no_trend_following``: trend-following breakout features disabled.
    - ``fib_pattern_only``: only Fibonacci + candlestick patterns enabled.
    - ``smart_money_only``: only Smart Money features enabled.
    - ``trend_following_only``: only trend-following features enabled.
    """
    base_signal = _base_signal_params()
    base_backtest = _base_backtest_params()

    no_smart_money = copy.copy(base_signal)
    no_smart_money.use_smart_money = False

    no_trend_following = copy.copy(base_signal)
    no_trend_following.use_trend_following = False

    fib_pattern_only = copy.copy(base_signal)
    fib_pattern_only.use_smart_money = False
    fib_pattern_only.use_trend_following = False

    smart_money_only = copy.copy(base_signal)
    smart_money_only.target_levels = ()
    smart_money_only.use_trend_following = False

    trend_following_only = copy.copy(base_signal)
    trend_following_only.target_levels = ()
    trend_following_only.use_smart_money = False

    return [
        AblationCase("full", "All modules enabled", base_signal, base_backtest),
        AblationCase(
            "no_smart_money",
            "Smart Money features disabled",
            no_smart_money,
            base_backtest,
        ),
        AblationCase(
            "no_trend_following",
            "Trend-following features disabled",
            no_trend_following,
            base_backtest,
        ),
        AblationCase(
            "fib_pattern_only",
            "Only Fibonacci + candlestick patterns",
            fib_pattern_only,
            base_backtest,
        ),
        AblationCase(
            "smart_money_only",
            "Only Smart Money features",
            smart_money_only,
            base_backtest,
        ),
        AblationCase(
            "trend_following_only",
            "Only trend-following features",
            trend_following_only,
            base_backtest,
        ),
    ]


def run_ablation(
    df: pd.DataFrame,
    cases: list[AblationCase] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate every ablation case and return ordered results.

    Results are sorted by total return descending.
    """
    cases = cases or default_ablation_cases()
    results: list[dict[str, Any]] = []

    for case in cases:
        signal_df = generate_signals(df, case.signal_params)
        signal_count = int(signal_df["signal_long"].sum())
        backtest_result = run_backtest(signal_df, case.backtest_params)
        metrics = summarize(backtest_result)

        results.append(
            {
                "case": case.name,
                "description": case.description,
                "signal_count": signal_count,
                "metrics": metrics,
            }
        )

    results.sort(key=lambda r: r["metrics"]["total_return"], reverse=True)
    return results


def ablation_report(
    results: list[dict[str, Any]],
    sub_index_name: str,
    period: str,
) -> dict[str, Any]:
    """Build a structured ablation report."""
    full_result = next((r for r in results if r["case"] == "full"), None)
    baseline_return = (
        full_result["metrics"]["total_return"] if full_result else 0.0
    )

    rows = []
    for r in results:
        ret = r["metrics"]["total_return"]
        rows.append(
            {
                "case": r["case"],
                "description": r["description"],
                "signal_count": r["signal_count"],
                "total_return": ret,
                "total_trades": r["metrics"]["total_trades"],
                "max_drawdown": r["metrics"]["max_drawdown"],
                "sharpe_ratio": r["metrics"]["sharpe_ratio"],
                "contribution": ret - baseline_return,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_index_name": sub_index_name,
        "period": period,
        "baseline_return": baseline_return,
        "cases": rows,
    }


def save_ablation_report(report: dict[str, Any], path: str | Path) -> Path:
    """Save ``report`` as JSON and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    return path


def main() -> None:
    """CLI entry point for running an ablation study."""
    import argparse

    from src.api.client import CSQAQClient
    from src.config import Settings
    from src.data.pipeline import load_or_fetch

    parser = argparse.ArgumentParser(
        description="Run an ablation study for the price-action strategy."
    )
    parser.add_argument(
        "--sub-index",
        dest="sub_index_name",
        default="手套",
        help="Sub-index name to study (default: 手套).",
    )
    parser.add_argument(
        "--period",
        default="1day",
        help="K-line period (default: 1day).",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional path to write the JSON report.",
    )
    args = parser.parse_args()

    settings = Settings()
    settings.validate()
    client = CSQAQClient(settings)

    df = load_or_fetch(
        settings,
        client,
        sub_index_name=args.sub_index_name,
        period=args.period,
    )

    results = run_ablation(df)
    report = ablation_report(
        results,
        sub_index_name=args.sub_index_name,
        period=args.period,
    )

    print(f"Ablation study completed for {args.sub_index_name} ({args.period}).")
    print(f"Baseline return: {report['baseline_return']:.2%}")
    print("\nCase ranking:")
    for row in report["cases"]:
        print(
            f"  {row['case']:<25} return={row['total_return']:.2%} "
            f"trades={row['total_trades']} contribution={row['contribution']:.2%}"
        )

    if args.output:
        path = save_ablation_report(report, args.output)
        print(f"\nReport saved to: {path}")


if __name__ == "__main__":
    main()
