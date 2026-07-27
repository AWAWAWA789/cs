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
from src.strategy.ensemble import EnsembleParams, generate_ensemble_signals
from src.strategy.signal import SignalParams, generate_signals
from src.strategy.trend_following_strategy import TrendFollowingParams


@dataclass(frozen=True)
class ScanPoint:
    """A single parameter combination to evaluate."""

    swing_order: int = 2
    fib_tolerance: float = 0.03
    confirmations: int = 1
    target_levels: tuple[str, ...] = ("0.5", "0.618")
    tp_target: str = "1.272"
    stop_loss_buffer: float = 0.002
    use_smart_money: bool = True
    liquidity_grab_buffer: float = 0.005
    use_trend_following: bool = False
    require_structure_resonance: bool = False
    structure_resonance_buffer: float = 0.03
    use_market_regime_filter: bool = False
    market_regime_confirmations: int = 4
    ensemble_mode: str | None = None
    ensemble_adx_threshold: float = 25.0
    ensemble_regime_confirmations: int = 4
    ensemble_trend_strength_threshold: float = 25.0
    ensemble_dynamic_weight_min: float = 0.2
    ensemble_dynamic_weight_max: float = 0.8
    ensemble_dynamic_weight_adx_scale: float = 25.0
    ensemble_use_signal_quality: bool = False
    ensemble_min_signal_quality: float = 0.0
    ensemble_quality_trend_weight: float = 0.4
    ensemble_quality_structure_weight: float = 0.4
    ensemble_quality_confluence_weight: float = 0.2
    trend_use_di_filter: bool = False
    trend_use_volatility_filter: bool = False
    trend_volatility_atr_multiplier: float = 0.5
    trend_use_pullback_confirmation: bool = False
    trend_pullback_lookback: int = 5
    trend_pullback_buffer: float = 0.005

    def to_dict(self) -> dict[str, Any]:
        return {
            "swing_order": self.swing_order,
            "fib_tolerance": self.fib_tolerance,
            "confirmations": self.confirmations,
            "target_levels": list(self.target_levels),
            "tp_target": self.tp_target,
            "stop_loss_buffer": self.stop_loss_buffer,
            "use_smart_money": self.use_smart_money,
            "liquidity_grab_buffer": self.liquidity_grab_buffer,
            "use_trend_following": self.use_trend_following,
            "require_structure_resonance": self.require_structure_resonance,
            "structure_resonance_buffer": self.structure_resonance_buffer,
            "use_market_regime_filter": self.use_market_regime_filter,
            "market_regime_confirmations": self.market_regime_confirmations,
            "ensemble_mode": self.ensemble_mode,
            "ensemble_adx_threshold": self.ensemble_adx_threshold,
            "ensemble_regime_confirmations": self.ensemble_regime_confirmations,
            "ensemble_trend_strength_threshold": self.ensemble_trend_strength_threshold,
            "ensemble_dynamic_weight_min": self.ensemble_dynamic_weight_min,
            "ensemble_dynamic_weight_max": self.ensemble_dynamic_weight_max,
            "ensemble_dynamic_weight_adx_scale": self.ensemble_dynamic_weight_adx_scale,
            "ensemble_use_signal_quality": self.ensemble_use_signal_quality,
            "ensemble_min_signal_quality": self.ensemble_min_signal_quality,
            "ensemble_quality_trend_weight": self.ensemble_quality_trend_weight,
            "ensemble_quality_structure_weight": self.ensemble_quality_structure_weight,
            "ensemble_quality_confluence_weight": self.ensemble_quality_confluence_weight,
            "trend_use_di_filter": self.trend_use_di_filter,
            "trend_use_volatility_filter": self.trend_use_volatility_filter,
            "trend_volatility_atr_multiplier": self.trend_volatility_atr_multiplier,
            "trend_use_pullback_confirmation": self.trend_use_pullback_confirmation,
            "trend_pullback_lookback": self.trend_pullback_lookback,
            "trend_pullback_buffer": self.trend_pullback_buffer,
        }


def default_grid() -> list[ScanPoint]:
    """Return a reasonable default parameter grid for glove/index 1d data.

    The grid includes Smart Money switches and the liquidity-grab buffer so that
    the scan can quantify the contribution of Smart Money features.
    """
    swing_orders = [1, 2]
    fib_tolerances = [0.03, 0.05, 0.08]
    confirmations_list = [1, 2]
    target_level_sets = [
        ("0.5", "0.618"),
        ("0.382", "0.5", "0.618"),
    ]
    tp_targets = ["1.272", "1.618"]
    stop_loss_buffers = [0.002, 0.005]
    use_smart_money_flags = [True, False]
    liquidity_grab_buffers = [0.003, 0.005, 0.008]
    use_trend_following_flags = [True, False]

    points: list[ScanPoint] = []
    for (
        swing_order,
        fib_tolerance,
        confirmations,
        target_levels,
        tp_target,
        stop_loss_buffer,
        use_smart_money,
        liquidity_grab_buffer,
        use_trend_following,
    ) in itertools.product(
        swing_orders,
        fib_tolerances,
        confirmations_list,
        target_level_sets,
        tp_targets,
        stop_loss_buffers,
        use_smart_money_flags,
        liquidity_grab_buffers,
        use_trend_following_flags,
    ):
        # Skip redundant buffer variations when Smart Money is disabled.
        if not use_smart_money and liquidity_grab_buffer != liquidity_grab_buffers[0]:
            continue
        for require_structure_resonance in (False, True):
            # Structure resonance only applies when Smart Money is active.
            if require_structure_resonance and not use_smart_money:
                continue
            points.append(
                ScanPoint(
                    swing_order=swing_order,
                    fib_tolerance=fib_tolerance,
                    confirmations=confirmations,
                    target_levels=target_levels,
                    tp_target=tp_target,
                    stop_loss_buffer=stop_loss_buffer,
                    use_smart_money=use_smart_money,
                    liquidity_grab_buffer=liquidity_grab_buffer,
                    use_trend_following=use_trend_following,
                    require_structure_resonance=require_structure_resonance,
                )
            )
    return points


def ensemble_grid() -> list[ScanPoint]:
    """Return a grid focused on ensemble mode, dynamic weights and signal quality.

    The grid keeps pullback parameters fixed at a sensible baseline and sweeps
    ensemble switching logic, dynamic-weight ranges, and signal-quality
    thresholds. This lets us calibrate the new phase-7 knobs without exploding
    the full factorial search space.
    """
    base = {
        "swing_order": 2,
        "fib_tolerance": 0.03,
        "confirmations": 1,
        "target_levels": ("0.5", "0.618"),
        "tp_target": "1.618",
        "stop_loss_buffer": 0.002,
        "use_smart_money": True,
        "liquidity_grab_buffer": 0.005,
        "use_trend_following": False,
        "require_structure_resonance": False,
        "structure_resonance_buffer": 0.03,
        "use_market_regime_filter": False,
        "market_regime_confirmations": 4,
        "ensemble_trend_strength_threshold": 25.0,
        "trend_use_di_filter": False,
        "trend_use_volatility_filter": False,
        "trend_volatility_atr_multiplier": 0.5,
        "trend_use_pullback_confirmation": False,
        "trend_pullback_lookback": 5,
        "trend_pullback_buffer": 0.005,
    }

    points: list[ScanPoint] = []
    for ensemble_mode in ("regime_switch", "union", "dynamic_weight"):
        for adx_threshold in (20.0, 25.0, 30.0):
            for regime_confirmations in (2, 4, 6):
                for dynamic_weight_min, dynamic_weight_max in ((0.1, 0.5), (0.2, 0.8), (0.3, 0.7)):
                    for dynamic_weight_adx_scale in (20.0, 25.0, 30.0):
                        for use_signal_quality in (False, True):
                            for min_signal_quality in (0.0, 0.3, 0.5):
                                # Skip redundant quality variations when disabled.
                                if not use_signal_quality and min_signal_quality != 0.0:
                                    continue
                                params = dict(base)
                                params["ensemble_mode"] = ensemble_mode
                                params["ensemble_adx_threshold"] = adx_threshold
                                params["ensemble_regime_confirmations"] = regime_confirmations
                                params["ensemble_dynamic_weight_min"] = dynamic_weight_min
                                params["ensemble_dynamic_weight_max"] = dynamic_weight_max
                                params["ensemble_dynamic_weight_adx_scale"] = dynamic_weight_adx_scale
                                params["ensemble_use_signal_quality"] = use_signal_quality
                                params["ensemble_min_signal_quality"] = min_signal_quality
                                points.append(ScanPoint(**params))
    return points


def _signal_params(point: ScanPoint) -> SignalParams:
    return SignalParams(
        swing_order=point.swing_order,
        fib_tolerance=point.fib_tolerance,
        target_levels=point.target_levels,
        confirmations=point.confirmations,
        use_smart_money=point.use_smart_money,
        liquidity_grab_buffer=point.liquidity_grab_buffer,
        use_trend_following=point.use_trend_following,
        trend_strength_threshold=point.ensemble_trend_strength_threshold,
        require_structure_resonance=point.require_structure_resonance,
        structure_resonance_buffer=point.structure_resonance_buffer,
        use_market_regime_filter=point.use_market_regime_filter,
        market_regime_confirmations=point.market_regime_confirmations,
        use_signal_quality=point.ensemble_use_signal_quality,
        min_signal_quality=point.ensemble_min_signal_quality,
        quality_trend_weight=point.ensemble_quality_trend_weight,
        quality_structure_weight=point.ensemble_quality_structure_weight,
        quality_confluence_weight=point.ensemble_quality_confluence_weight,
    )


def _backtest_params(point: ScanPoint) -> BacktestParams:
    return BacktestParams(
        tp_target=point.tp_target,
        stop_loss_buffer=point.stop_loss_buffer,
    )


def _ensemble_params(point: ScanPoint) -> EnsembleParams:
    """Build ensemble parameters from a scan point."""
    pullback_params = SignalParams(
        swing_order=point.swing_order,
        fib_tolerance=point.fib_tolerance,
        target_levels=point.target_levels,
        confirmations=point.confirmations,
        use_smart_money=point.use_smart_money,
        liquidity_grab_buffer=point.liquidity_grab_buffer,
        use_trend_following=False,
        require_structure_resonance=point.require_structure_resonance,
        structure_resonance_buffer=point.structure_resonance_buffer,
        use_market_regime_filter=False,
        use_signal_quality=point.ensemble_use_signal_quality,
        min_signal_quality=point.ensemble_min_signal_quality,
        quality_trend_weight=point.ensemble_quality_trend_weight,
        quality_structure_weight=point.ensemble_quality_structure_weight,
        quality_confluence_weight=point.ensemble_quality_confluence_weight,
    )
    trend_params = TrendFollowingParams(
        swing_order=point.swing_order,
        confirmations=point.confirmations,
        trend_strength_threshold=point.ensemble_trend_strength_threshold,
        use_higher_high_breakout=False,
        require_uptrend=True,
        use_di_filter=point.trend_use_di_filter,
        use_volatility_filter=point.trend_use_volatility_filter,
        volatility_atr_multiplier=point.trend_volatility_atr_multiplier,
        use_pullback_confirmation=point.trend_use_pullback_confirmation,
        pullback_lookback=point.trend_pullback_lookback,
        pullback_buffer=point.trend_pullback_buffer,
    )
    return EnsembleParams(
        pullback_params=pullback_params,
        trend_params=trend_params,
        mode=point.ensemble_mode or "regime_switch",
        adx_threshold=point.ensemble_adx_threshold,
        regime_confirmations=point.ensemble_regime_confirmations,
        dynamic_weight_min=point.ensemble_dynamic_weight_min,
        dynamic_weight_max=point.ensemble_dynamic_weight_max,
        dynamic_weight_adx_scale=point.ensemble_dynamic_weight_adx_scale,
        use_signal_quality=point.ensemble_use_signal_quality,
        min_signal_quality=point.ensemble_min_signal_quality,
        quality_trend_weight=point.ensemble_quality_trend_weight,
        quality_structure_weight=point.ensemble_quality_structure_weight,
        quality_confluence_weight=point.ensemble_quality_confluence_weight,
    )


def evaluate_point(
    df: pd.DataFrame,
    point: ScanPoint,
) -> dict[str, Any]:
    """Run signal generation and backtest for a single parameter point."""
    if point.ensemble_mode is None:
        signal_df = generate_signals(df, _signal_params(point))
    else:
        signal_df = generate_ensemble_signals(df, _ensemble_params(point))
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
    parser.add_argument(
        "--grid",
        type=str,
        default="default",
        choices=["default", "ensemble"],
        help="Parameter grid to use (default: default).",
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

    grid: list[ScanPoint]
    if args.grid == "ensemble":
        grid = ensemble_grid()
    else:
        grid = default_grid()

    results = run_scan(df, grid=grid)
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
