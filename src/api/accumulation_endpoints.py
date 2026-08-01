"""库存吸货分析 API endpoints。

提供吸货检测分析能力和一次性数据预热初始化（问题9）。

端点：
- POST /accumulation/analyze  — 对指定标的执行吸货分析
- POST /accumulation/scan     — 扫描多个标的的吸货评分排行
- POST /accumulation/init     — 一次性预热初始化（问题9）
- GET  /accumulation/status   — 查看初始化状态
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.cache import TTLCache
from src.api.logging import get_logger, log_request
from src.api.monitoring import record_request
from src.config import Settings
from src.data.cache import cache_file_path, load_cached
from src.data.pipeline import filter_from_2024
from src.scenario_engine.accumulation_detector import detect_accumulation

LOGGER = get_logger("csqaq.accumulation_api")

router = APIRouter(prefix="/accumulation", tags=["accumulation"])

# 分析结果缓存（5 分钟）
_ANALYSIS_CACHE = TTLCache(ttl_seconds=300.0)

# 初始化状态（进程级）
_INIT_STATE: dict[str, Any] = {
    "initialized": False,
    "last_run": None,
    "items_cached": 0,
    "errors": [],
}

# 支持的周期
_SUPPORTED_PERIODS = {"1hour", "4hour", "1day", "7day"}


# ── Request Models ─────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    """吸货分析请求体。"""
    sub_index: str = Field(..., description="子指数名称")
    period: str = Field("1day", description="K 线周期")


class ScanRequest(BaseModel):
    """吸货扫描请求体。"""
    sub_indices: list[str] = Field(..., description="要扫描的子指数列表")
    period: str = Field("1day", description="K 线周期")
    top_n: int = Field(10, ge=1, le=50, description="返回前 N 个")


class InitRequest(BaseModel):
    """一次性预热初始化请求体。"""
    sub_indices: list[str] | None = Field(
        None, description="要预热的子指数列表，为空则使用默认列表"
    )
    periods: list[str] | None = Field(
        None, description="要预热的周期列表，为空则使用全部支持周期"
    )


# ── Endpoints ──────────────────────────────────────────────


def _load_ohlc_for_accumulation(
    sub_index: str, period: str
) -> tuple[pd.DataFrame | None, str]:
    """加载 OHLC 数据用于吸货分析。

    优先从磁盘缓存加载，不触发 API 请求（避免阻塞）。
    返回 (df, data_source)，df 为 None 表示无数据。
    """
    settings = Settings()
    cache_path = cache_file_path(sub_index, period, settings.cache_path)

    df = load_cached(cache_path)
    if df is None:
        return None, "no_cache"

    df = filter_from_2024(df)
    if len(df) < 10:
        return None, "insufficient"

    return df, "cached"


@router.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """对指定标的执行吸货分析。

    基于本地缓存的 OHLCV 数据，计算吸货特征并输出评分。
    结果缓存 5 分钟。
    """
    start = time.perf_counter()
    period = req.period
    if period not in _SUPPORTED_PERIODS:
        raise HTTPException(status_code=400, detail=f"不支持的周期: {period}")

    cache_key = f"analyze:{req.sub_index}:{period}"
    cached = _ANALYSIS_CACHE.get(cache_key)
    if cached is not None:
        log_request(
            LOGGER,
            endpoint="/accumulation/analyze",
            sub_index=req.sub_index,
            period=period,
            cached=True,
        )
        return {**cached, "cached": True}

    df, data_source = _load_ohlc_for_accumulation(req.sub_index, period)
    if df is None:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request("/accumulation/analyze", latency_ms, error=False)
        return {
            "sub_index": req.sub_index,
            "period": period,
            "accumulation_score": 0.0,
            "phase": "neutral",
            "signals": {},
            "features": {},
            "data_source": data_source,
            "description": "无可用数据，请先执行数据初始化",
        }

    result = detect_accumulation(df, req.sub_index, period)
    result["data_source"] = data_source

    _ANALYSIS_CACHE.set(cache_key, result)

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/accumulation/analyze",
        sub_index=req.sub_index,
        period=period,
        latency_ms=latency_ms,
    )
    record_request("/accumulation/analyze", latency_ms, error=False)
    return {**result, "cached": False}


@router.post("/scan")
def scan(req: ScanRequest) -> dict[str, Any]:
    """扫描多个标的的吸货评分，返回排行。

    对每个子指数执行吸货分析，按评分排序返回 top_n。
    """
    start = time.perf_counter()
    results: list[dict[str, Any]] = []

    for sub_index in req.sub_indices:
        df, data_source = _load_ohlc_for_accumulation(sub_index, req.period)
        if df is None:
            results.append({
                "sub_index": sub_index,
                "accumulation_score": 0.0,
                "phase": "neutral",
                "data_source": data_source,
            })
            continue

        result = detect_accumulation(df, sub_index, req.period)
        results.append({
            "sub_index": sub_index,
            "accumulation_score": result["accumulation_score"],
            "phase": result["phase"],
            "duration_bars": result.get("duration_bars", 0),
            "data_source": "cached",
        })

    # 按吸货评分排序
    results.sort(key=lambda x: x["accumulation_score"], reverse=True)
    top = results[: req.top_n]

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/accumulation/scan", latency_ms, error=False)

    return {
        "period": req.period,
        "total_scanned": len(req.sub_indices),
        "top_results": top,
        "latency_ms": round(latency_ms, 2),
    }


@router.post("/init")
def init(req: InitRequest) -> dict[str, Any]:
    """一次性数据预热初始化（问题9）。

    预热本地缓存的 OHLC 数据到内存层，使后续所有功能（搜索、吸货分析、
    情景分析等）无需临时加载。仅加载已有缓存文件，不触发 API 请求。

    如果需要刷新数据，请先通过 /data/refresh 接口拉取最新数据。
    """
    start = time.perf_counter()
    settings = Settings()
    errors: list[str] = []
    items_cached = 0

    # 默认子指数列表
    sub_indices = req.sub_indices or [settings.sub_index_name]
    periods = req.periods or list(_SUPPORTED_PERIODS)

    for sub_index in sub_indices:
        for period in periods:
            if period not in _SUPPORTED_PERIODS:
                continue
            try:
                cache_path = cache_file_path(sub_index, period, settings.cache_path)
                df = load_cached(cache_path)
                if df is not None:
                    items_cached += 1
            except Exception as exc:
                errors.append(f"{sub_index}/{period}: {exc}")
                LOGGER.warning("init error for %s/%s: %s", sub_index, period, exc)

    _INIT_STATE["initialized"] = True
    _INIT_STATE["last_run"] = datetime.now(timezone.utc).isoformat()
    _INIT_STATE["items_cached"] = items_cached
    _INIT_STATE["errors"] = errors

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/accumulation/init", latency_ms, error=False)

    LOGGER.info(
        "accumulation init complete: %d items cached in %.0fms",
        items_cached,
        latency_ms,
    )

    return {
        "initialized": True,
        "items_cached": items_cached,
        "errors": errors,
        "latency_ms": round(latency_ms, 2),
        "message": f"已预热 {items_cached} 个数据项" + (f"，{len(errors)} 个错误" if errors else ""),
    }


@router.get("/status")
def init_status() -> dict[str, Any]:
    """查看初始化状态。"""
    return {
        "initialized": _INIT_STATE["initialized"],
        "last_run": _INIT_STATE["last_run"],
        "items_cached": _INIT_STATE["items_cached"],
        "errors": _INIT_STATE["errors"],
    }
