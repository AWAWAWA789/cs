"""Item (饰品) API endpoints for Phase 20.

Wraps CSQAQ's 7 item-related endpoints:
- search/suggest → POST /item/search
- goods/get_all_goods_id → GET /item/all
- info/good → GET /item/detail
- info/chart → POST /item/chart
- info/simple/chartAll → POST /item/chart-all
- info/good/statistic → GET /item/supply
- goods/getPriceByMarketHashName → POST /item/batch-price

Most endpoints use a 60-second TTL in-memory cache to reduce API calls
and avoid hitting the 1-request-per-second rate limit. Search uses a
shorter 30-second TTL.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.cache import ITEM_CACHE, TTLCache
from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger
from src.config import Settings

LOGGER = get_logger("csqaq.item_api")

router = APIRouter(prefix="/item", tags=["item"])

# Short-TTL cache for search suggestions (30s).
_SEARCH_CACHE = TTLCache(ttl_seconds=30.0)


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


class SearchRequest(BaseModel):
    """搜索请求体。"""
    text: str


class ChartRequest(BaseModel):
    """单品图表请求体。"""
    good_id: str
    key: str = "sell_price"
    platform: int = 1
    period: int = 30
    style: str = "all_style"


class ChartAllRequest(BaseModel):
    """全量图表请求体。"""
    good_id: str


class BatchPriceRequest(BaseModel):
    """批量价格请求体。"""
    market_hash_names: list[str]


# ── Endpoints ──────────────────────────────────────────────


def _normalize_search_result(raw: Any) -> dict[str, Any]:
    """将 CSQAQ /search/suggest 响应归一化为 ``{data: [{good_id, name}]}``。

    CSQAQ 该端点实际返回 ``{code, msg, data: [{id, value}]}``（``id`` 即
    good_id，``value`` 即中文名）。但本项目前端类型与其他端点（rank/page
    list 等）统一使用 ``good_id``/``name``。这里做一层映射，避免前端拿到
    ``item.good_id === undefined`` 进而导致 ``/info/good?id=undefined`` 的
    422 错误。同时对两种形状都做兼容，防止 API 字段调整时回归。
    """
    if not isinstance(raw, dict):
        return {"data": []}

    data = raw.get("data")
    items: list[dict[str, str]] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            good_id = str(
                item.get("good_id") or item.get("id") or ""
            )
            name = str(item.get("name") or item.get("value") or "")
            if not good_id and not name:
                continue
            items.append({"good_id": good_id, "name": name})

    return {
        "code": raw.get("code", 0),
        "msg": raw.get("msg", "Success"),
        "data": items,
    }


@router.post("/search")
async def search_suggest(req: SearchRequest) -> Any:
    """饰品名称联想搜索。

    封装 CSQAQ ``/api/v1/search/suggest?text={keyword}``，并将结果归一化为
    ``{data: [{good_id, name}]}`` 以匹配前端类型。结果缓存 30 秒。
    """
    cache_key = f"search:{req.text}"
    cached = _SEARCH_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("item_search (cached) text=%s", req.text)
        return cached

    LOGGER.info("item_search text=%s", req.text)
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.get, "/search/suggest", params={"text": req.text})
        normalized = _normalize_search_result(result)
        _SEARCH_CACHE.set(cache_key, normalized)
        return normalized
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/all")
async def get_all_goods_id() -> Any:
    """全量饰品 ID 映射表。

    封装 CSQAQ ``/api/v1/goods/get_all_goods_id``。结果缓存 60 秒。
    """
    cache_key = "all_goods_id"
    cached = ITEM_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("item_all_goods_id (cached)")
        return cached

    LOGGER.info("item_all_goods_id")
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.get, "/goods/get_all_goods_id")
        ITEM_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/detail")
async def get_item_detail(good_id: str) -> Any:
    """单件饰品详情（7 平台 50+ 字段）。

    封装 CSQAQ ``/api/v1/info/good?id={good_id}``。结果缓存 60 秒。
    """
    cache_key = f"detail:{good_id}"
    cached = ITEM_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("item_detail (cached) good_id=%s", good_id)
        return cached

    LOGGER.info("item_detail good_id=%s", good_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.get, "/info/good", params={"id": good_id})
        ITEM_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/chart")
async def get_item_chart(req: ChartRequest) -> Any:
    """单品多平台多周期图表数据。

    封装 CSQAQ ``/api/v1/info/chart``，支持 11 种指标 × 4 平台 × 7 周期。
    结果缓存 60 秒。
    """
    cache_key = f"chart:{req.good_id}:{req.key}:{req.platform}:{req.period}:{req.style}"
    cached = ITEM_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("item_chart (cached) good_id=%s key=%s platform=%d period=%d", req.good_id, req.key, req.platform, req.period)
        return cached

    LOGGER.info("item_chart good_id=%s key=%s platform=%d period=%d", req.good_id, req.key, req.platform, req.period)
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.post, "/info/chart", json={
            "good_id": req.good_id,
            "key": req.key,
            "platform": req.platform,
            "period": req.period,
            "style": req.style,
        })
        ITEM_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/chart-all")
async def get_item_chart_all(req: ChartAllRequest) -> Any:
    """单品全量图表（仅售价+在售量）。

    封装 CSQAQ ``/api/v1/info/simple/chartAll``。结果缓存 60 秒。
    """
    cache_key = f"chart_all:{req.good_id}"
    cached = ITEM_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("item_chart_all (cached) good_id=%s", req.good_id)
        return cached

    LOGGER.info("item_chart_all good_id=%s", req.good_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.post, "/info/simple/chartAll", json={"good_id": req.good_id})
        ITEM_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/supply")
async def get_item_supply(good_id: str) -> Any:
    """单件饰品存世量走势（近 180 天）。

    封装 CSQAQ ``/api/v1/info/good/statistic?id={good_id}``。结果缓存 60 秒。
    """
    cache_key = f"supply:{good_id}"
    cached = ITEM_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("item_supply (cached) good_id=%s", good_id)
        return cached

    LOGGER.info("item_supply good_id=%s", good_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.get, "/info/good/statistic", params={"id": good_id})
        ITEM_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/batch-price")
async def get_batch_price(req: BatchPriceRequest) -> Any:
    """批量获取饰品价格和在售数据（单次 ≤50 个）。

    封装 CSQAQ ``/api/v1/goods/getPriceByMarketHashName``。结果缓存 60 秒。
    """
    if len(req.market_hash_names) > 50:
        raise HTTPException(status_code=400, detail="单次最多查询 50 个饰品")

    cache_key = f"batch_price:{':'.join(sorted(req.market_hash_names))}"
    cached = ITEM_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("item_batch_price (cached) count=%d", len(req.market_hash_names))
        return cached

    LOGGER.info("item_batch_price count=%d", len(req.market_hash_names))
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.post, "/goods/getPriceByMarketHashName", json={
            "market_hash_names": req.market_hash_names,
        })
        ITEM_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)
