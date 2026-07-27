"""Parameter sensitivity heatmaps for the price-action strategy.

Produces 2D heatmaps of performance metrics across two parameter dimensions
while keeping all other parameters fixed. This helps identify stable parameter
regions and avoid overfitting to a single optimum.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis.metrics import summarize
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.signal import SignalParams, generate_signals


def evaluate_parameter_pair(
    df: pd.DataFrame,
    param_a_name: str,
    param_a_value: Any,
    param_b_name: str,
    param_b_value: Any,
    base_signal_params: dict[str, Any] | None = None,
    base_backtest_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run signal generation and backtest for a single parameter pair."""
    signal_kwargs = dict(base_signal_params or {})
    signal_kwargs[param_a_name] = param_a_value
    signal_kwargs[param_b_name] = param_b_value

    backtest_kwargs = dict(base_backtest_params or {})

    signal_df = generate_signals(df, SignalParams(**signal_kwargs))
    signal_count = int(signal_df["signal_long"].sum())
    result = run_backtest(signal_df, BacktestParams(**backtest_kwargs))
    metrics = summarize(result)
    return {
        "signal_count": signal_count,
        "metrics": metrics,
    }


def parameter_heatmap(
    df: pd.DataFrame,
    param_a_name: str,
    param_a_values: list[Any],
    param_b_name: str,
    param_b_values: list[Any],
    metric: str = "total_return",
    base_signal_params: dict[str, Any] | None = None,
    base_backtest_params: dict[str, Any] | None = None,
    title: str = "Parameter Heatmap",
    output_path: str | Path | None = None,
) -> tuple[plt.Figure, pd.DataFrame]:
    """Draw a 2D heatmap of ``metric`` across two parameter axes.

    Args:
        df: OHLC DataFrame.
        param_a_name: First parameter name (must be valid for ``SignalParams``
            or ``BacktestParams``).
        param_a_values: Values for the first parameter; used as rows.
        param_b_name: Second parameter name.
        param_b_values: Values for the second parameter; used as columns.
        metric: Metric from ``summarize`` output to visualize.
        base_signal_params: Fixed signal parameters.
        base_backtest_params: Fixed backtest parameters.
        title: Chart title.
        output_path: Optional path to save the PNG.

    Returns:
        The matplotlib figure and the raw results DataFrame.
    """
    base_signal_params = base_signal_params or {}
    base_backtest_params = base_backtest_params or {}

    # Determine which parameter belongs to which config object.
    signal_param_names = {
        "swing_order",
        "fib_tolerance",
        "target_levels",
        "confirmations",
        "use_smart_money",
        "liquidity_grab_buffer",
        "use_trend_following",
    }

    rows = []
    for a_value in param_a_values:
        row = []
        for b_value in param_b_values:
            signal_kwargs = dict(base_signal_params)
            backtest_kwargs = dict(base_backtest_params)

            if param_a_name in signal_param_names:
                signal_kwargs[param_a_name] = a_value
            else:
                backtest_kwargs[param_a_name] = a_value

            if param_b_name in signal_param_names:
                signal_kwargs[param_b_name] = b_value
            else:
                backtest_kwargs[param_b_name] = b_value

            signal_df = generate_signals(df, SignalParams(**signal_kwargs))
            result = run_backtest(signal_df, BacktestParams(**backtest_kwargs))
            metrics = summarize(result)
            row.append(metrics[metric])
        rows.append(row)

    matrix = np.array(rows)
    labels_a = [str(v) for v in param_a_values]
    labels_b = [str(v) for v in param_b_values]

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", interpolation="nearest")

    ax.set_xticks(np.arange(len(labels_b)))
    ax.set_yticks(np.arange(len(labels_a)))
    ax.set_xticklabels(labels_b)
    ax.set_yticklabels(labels_a)
    ax.set_xlabel(param_b_name)
    ax.set_ylabel(param_a_name)
    ax.set_title(f"{title} | {metric}")

    # Annotate cells.
    for i in range(len(labels_a)):
        for j in range(len(labels_b)):
            value = matrix[i, j]
            text = f"{value:.2%}" if metric in {"total_return", "max_drawdown", "win_rate", "avg_trade_return"} else f"{value:.3f}"
            ax.text(
                j,
                i,
                text,
                ha="center",
                va="center",
                color="black",
                fontsize=8,
            )

    fig.colorbar(im, ax=ax, label=metric)
    fig.tight_layout()

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150)

    results_df = pd.DataFrame(
        matrix,
        index=pd.Index(labels_a, name=param_a_name),
        columns=pd.Index(labels_b, name=param_b_name),
    )
    return fig, results_df


def plot_metric_heatmaps(
    df: pd.DataFrame,
    param_a_name: str,
    param_a_values: list[Any],
    param_b_name: str,
    param_b_values: list[Any],
    base_signal_params: dict[str, Any] | None = None,
    base_backtest_params: dict[str, Any] | None = None,
    title_prefix: str = "",
    output_dir: str | Path = "reports",
) -> dict[str, Path]:
    """Generate heatmaps for total_return, sharpe_ratio and max_drawdown.

    Returns a mapping from metric name to saved PNG path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = ["total_return", "sharpe_ratio", "max_drawdown"]
    paths: dict[str, Path] = {}

    for metric in metrics:
        safe_metric = metric.replace("/", "_")
        output_path = output_dir / f"{title_prefix}_{param_a_name}_vs_{param_b_name}_{safe_metric}.png"
        _, _ = parameter_heatmap(
            df,
            param_a_name=param_a_name,
            param_a_values=param_a_values,
            param_b_name=param_b_name,
            param_b_values=param_b_values,
            metric=metric,
            base_signal_params=base_signal_params,
            base_backtest_params=base_backtest_params,
            title=f"{title_prefix} {metric}",
            output_path=output_path,
        )
        paths[metric] = output_path

    return paths


def main() -> None:
    """CLI entry point for generating parameter heatmaps."""
    import argparse

    from src.api.client import CSQAQClient
    from src.config import Settings
    from src.data.pipeline import load_or_fetch

    parser = argparse.ArgumentParser(
        description="Generate parameter sensitivity heatmaps."
    )
    parser.add_argument(
        "--sub-index",
        dest="sub_index_name",
        default="手套",
        help="Sub-index name (default: 手套).",
    )
    parser.add_argument(
        "--period",
        default="1day",
        help="K-line period (default: 1day).",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory to write PNGs (default: reports).",
    )
    parser.add_argument(
        "--confirmations",
        type=int,
        nargs="+",
        default=[1, 2, 3],
        help="List of confirmations values to scan (default: 1 2 3).",
    )
    parser.add_argument(
        "--tp-targets",
        dest="tp_targets",
        nargs="+",
        default=["1.272", "1.618", "2.0"],
        help="List of tp_target values to scan (default: 1.272 1.618 2.0).",
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

    paths = plot_metric_heatmaps(
        df,
        param_a_name="confirmations",
        param_a_values=args.confirmations,
        param_b_name="tp_target",
        param_b_values=args.tp_targets,
        base_signal_params={
            "swing_order": 2,
            "fib_tolerance": 0.03,
            "use_smart_money": True,
            "use_trend_following": False,
        },
        base_backtest_params={"stop_loss_buffer": 0.002},
        title_prefix=f"{args.sub_index_name}_{args.period}",
        output_dir=args.output_dir,
    )

    print("Heatmaps saved:")
    for metric, path in paths.items():
        print(f"  {metric}: {path}")


if __name__ == "__main__":
    main()
