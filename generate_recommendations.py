"""Generate sub-index specific parameter recommendations.

This script runs a focused parameter scan for each configured sub-index and
writes a JSON file with the top-performing parameter combination per index.
The recommendations are based on in-sample total return and are intended as a
starting point for walk-forward validation.

Example:
    CSQAQ_API_TOKEN=your_token python generate_recommendations.py
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.api.client import CSQAQClient
from src.config import Settings
from src.data.pipeline import load_or_fetch
from src.optimization.param_scan import ScanPoint, run_scan, save_report


SUB_INDICES = ["手套", "匕首", "百元主战", "贴纸"]


def _focused_grid() -> list[ScanPoint]:
    """Return a focused grid for sub-index recommendation.

    The grid focuses on the parameters that historically drove the largest
    differences in performance: swing_order, take-profit target, Smart Money
    usage, and ensemble vs standalone pullback.
    """
    points: list[ScanPoint] = []
    for swing_order in (1, 2):
        for tp_target in ("1.272", "1.618"):
            for use_smart_money in (True, False):
                for ensemble_mode in (None, "union"):
                    points.append(
                        ScanPoint(
                            swing_order=swing_order,
                            fib_tolerance=0.03,
                            confirmations=1,
                            target_levels=("0.5", "0.618"),
                            tp_target=tp_target,
                            stop_loss_buffer=0.002,
                            use_smart_money=use_smart_money,
                            liquidity_grab_buffer=0.005,
                            use_trend_following=False,
                            require_structure_resonance=False,
                            use_market_regime_filter=False,
                            market_regime_confirmations=4,
                            ensemble_mode=ensemble_mode,
                            ensemble_adx_threshold=25.0,
                            ensemble_regime_confirmations=4,
                            ensemble_trend_strength_threshold=25.0,
                        )
                    )
    return points


def _extract_recommendation(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the top result formatted as a recommendation entry."""
    top = results[0]
    return {
        "params": top["params"],
        "signal_count": top["signal_count"],
        "total_return": top["metrics"]["total_return"],
        "max_drawdown": top["metrics"]["max_drawdown"],
        "sharpe_ratio": top["metrics"]["sharpe_ratio"],
        "total_trades": top["metrics"]["total_trades"],
        "win_rate": top["metrics"]["win_rate"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate sub-index parameter recommendations."
    )
    parser.add_argument(
        "--period",
        default="1day",
        help="K-line period (default: 1day).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="sub_index_recommendations.json",
        help="Output path for recommendations JSON (default: sub_index_recommendations.json).",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="reports",
        help="Directory to write per-sub-index scan reports (default: reports).",
    )
    args = parser.parse_args()

    settings = Settings()
    settings.validate()
    client = CSQAQClient(settings)

    grid = _focused_grid()
    recommendations: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": args.period,
        "grid_size": len(grid),
        "sub_indices": {},
    }

    for sub_index in SUB_INDICES:
        print(f"\nScanning {sub_index}...")
        df = load_or_fetch(
            settings,
            client,
            sub_index_name=sub_index,
            period=args.period,
        )
        results = run_scan(df, grid=grid)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sub_index_name": sub_index,
            "period": args.period,
            "bars": len(df),
            "combinations": len(results),
            "top_10": results[:10],
            "all_results": results,
        }
        report_path = Path(args.report_dir) / f"scan_{sub_index}_1d_phase6.json"
        save_report(report, report_path)
        print(
            f"  Best return: {results[0]['metrics']['total_return']:.2%} "
            f"(signals={results[0]['signal_count']}, "
            f"trades={results[0]['metrics']['total_trades']})"
        )
        print(f"  Report saved: {report_path}")

        recommendations["sub_indices"][sub_index] = _extract_recommendation(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(recommendations, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nRecommendations saved to: {output_path}")


if __name__ == "__main__":
    main()
