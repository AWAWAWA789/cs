"""Walk-forward validation framework for the price-action strategy.

The framework splits the dataset into rolling training / test windows,
optimizes signal/backtest parameters on each training window, and evaluates
the chosen parameters on the immediately following test window. This reduces
parameter overfitting and measures strategy stability across different market
regimes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.optimization.param_scan import ScanPoint, evaluate_point, run_scan


@dataclass(frozen=True)
class WalkForwardWindow:
    """A single train/test split and its outcome."""

    train_start: int
    train_end: int
    test_start: int
    test_end: int
    best_params: dict[str, Any]
    train_return: float
    test_metrics: dict[str, Any]


def walk_forward(
    df: pd.DataFrame,
    grid: list[ScanPoint],
    train_size: int,
    test_size: int,
    step_size: int | None = None,
) -> list[WalkForwardWindow]:
    """Run a rolling walk-forward analysis.

    Args:
        df: OHLC DataFrame ordered by time.
        grid: Parameter combinations to evaluate on each training window.
        train_size: Number of bars in each training window.
        test_size: Number of bars in each test window.
        step_size: Number of bars to advance between windows. Defaults to
            ``test_size`` (non-overlapping test windows).

    Returns:
        A list of ``WalkForwardWindow`` records, one per completed window.
    """
    if len(df) < train_size + test_size:
        return []

    step_size = step_size or test_size
    windows: list[WalkForwardWindow] = []

    for test_end in range(train_size + test_size, len(df) + 1, step_size):
        test_start = test_end - test_size
        train_end = test_start
        train_start = max(0, train_end - train_size)

        train_df = df.iloc[train_start:train_end].reset_index(drop=True)
        test_df = df.iloc[test_start:test_end].reset_index(drop=True)

        train_results = run_scan(train_df, grid=grid)
        best = train_results[0]
        best_point = _scan_point_from_dict(best["params"])

        test_result = evaluate_point(test_df, best_point)

        windows.append(
            WalkForwardWindow(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                best_params=best["params"],
                train_return=best["metrics"]["total_return"],
                test_metrics=test_result["metrics"],
            )
        )

    return windows


def _scan_point_from_dict(params: dict[str, Any]) -> ScanPoint:
    """Rebuild a ``ScanPoint`` from its serialized form."""
    return ScanPoint(
        swing_order=params["swing_order"],
        fib_tolerance=params["fib_tolerance"],
        confirmations=params["confirmations"],
        target_levels=tuple(params["target_levels"]),
        tp_target=params["tp_target"],
        stop_loss_buffer=params["stop_loss_buffer"],
        use_smart_money=params["use_smart_money"],
        liquidity_grab_buffer=params["liquidity_grab_buffer"],
        use_trend_following=params["use_trend_following"],
        require_structure_resonance=params.get("require_structure_resonance", False),
        structure_resonance_buffer=params.get("structure_resonance_buffer", 0.03),
        use_market_regime_filter=params.get("use_market_regime_filter", False),
        market_regime_confirmations=params.get("market_regime_confirmations", 4),
        ensemble_mode=params.get("ensemble_mode"),
        ensemble_adx_threshold=params.get("ensemble_adx_threshold", 25.0),
        ensemble_regime_confirmations=params.get("ensemble_regime_confirmations", 4),
        ensemble_trend_strength_threshold=params.get(
            "ensemble_trend_strength_threshold", 25.0
        ),
        ensemble_dynamic_weight_min=params.get("ensemble_dynamic_weight_min", 0.2),
        ensemble_dynamic_weight_max=params.get("ensemble_dynamic_weight_max", 0.8),
        ensemble_dynamic_weight_adx_scale=params.get(
            "ensemble_dynamic_weight_adx_scale", 25.0
        ),
        ensemble_use_signal_quality=params.get("ensemble_use_signal_quality", False),
        ensemble_min_signal_quality=params.get("ensemble_min_signal_quality", 0.0),
        ensemble_quality_trend_weight=params.get(
            "ensemble_quality_trend_weight", 0.4
        ),
        ensemble_quality_structure_weight=params.get(
            "ensemble_quality_structure_weight", 0.4
        ),
        ensemble_quality_confluence_weight=params.get(
            "ensemble_quality_confluence_weight", 0.2
        ),
        trend_use_di_filter=params.get("trend_use_di_filter", False),
        trend_use_volatility_filter=params.get("trend_use_volatility_filter", False),
        trend_volatility_atr_multiplier=params.get(
            "trend_volatility_atr_multiplier", 0.5
        ),
        trend_use_pullback_confirmation=params.get(
            "trend_use_pullback_confirmation", False
        ),
        trend_pullback_lookback=params.get("trend_pullback_lookback", 5),
        trend_pullback_buffer=params.get("trend_pullback_buffer", 0.005),
    )


def walk_forward_report(
    windows: list[WalkForwardWindow],
    sub_index_name: str,
    period: str,
) -> dict[str, Any]:
    """Build a structured walk-forward report."""
    test_returns = [w.test_metrics["total_return"] for w in windows]
    avg_test_return = sum(test_returns) / len(test_returns) if test_returns else 0.0
    positive_windows = sum(1 for r in test_returns if r > 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_index_name": sub_index_name,
        "period": period,
        "windows": len(windows),
        "avg_test_return": avg_test_return,
        "positive_windows": positive_windows,
        "window_details": [
            {
                "train_start": w.train_start,
                "train_end": w.train_end,
                "test_start": w.test_start,
                "test_end": w.test_end,
                "best_params": w.best_params,
                "train_return": w.train_return,
                "test_return": w.test_metrics["total_return"],
                "test_trades": w.test_metrics["total_trades"],
                "test_max_drawdown": w.test_metrics["max_drawdown"],
                "test_sharpe": w.test_metrics["sharpe_ratio"],
            }
            for w in windows
        ],
    }


def save_walk_forward_report(report: dict[str, Any], path: str | Path) -> Path:
    """Save ``report`` as JSON and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    return path


def main() -> None:
    """CLI entry point for walk-forward validation."""
    import argparse

    from src.api.client import CSQAQClient
    from src.config import Settings
    from src.data.pipeline import load_or_fetch
    from src.optimization.param_scan import default_grid

    parser = argparse.ArgumentParser(
        description="Run walk-forward validation for the price-action strategy."
    )
    parser.add_argument(
        "--sub-index",
        dest="sub_index_name",
        default="手套",
        help="Sub-index name to validate (default: 手套).",
    )
    parser.add_argument(
        "--period",
        default="1day",
        help="K-line period (default: 1day).",
    )
    parser.add_argument(
        "--train-size",
        type=int,
        default=300,
        help="Training window size in bars (default: 300).",
    )
    parser.add_argument(
        "--test-size",
        type=int,
        default=150,
        help="Test window size in bars (default: 150).",
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

    # Use a reduced grid focused on market regime filtering and ensemble modes.
    grid = [
        ScanPoint(
            swing_order=swing_order,
            fib_tolerance=fib_tolerance,
            confirmations=1,
            target_levels=("0.5", "0.618"),
            tp_target=tp_target,
            stop_loss_buffer=stop_loss_buffer,
            use_smart_money=use_smart_money,
            liquidity_grab_buffer=0.005,
            use_trend_following=False,
            use_market_regime_filter=use_market_regime_filter,
            market_regime_confirmations=4,
            ensemble_mode=ensemble_mode,
            ensemble_adx_threshold=25.0,
            ensemble_regime_confirmations=4,
            ensemble_trend_strength_threshold=25.0,
        )
        for swing_order in (1, 2)
        for fib_tolerance in (0.03, 0.05)
        for tp_target in ("1.272", "1.618")
        for stop_loss_buffer in (0.002, 0.005)
        for use_smart_money in (True, False)
        for use_market_regime_filter in (True, False)
        for ensemble_mode in (None, "regime_switch", "union")
    ]

    windows = walk_forward(
        df,
        grid=grid,
        train_size=args.train_size,
        test_size=args.test_size,
    )
    report = walk_forward_report(
        windows,
        sub_index_name=args.sub_index_name,
        period=args.period,
    )

    print(f"Completed {len(windows)} walk-forward windows.")
    print(f"Average test return: {report['avg_test_return']:.2%}")
    print(f"Positive windows: {report['positive_windows']} / {len(windows)}")

    if args.output:
        path = save_walk_forward_report(report, args.output)
        print(f"Report saved to: {path}")


if __name__ == "__main__":
    main()
