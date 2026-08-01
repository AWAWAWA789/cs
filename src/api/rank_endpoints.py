"""Rank (排行榜/系列) API endpoints.

Wraps CSQAQ's 4 rank-related endpoints with correct API URLs:
- info/get_rank_list → POST /rank/list  (涨跌排行榜)
- info/get_page_list → POST /rank/items (饰品列表)
- info/get_series_list → POST /rank/series (热门系列)
- info/get_series_detail → GET /rank/series/{series_id} (系列详情)

All endpoints use a 90-second TTL in-memory cache to reduce API calls
and avoid hitting the 1-request-per-second rate limit.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.cache import RANK_CACHE
from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger
from src.config import Settings

LOGGER = get_logger("csqaq.rank_api")

router = APIRouter(prefix="/rank", tags=["rank"])

# ── Sort mapping: frontend sort key → CSQAQ filter "排序" value ──
_SORT_MAP: dict[str, str] = {
    "chg_1_desc": "价格_价格上升(百分比)_近1天",
    "chg_1_asc": "价格_价格下降(百分比)_近1天",
    "chg_7_desc": "价格_价格上升(百分比)_近7天",
    "chg_30_desc": "价格_价格上升(百分比)_近1个月",
    "sell_num_desc": "成交量_Steam日成交量",
}

# ── Type filter mapping: frontend type → CSQAQ "类型" value ──
_TYPE_MAP: dict[str, str] = {
    "刀": "不限_匕首",
    "手套": "不限_手套",
    "步枪": "不限_步枪",
    "手枪": "不限_手枪",
    "狙击枪": "不限_步枪",
    "微型冲锋枪": "不限_微型冲锋枪",
    "重型武器": "不限_微型冲锋枪",
}


def _get_client() -> CSQAQClient:
    """Create a CSQAQ client from current settings."""
    return CSQAQClient(Settings())


def _handle_api_error(exc: CSQAQAPIError) -> None:
    """将 CSQAQ API 错误转换为用户友好的 HTTP 异常。"""
    if exc.code == 401:
        raise HTTPException(
            status_code=503,
            detail=f"CSQAQ API 授权失败: {exc}",
        ) from exc
    if exc.code == 429:
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁: {exc}",
        ) from exc
    raise HTTPException(
        status_code=502,
        detail=f"CSQAQ API 错误(code={exc.code}): {exc}",
    ) from exc


# ── Request Models ─────────────────────────────────────────


class RankListRequest(BaseModel):
    """涨跌排行榜请求体。"""
    sort: str = "chg_1_desc"
    page_index: int = 1
    page_size: int = 20


class ItemsRequest(BaseModel):
    """饰品列表（带筛选）请求体。"""
    type: str | None = None
    quality: str | None = None
    category: str | None = None
    wear: str | None = None
    search: str | None = None
    page_index: int = 1
    page_size: int = 20


# ── Endpoints ──────────────────────────────────────────────


@router.post("/list")
async def get_rank_list(req: RankListRequest) -> Any:
    """涨跌排行榜。

    封装 CSQAQ ``/api/v1/info/get_rank_list``，支持按涨跌幅等多种排序字段分页查询。
    结果缓存 90 秒。
    """
    cache_key = f"list:{req.sort}:{req.page_index}:{req.page_size}"
    cached = RANK_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("rank_list (cached) sort=%s page_index=%d page_size=%d", req.sort, req.page_index, req.page_size)
        return cached

    LOGGER.info("rank_list sort=%s page_index=%d page_size=%d", req.sort, req.page_index, req.page_size)

    # Map frontend sort key to CSQAQ filter format
    sort_value = _SORT_MAP.get(req.sort, "价格_价格上升(百分比)_近1天")

    client = _get_client()
    try:
        result = await asyncio.to_thread(client.post, "/info/get_rank_list", json={
            "page_index": req.page_index,
            "page_size": req.page_size,
            "show_recently_price": True,
            "filter": {
                "排序": [sort_value],
            },
        })
        RANK_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/items")
async def get_rank_items(req: ItemsRequest) -> Any:
    """饰品列表（支持多维度筛选）。

    封装 CSQAQ ``/api/v1/info/get_page_list``，可按类型、品质、分类、磨损、
    关键词等条件筛选并分页返回饰品列表。结果缓存 90 秒。
    """
    cache_key = f"items:{req.type}:{req.quality}:{req.category}:{req.wear}:{req.search}:{req.page_index}:{req.page_size}"
    cached = RANK_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("rank_items (cached) type=%s quality=%s page_index=%d", req.type, req.quality, req.page_index)
        return cached

    LOGGER.info(
        "rank_items type=%s quality=%s category=%s wear=%s search=%s page_index=%d page_size=%d",
        req.type, req.quality, req.category, req.wear, req.search, req.page_index, req.page_size,
    )

    # Build CSQAQ filter object with Chinese keys
    filter_obj: dict[str, list[str]] = {}
    if req.type:
        mapped_type = _TYPE_MAP.get(req.type)
        if mapped_type:
            filter_obj["类型"] = [mapped_type]
    if req.quality:
        filter_obj["品质"] = [req.quality]
    if req.category:
        filter_obj["类别"] = [req.category]
    if req.wear:
        filter_obj["磨损"] = [req.wear]

    body: dict[str, Any] = {
        "page_index": req.page_index,
        "page_size": req.page_size,
    }
    if req.search:
        body["search"] = req.search
    if filter_obj:
        body["filter"] = filter_obj

    client = _get_client()
    try:
        result = await asyncio.to_thread(client.post, "/info/get_page_list", json=body)
        RANK_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/series")
async def get_series_list() -> Any:
    """热门系列列表。

    封装 CSQAQ ``/api/v1/info/get_series_list`` (POST)。结果缓存 90 秒。
    """
    cache_key = "series:list"
    cached = RANK_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("rank_series_list (cached)")
        return cached

    LOGGER.info("rank_series_list")
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.post, "/info/get_series_list")
        RANK_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/series/{series_id}")
async def get_series_detail(series_id: str) -> Any:
    """系列详情。

    封装 CSQAQ ``/api/v1/info/get_series_detail?series_id={series_id}`` (GET)。
    结果缓存 90 秒。
    """
    cache_key = f"series:detail:{series_id}"
    cached = RANK_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("rank_series_detail (cached) series_id=%s", series_id)
        return cached

    LOGGER.info("rank_series_detail series_id=%s", series_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.get, "/info/get_series_detail", params={"series_id": series_id})
        RANK_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)
