"""Item (饰品) API endpoints for Phase 20.

Wraps CSQAQ's 7 item-related endpoints:
- search/suggest → POST /item/search
- goods/get_all_goods_id → GET /item/all
- info/good → GET /item/detail
- info/chart → POST /item/chart
- info/simple/chartAll → POST /item/chart-all
- info/good/statistic → GET /item/supply
- goods/getPriceByMarketHashName → POST /item/batch-price
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger
from src.config import Settings

LOGGER = get_logger("csqaq.item_api")

router = APIRouter(prefix="/item", tags=["item"])


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


@router.post("/search")
async def search_suggest(req: SearchRequest) -> Any:
    """饰品名称联想搜索。

    封装 CSQAQ ``/api/v1/search/suggest?text={keyword}``。
    """
    LOGGER.info("item_search text=%s", req.text)
    client = _get_client()
    try:
        return client.get("/search/suggest", params={"text": req.text})
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/all")
async def get_all_goods_id() -> Any:
    """全量饰品 ID 映射表。

    封装 CSQAQ ``/api/v1/goods/get_all_goods_id``。
    """
    LOGGER.info("item_all_goods_id")
    client = _get_client()
    try:
        return client.get("/goods/get_all_goods_id")
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/detail")
async def get_item_detail(good_id: str) -> Any:
    """单件饰品详情（7 平台 50+ 字段）。

    封装 CSQAQ ``/api/v1/info/good?id={good_id}``。
    """
    LOGGER.info("item_detail good_id=%s", good_id)
    client = _get_client()
    try:
        return client.get("/info/good", params={"id": good_id})
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/chart")
async def get_item_chart(req: ChartRequest) -> Any:
    """单品多平台多周期图表数据。

    封装 CSQAQ ``/api/v1/info/chart``，支持 11 种指标 × 4 平台 × 7 周期。
    """
    LOGGER.info("item_chart good_id=%s key=%s platform=%d period=%d", req.good_id, req.key, req.platform, req.period)
    client = _get_client()
    try:
        return client.post("/info/chart", json={
            "good_id": req.good_id,
            "key": req.key,
            "platform": req.platform,
            "period": req.period,
            "style": req.style,
        })
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/chart-all")
async def get_item_chart_all(req: ChartAllRequest) -> Any:
    """单品全量图表（仅售价+在售量）。

    封装 CSQAQ ``/api/v1/info/simple/chartAll``。
    """
    LOGGER.info("item_chart_all good_id=%s", req.good_id)
    client = _get_client()
    try:
        return client.post("/info/simple/chartAll", json={"good_id": req.good_id})
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.get("/supply")
async def get_item_supply(good_id: str) -> Any:
    """单件饰品存世量走势（近 180 天）。

    封装 CSQAQ ``/api/v1/info/good/statistic?id={good_id}``。
    """
    LOGGER.info("item_supply good_id=%s", good_id)
    client = _get_client()
    try:
        return client.get("/info/good/statistic", params={"id": good_id})
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/batch-price")
async def get_batch_price(req: BatchPriceRequest) -> Any:
    """批量获取饰品价格和在售数据（单次 ≤50 个）。

    封装 CSQAQ ``/api/v1/goods/getPriceByMarketHashName``。
    """
    if len(req.market_hash_names) > 50:
        raise HTTPException(status_code=400, detail="单次最多查询 50 个饰品")
    LOGGER.info("item_batch_price count=%d", len(req.market_hash_names))
    client = _get_client()
    try:
        return client.post("/goods/getPriceByMarketHashName", json={
            "market_hash_names": req.market_hash_names,
        })
    except CSQAQAPIError as exc:
        _handle_api_error(exc)
