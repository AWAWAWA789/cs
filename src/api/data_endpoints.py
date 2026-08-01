"""Data management API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.logging import LOGGER, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period

router = APIRouter(prefix="/data", tags=["data"])

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"

_PERIOD_SUFFIX = {"1hour": "1h", "4hour": "4h", "1day": "1d", "7day": "7d"}


class RefreshRequest(BaseModel):
    sub_index: str
    period: str = "1day"


@router.get("/cache-status")
def cache_status() -> dict[str, Any]:
    """List all cached parquet files with metadata."""
    if not CACHE_DIR.exists():
        return {
            "cache_dir": str(CACHE_DIR),
            "total_files": 0,
            "total_size_bytes": 0,
            "files": [],
        }

    files = []
    total_size = 0
    for path in sorted(CACHE_DIR.glob("*.parquet"), key=lambda p: p.name):
        stat = path.stat()
        total_size += stat.st_size

        bar_count = None
        try:
            df = pd.read_parquet(path, columns=["close"])
            bar_count = len(df)
        except Exception:
            pass

        files.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "bar_count": bar_count,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    log_request(LOGGER, endpoint="/data/cache-status", extra={"file_count": len(files)})
    return {
        "cache_dir": str(CACHE_DIR),
        "total_files": len(files),
        "total_size_bytes": total_size,
        "files": files,
    }


@router.post("/refresh")
def refresh_data(request: RefreshRequest) -> dict[str, Any]:
    """Force refresh cached data for a sub-index and period."""
    period = _normalize_period(request.period)
    try:
        df = _load_ohlc(request.sub_index, period, force_refresh=True)
        bar_count = len(df)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Data refresh failed: {exc}") from exc

    log_request(
        LOGGER,
        endpoint="/data/refresh",
        sub_index=request.sub_index,
        period=period,
        extra={"bar_count": bar_count},
    )
    return {
        "sub_index": request.sub_index,
        "period": period,
        "success": True,
        "bar_count": bar_count,
        "message": f"已刷新 {bar_count} 根K线数据",
    }
