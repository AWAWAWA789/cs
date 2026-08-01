"""库存监控 API endpoints for the accumulation analysis feature.

Wraps CSQAQ's 7 inventory monitoring endpoints:
- monitor/get_task_list → POST /monitor/tasks
- monitor/get_task_trends → POST /monitor/trends
- monitor/get_good_rank → POST /monitor/good-rank
- monitor/get_task_info → POST /monitor/user-info
- monitor/get_task_trends_detail → POST /monitor/user-trends
- task/get_task_all → POST /monitor/user-inventory
- monitor/get_snapshot_list → POST /monitor/snapshots

Each endpoint uses a 60-second TTL in-memory cache to reduce API calls.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.cache import TTLCache
from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger
from src.config import Settings

LOGGER = get_logger("csqaq.monitor_api")

router = APIRouter(prefix="/monitor", tags=["monitor"])

# 缓存：库存监控数据变化频率低，60 秒 TTL 足够
_MONITOR_CACHE = TTLCache(ttl_seconds=60.0)


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


# ── Request Models ─────────────────────────────────────────


class TaskListRequest(BaseModel):
    """监控任务列表请求体。"""
    page_index: int = Field(1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(20, ge=1, le=500, description="每页数量")
    search: str | None = Field(None, description="搜索 Steam 用户名/ID")
    sort: str | None = Field(None, description="排序字段")


class TaskTrendsRequest(BaseModel):
    """库存变动动态请求体。"""
    good_id: str | None = Field(None, description="按饰品 ID 筛选变动")
    page_index: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=500)


class GoodRankRequest(BaseModel):
    """饰品持有量排行请求体。"""
    good_id: str = Field(..., description="饰品 ID")
    page_index: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=500)


class TaskInfoRequest(BaseModel):
    """单个用户信息请求体。"""
    task_id: str = Field(..., description="监控任务 ID")


class UserTrendsRequest(BaseModel):
    """单个用户库存动态请求体。"""
    task_id: str = Field(..., description="监控任务 ID")
    page_index: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=500)


class UserInventoryRequest(BaseModel):
    """单个用户全部库存请求体。"""
    task_id: str = Field(..., description="监控任务 ID")
    snapshot_id: str | None = Field(None, description="快照 ID，用于查看历史库存")


class SnapshotListRequest(BaseModel):
    """库存快照列表请求体。"""
    task_id: str = Field(..., description="监控任务 ID")


# ── Endpoints ──────────────────────────────────────────────


@router.post("/tasks")
async def get_task_list(req: TaskListRequest) -> Any:
    """监控任务列表：支持搜索 Steam 用户名/ID，按多种维度排序。

    封装 CSQAQ ``POST /api/v1/monitor/get_task_list``。结果缓存 60 秒。
    """
    cache_key = f"tasks:{req.page_index}:{req.page_size}:{req.search}:{req.sort}"
    cached = _MONITOR_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("monitor_tasks (cached) page=%d", req.page_index)
        return cached

    LOGGER.info("monitor_tasks page=%d search=%s", req.page_index, req.search)
    client = _get_client()
    body: dict[str, Any] = {
        "page_index": req.page_index,
        "page_size": req.page_size,
    }
    if req.search:
        body["search"] = req.search
    if req.sort:
        body["sort"] = req.sort
    try:
        result = await asyncio.to_thread(client.post, "/monitor/get_task_list", json=body)
        _MONITOR_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/trends")
async def get_task_trends(req: TaskTrendsRequest) -> Any:
    """库存变动动态：全站最新变动，或按 good_id 筛选特定饰品变动。

    封装 CSQAQ ``POST /api/v1/monitor/get_task_trends``。结果缓存 60 秒。
    """
    cache_key = f"trends:{req.good_id}:{req.page_index}:{req.page_size}"
    cached = _MONITOR_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("monitor_trends (cached) good_id=%s", req.good_id)
        return cached

    LOGGER.info("monitor_trends good_id=%s", req.good_id)
    client = _get_client()
    body: dict[str, Any] = {
        "page_index": req.page_index,
        "page_size": req.page_size,
    }
    if req.good_id:
        body["good_id"] = req.good_id
    try:
        result = await asyncio.to_thread(client.post, "/monitor/get_task_trends", json=body)
        _MONITOR_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/good-rank")
async def get_good_rank(req: GoodRankRequest) -> Any:
    """饰品持有量排行榜：按 good_id 查询持有该饰品的用户排行。

    封装 CSQAQ ``POST /api/v1/monitor/get_good_rank``。结果缓存 60 秒。
    """
    cache_key = f"good_rank:{req.good_id}:{req.page_index}:{req.page_size}"
    cached = _MONITOR_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("monitor_good_rank (cached) good_id=%s", req.good_id)
        return cached

    LOGGER.info("monitor_good_rank good_id=%s", req.good_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(
            client.post,
            "/monitor/get_good_rank",
            json={
                "good_id": req.good_id,
                "page_index": req.page_index,
                "page_size": req.page_size,
            },
        )
        _MONITOR_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/user-info")
async def get_task_info(req: TaskInfoRequest) -> Any:
    """单个用户信息：返回用户详情。

    封装 CSQAQ ``POST /api/v1/monitor/get_task_info``。结果缓存 60 秒。
    """
    cache_key = f"user_info:{req.task_id}"
    cached = _MONITOR_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("monitor_user_info (cached) task_id=%s", req.task_id)
        return cached

    LOGGER.info("monitor_user_info task_id=%s", req.task_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(
            client.post, "/monitor/get_task_info", json={"task_id": req.task_id}
        )
        _MONITOR_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/user-trends")
async def get_user_trends(req: UserTrendsRequest) -> Any:
    """单个用户库存动态：返回该用户的库存变动历史。

    封装 CSQAQ ``POST /api/v1/monitor/get_task_trends_detail``。结果缓存 60 秒。
    """
    cache_key = f"user_trends:{req.task_id}:{req.page_index}:{req.page_size}"
    cached = _MONITOR_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("monitor_user_trends (cached) task_id=%s", req.task_id)
        return cached

    LOGGER.info("monitor_user_trends task_id=%s", req.task_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(
            client.post,
            "/monitor/get_task_trends_detail",
            json={
                "task_id": req.task_id,
                "page_index": req.page_index,
                "page_size": req.page_size,
            },
        )
        _MONITOR_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/user-inventory")
async def get_user_inventory(req: UserInventoryRequest) -> Any:
    """单个用户全部库存：支持快照 ID 查看历史库存。

    封装 CSQAQ ``POST /api/v1/task/get_task_all``。结果缓存 60 秒。
    """
    cache_key = f"user_inventory:{req.task_id}:{req.snapshot_id}"
    cached = _MONITOR_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("monitor_user_inventory (cached) task_id=%s", req.task_id)
        return cached

    LOGGER.info("monitor_user_inventory task_id=%s", req.task_id)
    client = _get_client()
    body: dict[str, Any] = {"task_id": req.task_id}
    if req.snapshot_id:
        body["snapshot_id"] = req.snapshot_id
    try:
        result = await asyncio.to_thread(client.post, "/task/get_task_all", json=body)
        _MONITOR_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)


@router.post("/snapshots")
async def get_snapshot_list(req: SnapshotListRequest) -> Any:
    """库存快照列表：返回用户的历史库存快照。

    封装 CSQAQ ``POST /api/v1/monitor/get_snapshot_list``。结果缓存 60 秒。
    """
    cache_key = f"snapshots:{req.task_id}"
    cached = _MONITOR_CACHE.get(cache_key)
    if cached is not None:
        LOGGER.info("monitor_snapshots (cached) task_id=%s", req.task_id)
        return cached

    LOGGER.info("monitor_snapshots task_id=%s", req.task_id)
    client = _get_client()
    try:
        result = await asyncio.to_thread(
            client.post, "/monitor/get_snapshot_list", json={"task_id": req.task_id}
        )
        _MONITOR_CACHE.set(cache_key, result)
        return result
    except CSQAQAPIError as exc:
        _handle_api_error(exc)
