"""Visualization helpers for backtest reports.

Produces static charts using matplotlib so that reports can be generated in
both local and TRAE environments without a display. All functions accept a
``BacktestResult`` plus the original signal DataFrame and write PNG files to a
configurable output directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from src.backtest.engine import BacktestResult, Trade


def _timestamp_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Return a DatetimeIndex for plotting.

    If ``df`` already has a DatetimeIndex, return it. Otherwise try the
    ``timestamp`` column. Falls back to a RangeIndex if no timestamps exist.
    """
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index
    if "timestamp" in df.columns:
        return pd.DatetimeIndex(df["timestamp"])
    return pd.DatetimeIndex(df.index)


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _signal_source_color(reason: str) -> str:
    """Return a color for the signal based on its source prefix."""
    if reason.startswith("ensemble_"):
        return "purple"
    if reason.startswith("trend_following_"):
        return "green"
    if reason.startswith("smart_money_"):
        return "orange"
    return "blue"


def _signal_source_label(reason: str) -> str:
    """Return a human-readable label for the signal source."""
    if reason.startswith("ensemble_"):
        return "ensemble"
    if reason.startswith("trend_following_"):
        return "trend_following"
    if reason.startswith("smart_money_"):
        return "smart_money"
    return "pullback"


def plot_equity_curve(
    result: BacktestResult,
    title: str = "Equity Curve",
    output_path: Optional[str | Path] = None,
) -> plt.Figure:
    """Plot the strategy equity curve.

    Args:
        result: Backtest result containing ``equity_curve``.
        title: Chart title.
        output_path: Optional path to save the PNG.

    Returns:
        The matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    equity = result.equity_curve
    ax.plot(equity.index, equity, label="Strategy", color="#1f77b4", linewidth=1.5)

    initial = equity.iloc[0]
    final = equity.iloc[-1]
    total_return = final / initial - 1

    ax.axhline(initial, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.set_title(f"{title} | Return: {_format_percent(total_return)}")
    ax.set_xlabel("Time")
    ax.set_ylabel("Equity")
    ax.legend()
    ax.grid(True, alpha=0.3)

    if isinstance(equity.index, pd.DatetimeIndex):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()

    fig.tight_layout()

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150)

    return fig


def _plot_candlesticks(ax: plt.Axes, df: pd.DataFrame, ts_index: pd.DatetimeIndex) -> None:
    """Draw OHLC candlesticks on the given axes using integer x positions."""
    n = len(df)
    width = 0.6
    open_ = df["open"].values
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    for i in range(n):
        color = "#26a69a" if close[i] >= open_[i] else "#ef5350"
        lower = min(open_[i], close[i])
        upper = max(open_[i], close[i])
        height = upper - lower

        # Body
        rect = plt.Rectangle((i - width / 2, lower), width, height, color=color)
        ax.add_patch(rect)
        # Wick
        ax.plot([i, i], [low[i], high[i]], color=color, linewidth=0.8)

    ax.set_xlim(-1, n)
    ax.set_ylabel("Price")


def plot_price_with_trades(
    df: pd.DataFrame,
    result: BacktestResult,
    title: str = "Price & Trades",
    output_path: Optional[str | Path] = None,
) -> plt.Figure:
    """Plot candlesticks with signal, entry and exit markers.

    Args:
        df: Signal DataFrame (OHLC + ``signal_long``, ``signal_reason``).
        result: Backtest result containing trades.
        title: Chart title.
        output_path: Optional path to save the PNG.

    Returns:
        The matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=(14, 7))
    ts_index = _timestamp_index(df)
    _plot_candlesticks(ax, df, ts_index)

    n = len(df)
    signal_indices = df.index[df["signal_long"]].tolist()
    source_positions: dict[str, list[int]] = {}
    for idx in signal_indices:
        pos = int(df.index.get_loc(idx))
        reason = df["signal_reason"].iloc[pos] if "signal_reason" in df.columns else ""
        label = _signal_source_label(reason)
        source_positions.setdefault(label, []).append(pos)

    for label, positions in source_positions.items():
        if not positions:
            continue
        color = _signal_source_color(f"{label}_")
        ax.scatter(
            positions,
            df["low"].iloc[positions],
            marker="^",
            color=color,
            s=60,
            zorder=5,
            label=label,
        )

    for trade in result.trades:
        entry_pos = int(df.index.get_loc(trade.entry_index))
        exit_pos = int(df.index.get_loc(trade.exit_index))

        ax.scatter(
            entry_pos,
            trade.entry_price,
            marker="v",
            color="green",
            s=100,
            zorder=6,
            label="Entry" if trade == result.trades[0] else "",
        )
        ax.scatter(
            exit_pos,
            trade.exit_price,
            marker="x",
            color="red" if trade.pnl < 0 else "green",
            s=100,
            zorder=6,
            label="Exit" if trade == result.trades[0] else "",
        )
        ax.plot(
            [entry_pos, exit_pos],
            [trade.entry_price, trade.exit_price],
            color="green" if trade.pnl >= 0 else "red",
            linewidth=1,
            alpha=0.6,
        )

        # Draw stop-loss and take-profit levels across the trade duration.
        if trade.stop_loss is not None and trade.take_profit is not None:
            ax.plot(
                [entry_pos, exit_pos],
                [trade.stop_loss, trade.stop_loss],
                color="red",
                linestyle="--",
                linewidth=0.8,
                alpha=0.5,
                label="SL" if trade == result.trades[0] else "",
            )
            ax.plot(
                [entry_pos, exit_pos],
                [trade.take_profit, trade.take_profit],
                color="green",
                linestyle="--",
                linewidth=0.8,
                alpha=0.5,
                label="TP" if trade == result.trades[0] else "",
            )

    # Mark swing highs and lows when columns are present.
    if "swing_high" in df.columns:
        swing_high_indices = df.index[df["swing_high"]].tolist()
        for idx in swing_high_indices:
            pos = int(df.index.get_loc(idx))
            ax.scatter(
                pos,
                df["high"].iloc[pos],
                marker="*",
                color="orange",
                s=40,
                zorder=4,
                label="Swing High" if idx == swing_high_indices[0] else "",
            )
    if "swing_low" in df.columns:
        swing_low_indices = df.index[df["swing_low"]].tolist()
        for idx in swing_low_indices:
            pos = int(df.index.get_loc(idx))
            ax.scatter(
                pos,
                df["low"].iloc[pos],
                marker="*",
                color="purple",
                s=40,
                zorder=4,
                label="Swing Low" if idx == swing_low_indices[0] else "",
            )

    ax.set_title(title)
    ax.set_xlabel("Bar")
    ax.grid(True, alpha=0.3)

    # Use timestamp labels on the x-axis when available.
    if len(ts_index) == n:
        step = max(1, n // 8)
        ax.set_xticks(range(0, n, step))
        ax.set_xticklabels(
            [ts_index[i].strftime("%Y-%m-%d") for i in range(0, n, step)],
            rotation=30,
            ha="right",
        )

    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys())

    fig.tight_layout()

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150)

    return fig


def generate_report_plots(
    df: pd.DataFrame,
    result: BacktestResult,
    output_dir: str | Path,
    prefix: str = "",
) -> dict[str, Path]:
    """Generate the standard set of report charts.

    Args:
        df: Signal DataFrame.
        result: Backtest result.
        output_dir: Directory where PNG files will be written.
        prefix: Optional filename prefix (e.g. ``glove_1d_``).

    Returns:
        Mapping of plot name to saved file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    equity_path = output_dir / f"{prefix}equity_curve.png"
    trades_path = output_dir / f"{prefix}trades.png"

    plot_equity_curve(result, title=f"{prefix}Equity Curve", output_path=equity_path)
    plot_price_with_trades(df, result, title=f"{prefix}Price & Trades", output_path=trades_path)

    return {"equity_curve": equity_path, "trades": trades_path}
