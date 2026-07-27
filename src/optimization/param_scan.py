"""Parameter sensitivity scanner for the price-action strategy.

The scanner evaluates combinations of signal and backtest parameters on a
single sub-index/period and writes a JSON report with the resulting metrics.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.metrics import summarize
from src.api.client import CSQAQClient
from src.backtest.engine import BacktestParams, run_backtest
from src.config import Settings
from src.data.pipeline import load_or_fetch
from src.strategy.signal import SignalParams, generate_signals


@dataclass(frozen=True)
class ScanPoint:
    """A single parameter combination to evaluate."""

    swing_order: int = 2
    fib_tolerance: float = 0.03
    confirmations: int = 2
    target_levels: tuple[str, ...] = ("0.5", "0.618")
    tp_target: str = "1.272"
    stop_loss_buffer: float = 0.002

    def to_dict(self) -> dict[str, Any]:
        return {
            "swing_order": self.swing_order,
            "fib_tolerance": self.fib_tolerance,
            "confirmations": self.confirmations,
            "target_levels": list(self.target_levels),
            "tp_target": self.tp_target,
            "stop_loss_buffer": self.stop_loss_buffer,
        }


def default_grid() -> list[ScanPoint]:
    """Return a reasonable default parameter grid for glove/index 1d data."""
    swing_orders = [1, 2]
    fib_tolerances = [0.03, 0.05, 0.08]
    confirmations_list = [1, 2]
    target_level_sets = [
        ("0.5", "0.618"),
        ("0.382", "0.5", "0.618"),
    ]
    tp_targets = ["1.272", "1.618"]
    stop_loss_buffers = [0.002, 0.005]

    points: list[ScanPoint] = []
    for (
        swing_order,
        fib_tolerance,
        confirmations,
        target_levels,
        tp_target,
        stop_loss_buffer,
    ) in itertools.product(
        swing_orders,
        fib_tolerances,
        confirmations_list,
        target_level_sets,
        tp_targets,
        stop_loss_buffers,
    ):
        points.append(
            ScanPoint(
                swing_order=swing_order,
                fib_tolerance=fib_tolerance,
                confirmations=confirmations,
                target_levels=target_levels,
                tp_target=tp_target,
                stop_loss_buffer=stop_loss_buffer,
            )
        )
    return points


def _signal_params(point: ScanPoint) -> SignalParams:
    return SignalParams(
        swing_order=point.swing_order,
        fib_tolerance=point.fib_tolerance,
        target_levels=point.target_levels,
        confirmations=point.confirmations,
    )


def _backtest_params(point: ScanPoint) -> BacktestParams:
    return BacktestParams(
        tp_target=point.tp_target,
        stop_loss_buffer=point.stop_loss_buffer,
    )


def evaluate_point(
    df: pd.DataFrame,
    point: ScanPoint,
) -> dict[str, Any]:
    """Run signal generation and backtest for a single parameter point."""
    signal_df = generate_signals(df, _signal_params(point))
    signal_count = int(signal_df["signal_long"].sum())
    result = run_backtest(signal_df, _backtest_params(point))
    metrics = summarize(result)
    return {
        "params": point.to_dict(),
        "signal_count": signal_count,
        "metrics": metrics,
    }


def run_scan(
    df: pd.DataFrame,
    grid: list[ScanPoint] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate every point in ``grid`` and return ordered results.

    Results are sorted by total return descending.
    """
    grid = grid or default_grid()
    results = [evaluate_point(df, point) for point in grid]
    results.sort(key=lambda r: r["metrics"]["total_return"], reverse=True)
    return results


def scan_report(
    results: list[dict[str, Any]],
    sub_index_name: str,
    period: str,
    bars: int,
) -> dict[str, Any]:
    """Build a structured scan report."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_index_name": sub_index_name,
        "period": period,
        "bars": bars,
        "combinations": len(results),
        "top_10": results[:10],
        "bottom_10": results[-10:],
        "all_results": results,
    }


def save_report(report: dict[str, Any], path: str | Path) -> Path:
    """Save ``report`` as JSON and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    return path


def main() -> None:
    """CLI entry point for running a parameter scan."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a parameter sensitivity scan for the price-action strategy."
    )
    parser.add_argument(
        "--sub-index",
        dest="sub_index_name",
        default="手套",
        help="Sub-index name to scan (default: 手套).",
    )
    parser.add_argument(
        "--period",
        default="1day",
        help="K-line period (default: 1day).",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional path to write the JSON scan report.",
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

    results = run_scan(df)
    report = scan_report(
        results,
        sub_index_name=args.sub_index_name,
        period=args.period,
        bars=len(df),
    )

    print(f"Scanned {len(results)} parameter combinations.")
    top = report["top_10"][0]
    print(
        f"Best return: {top['metrics']['total_return']:.2%} "
        f"(signals={top['signal_count']}, trades={top['metrics']['total_trades']})"
    )
    print(f"Params: {top['params']}")

    if args.output:
        path = save_report(report, args.output)
        print(f"Report saved to: {path}")


if __name__ == "__main__":
    main()
