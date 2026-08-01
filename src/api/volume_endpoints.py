"""实时成交数据 API endpoints。

Wraps CSQAQ's 2 volume endpoints (currently paused upstream):
- vol/current → GET /volume/current
- vol/detail → GET /volume/detail

注意：上游 CSQAQ 实时成交数据已暂停更新，前端需标注"数据暂停更新"状态。
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.cache import TTLCache
from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger
from src.config import Settings

LOGGER = get_logger("csqaq.volume_api")

router = APIRouter(prefix="/volume", tags=["volume"])

_VOLUME_CACHE = TTLCache(ttl_seconds=60.0)


def _get_client() -> CSQAQClient:
    """从当前配置创建 CSQAQ 客户端。"""
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


@router.get("/current")
async def get_current_volume() -> Any:
    """平台实时成交量数据。

    封装 CSQAQ ``GET /api/v1/vol/current``。结果缓存 60 秒。
    注意：上游数据已暂停更新。
    """
    cache_key = "current_volume"
    cached = _VOLUME_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("volume_current (cached)")
        return cached

    LOGGER.info("volume_current")
    client = _get_client()
    try:
        result = await asyncio.to_thread(client.get, "/vol/current")
        _VOLUME_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/detail")
async def get_volume_detail(
    vol_id: str = Query(..., description="饰品成交量 ID"),
) -> Any:
    """单品实时成交量历史图表和磨损数据。

    封装 CSQAQ ``GET /api/v1/vol/detail?id={vol_id}``。结果缓存 60 秒。
    注意：上游数据已暂停更新。
    """
    cache_key = f"volume_detail:{vol_id}"
    cached = _VOLUME_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("volume_detail (cached) vol_id=%s", vol_id)
        return cached

    LOGGER.info("volume_detail vol_id=%s", vol_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(
            client.get, "/vol/detail", params={"id": vol_id}
        )
        _VOLUME_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)
