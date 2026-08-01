"""Trend scan API endpoints with async task execution."""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.analysis.metrics import summarize
from src.api.logging import LOGGER, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period
from src.api.task_queue import TASK_QUEUE, TaskQueue
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)

router = APIRouter(prefix="/trend-scan", tags=["trend-scan"])


class ScanRequest(BaseModel):
    sub_index: str
    period: str = "1day"


def _param_grid() -> list[dict[str, Any]]:
    """Generate the full parameter grid for trend scan."""
    combos = []
    for swing_order, confirmations, trend_threshold, use_di, use_vol, vol_mult, use_pb, pb_lookback, pb_buffer in itertools.product(
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
        combos.append({
            "swing_order": swing_order,
            "confirmations": confirmations,
            "trend_strength_threshold": trend_threshold,
            "use_di_filter": use_di,
            "use_volatility_filter": use_vol,
            "volatility_atr_multiplier": vol_mult,
            "use_pullback_confirmation": use_pb,
            "pullback_lookback": pb_lookback,
            "pullback_buffer": pb_buffer,
        })
    return combos


def _run_scan(
    sub_index: str,
    period: str,
    progress_cb,
) -> dict[str, Any]:
    """Execute the full parameter scan. Runs in a background thread."""
    df, _ = _load_ohlc(sub_index, period)
    grid = _param_grid()
    total = len(grid)
    results: list[dict[str, Any]] = []

    for i, params_dict in enumerate(grid):
        params = TrendFollowingParams(
            swing_order=params_dict["swing_order"],
            confirmations=params_dict["confirmations"],
            trend_strength_threshold=params_dict["trend_strength_threshold"],
            use_di_filter=params_dict["use_di_filter"],
            use_volatility_filter=params_dict["use_volatility_filter"],
            volatility_atr_multiplier=params_dict["volatility_atr_multiplier"],
            use_pullback_confirmation=params_dict["use_pullback_confirmation"],
            pullback_lookback=params_dict["pullback_lookback"],
            pullback_buffer=params_dict["pullback_buffer"],
        )
        try:
            signal_df = generate_trend_following_signals(df, params)
            bt_result = run_backtest(signal_df, BacktestParams())
            metrics = summarize(bt_result)
            results.append({
                "params": params_dict,
                "total_return": metrics["total_return"],
                "max_drawdown": metrics["max_drawdown"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "win_rate": metrics["win_rate"],
                "total_trades": metrics["total_trades"],
            })
        except Exception:
            # Skip parameter combinations that error out
            pass

        progress_cb((i + 1) / total, f"扫描进度 {i + 1}/{total}")

    results.sort(key=lambda x: x["total_return"], reverse=True)
    non_negative = sum(1 for r in results if r["total_return"] >= 0)

    return {
        "sub_index": sub_index,
        "period": period,
        "total_combinations": total,
        "top_10": results[:10],
        "bottom_10": results[-10:],
        "non_negative_count": non_negative,
        "all_results": results,
    }


@router.post("/start")
def start_scan(request: ScanRequest) -> dict[str, str]:
    """Start an async trend scan task. Returns task_id for polling."""
    # Validate period early
    _normalize_period(request.period)

    task_id = TASK_QUEUE.create(
        lambda progress_cb: _run_scan(request.sub_index, request.period, progress_cb)
    )
    TASK_QUEUE.run(task_id)

    log_request(
        LOGGER,
        endpoint="/trend-scan/start",
        sub_index=request.sub_index,
        period=request.period,
        extra={"task_id": task_id},
    )
    return {"task_id": task_id}


@router.get("/status/{task_id}")
def get_status(task_id: str) -> dict[str, Any]:
    """Get the status of a trend scan task."""
    info = TASK_QUEUE.get(task_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return info.to_dict()
