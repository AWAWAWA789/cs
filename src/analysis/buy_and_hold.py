"""买入持有基准计算。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_buy_and_hold(
    df: pd.DataFrame, risk_free_rate: float = 0.0
) -> dict[str, Any]:
    """计算从第一根 K 线收盘买入、最后一根收盘卖出的基准收益。

    Args:
        df: 包含 open/high/low/close 的 DataFrame。
        risk_free_rate: 年化无风险利率，按 0 简化处理。

    Returns:
        包含 total_return、max_drawdown、sharpe、start_price、end_price 的字典。
    """
    if len(df) < 2:
        return {
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "start_price": float(df["close"].iloc[0]) if len(df) else 0.0,
            "end_price": float(df["close"].iloc[-1]) if len(df) else 0.0,
        }

    prices = df["close"].values
    start_price = float(prices[0])
    end_price = float(prices[-1])
    total_return = (end_price - start_price) / start_price

    cummax = np.maximum.accumulate(prices)
    drawdowns = (prices - cummax) / cummax
    max_drawdown = float(np.min(drawdowns))

    returns = np.diff(prices) / prices[:-1]
    mean_return = float(np.mean(returns))
    std_return = float(np.std(returns, ddof=0))
    sharpe = 0.0
    if std_return > 0:
        sharpe = float(
            (mean_return - risk_free_rate) / std_return * np.sqrt(len(returns))
        )

    return {
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "sharpe": round(sharpe, 6),
        "start_price": round(start_price, 6),
        "end_price": round(end_price, 6),
    }
