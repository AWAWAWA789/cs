"""Ensemble strategy API endpoints."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.analysis.metrics import summarize
from src.api.logging import LOGGER, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period, _to_iso
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.ensemble import EnsembleParams, generate_ensemble_signals
from src.strategy.signal import SignalParams, generate_signals
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)

router = APIRouter(prefix="/ensemble", tags=["ensemble"])


# --- Request body for POST variant ----------------------------------------
# Mirrors the Query parameters of the GET endpoint so callers can pass Chinese
# ``sub_index`` values in a JSON body, avoiding URL-encoding issues with
# uvicorn's HTTP parser.

class EnsembleRunRequest(BaseModel):
    """Request body for POST /ensemble/run."""

    sub_index: str
    period: str = "1day"


def _run_single_strategy(
    df: Any,
    signal_df: Any,
    strategy_name: str,
) -> dict[str, Any]:
    """Run backtest on a signal df and return structured result."""
    result = run_backtest(signal_df, BacktestParams())
    metrics = summarize(result)
    equity_records = [
        {"timestamp": _to_iso(ts), "equity": round(float(val), 4)}
        for ts, val in result.equity_curve.items()
    ]
    return {
        "strategy_name": strategy_name,
        "metrics": metrics,
        "equity_curve": equity_records,
        "trade_count": len(result.trades),
    }


@router.get("/run")
def run_ensemble(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, Any]:
    """Run ensemble, pullback, and trend-following strategies for comparison."""
    period = _normalize_period(period)
    start = time.perf_counter()
    try:
        df = _load_ohlc(sub_index, period)

        pullback_signals = generate_signals(
            df, SignalParams(use_smart_money=True, use_trend_following=False)
        )
        trend_signals = generate_trend_following_signals(df, TrendFollowingParams())
        ensemble_signals = generate_ensemble_signals(
            df, EnsembleParams()
        )

        pullback_result = _run_single_strategy(df, pullback_signals, "pullback")
        trend_result = _run_single_strategy(df, trend_signals, "trend_following")
        ensemble_result = _run_single_strategy(df, ensemble_signals, "ensemble")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ensemble run failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/ensemble/run",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
    )
    return {
        "sub_index": sub_index,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ensemble": ensemble_result,
        "pullback": pullback_result,
        "trend_following": trend_result,
    }


@router.post("/run")
def run_ensemble_post(request: EnsembleRunRequest) -> dict[str, Any]:
    """POST version of /ensemble/run (accepts body to avoid URL encoding issues)."""
    return run_ensemble(request.sub_index, request.period)
