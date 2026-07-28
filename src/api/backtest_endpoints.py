"""Backtest endpoints for Phase 16.

Exposes the existing trend-following signal generator and backtest engine over
HTTP so the frontend can render an equity curve and trade markers.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.api.logging import get_logger, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.signal import SignalParams, generate_signals


LOGGER = get_logger("csqaq.backtest_api")
router = APIRouter(prefix="/backtest", tags=["backtest"])


def _to_iso(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _run_backtest(df: pd.DataFrame) -> dict[str, Any]:
    """Generate signals and run a long-only backtest on ``df``."""
    df_with_signals = generate_signals(
        df,
        SignalParams(
            use_smart_money=True,
            use_trend_following=True,
        ),
    )
    result = run_backtest(df_with_signals, BacktestParams())

    equity_records = []
    for ts, value in result.equity_curve.items():
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        equity_records.append({"timestamp": ts_iso, "equity": round(float(value), 4)})

    trade_records = []
    for trade in result.trades:
        trade_records.append(
            {
                "entry_index": trade.entry_index,
                "entry_time": _to_iso(trade.entry_time),
                "entry_price": round(float(trade.entry_price), 6),
                "exit_time": _to_iso(trade.exit_time),
                "exit_price": round(float(trade.exit_price), 6) if trade.exit_price is not None else None,
                "exit_reason": trade.exit_reason,
                "pnl": round(float(trade.pnl), 4),
                "return_pct": round(float(trade.return_pct), 6),
            }
        )

    final_equity = float(result.final_equity)
    initial = float(result.params.initial_capital)
    total_return = round((final_equity - initial) / initial, 6)

    return {
        "equity_curve": equity_records,
        "trades": trade_records,
        "total_return": total_return,
        "final_equity": round(final_equity, 4),
        "trade_count": len(trade_records),
    }


@router.get("/equity")
def equity(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, Any]:
    """Return equity curve and simulated trades for the price-action strategy."""
    period = _normalize_period(period)
    start = time.perf_counter()
    try:
        df = _load_ohlc(sub_index, period)
        payload = _run_backtest(df)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(
            LOGGER,
            endpoint="/backtest/equity",
            sub_index=sub_index,
            period=period,
            latency_ms=latency_ms,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/backtest/equity",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
        extra={"trade_count": payload["trade_count"]},
    )
    return {
        "sub_index": sub_index,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
