"""Rank (排行榜/系列) API endpoints.

Wraps CSQAQ's 4 rank-related endpoints:
- rank/list → POST /rank/list
- goods/get_page_list → POST /rank/items
- series/get_series_list → GET /rank/series
- series/get_series_detail → GET /rank/series/{series_id}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger
from src.config import Settings

LOGGER = get_logger("csqaq.rank_api")

router = APIRouter(prefix="/rank", tags=["rank"])


def _get_client() -> CSQAQClient:
    """Create a CSQAQ client from current settings."""
    return CSQAQClient(Settings())


def _handle_api_error(exc: CSQAQAPIError) -> None:
    """将 CSQAQ API 错误转换为用户友好的 HTTP 异常。"""
    if exc.code == 401:
        raise HTTPException(
            status_code=503,
            detail="CSQAQ API 未授权(401)。请在 .env 中配置有效的 API Token 并绑定 IP。",
        ) from exc
    if exc.code == 429:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍等几秒后再试。",
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

    封装 CSQAQ ``/api/v1/rank/list``，支持按涨跌幅等多种排序字段分页查询。
    """
    LOGGER.info("rank_list sort=%s page_index=%d page_size=%d", req.sort, req.page_index, req.page_size)
    client = _get_client()
    try:
        return client.post("/rank/list", json={
            "sort": req.sort,
            "page_index": req.page_index,
            "page_size": req.page_size,
        })
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/items")
async def get_rank_items(req: ItemsRequest) -> Any:
    """饰品列表（支持多维度筛选）。

    封装 CSQAQ ``/api/v1/goods/get_page_list``，可按类型、品质、分类、磨损、
    关键词等条件筛选并分页返回饰品列表。
    """
    LOGGER.info(
        "rank_items type=%s quality=%s category=%s wear=%s search=%s page_index=%d page_size=%d",
        req.type, req.quality, req.category, req.wear, req.search, req.page_index, req.page_size,
    )
    client = _get_client()
    try:
        return client.post("/goods/get_page_list", json={
            "type": req.type,
            "quality": req.quality,
            "category": req.category,
            "wear": req.wear,
            "search": req.search,
            "page_index": req.page_index,
            "page_size": req.page_size,
        })
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/series")
async def get_series_list() -> Any:
    """热门系列列表。

    封装 CSQAQ ``/api/v1/series/get_series_list``。
    """
    LOGGER.info("rank_series_list")
    client = _get_client()
    try:
        return client.get("/series/get_series_list")
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/series/{series_id}")
async def get_series_detail(series_id: str) -> Any:
    """系列详情。

    封装 CSQAQ ``/api/v1/series/get_series_detail?series_id={series_id}``。
    """
    LOGGER.info("rank_series_detail series_id=%s", series_id)
    client = _get_client()
    try:
        return client.get("/series/get_series_detail", params={"series_id": series_id})
    except CSQAQAPIError as exc:
        _handle_api_error(exc)
