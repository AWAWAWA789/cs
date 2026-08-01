"""库存吸货分析 API endpoints。

提供吸货检测分析能力和一次性数据预热初始化（问题9）。

端点：
- POST /accumulation/analyze  — 对指定标的执行吸货分析
- POST /accumulation/scan     — 扫描多个标的的吸货评分排行
- POST /accumulation/init     — 一次性预热初始化（问题9）
- GET  /accumulation/status   — 查看初始化状态

支持两种数据源：
1. 指数(sub_index)：从本地缓存的 OHLCV 数据加载
2. 单品(good_id)：从 CSQAQ /info/chart 拉取价格序列，构造为 OHLC
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.cache import TTLCache, ITEM_CACHE
from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger, log_request
from src.api.monitoring import record_request
from src.config import Settings
from src.data.cache import cache_file_path, load_cached
from src.data.pipeline import filter_from_2024
from src.scenario_engine.accumulation_detector import detect_accumulation
from src.scenario_engine.team_analyzer import analyze_team

LOGGER = get_logger("csqaq.accumulation_api")

router = APIRouter(prefix="/accumulation", tags=["accumulation"])

# 分析结果缓存（5 分钟）
_ANALYSIS_CACHE = TTLCache(ttl_seconds=300.0)

# 团队分析结果缓存（5 分钟）
_TEAM_CACHE = TTLCache(ttl_seconds=300.0)

# 初始化状态（进程级）
_INIT_STATE: dict[str, Any] = {
    "initialized": False,
    "last_run": None,
    "items_cached": 0,
    "errors": [],
}

# 支持的周期
_SUPPORTED_PERIODS = {"1hour", "4hour", "1day", "7day"}

# 单品图表周期映射：吸货分析周期 → CSQAQ /info/chart 的天数 period
# /info/chart 的 period 是天数，吸货分析的周期是别名，需要映射
_ITEM_PERIOD_DAYS = {
    "1hour": 7,     # 近7天数据按小时聚合
    "4hour": 30,    # 近30天数据按4小时聚合
    "1day": 365,    # 近1年数据按天聚合
    "7day": 1095,   # 近3年数据按周聚合
}


# ── Request Models ─────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    """吸货分析请求体。

    支持两种模式：
    - 指数模式：提供 sub_index（如"饰品指数"），从指数缓存加载
    - 单品模式：提供 good_id（如"2"），从 CSQAQ /info/chart 拉取
    单品模式优先级高于指数模式。
    """
    sub_index: str = Field("", description="子指数名称（指数模式）")
    good_id: str | None = Field(None, description="单品 good_id（单品模式，优先）")
    period: str = Field("1day", description="K 线周期")
    platform: int = Field(1, description="平台：1-BUFF/2-悠悠/3-Steam/4-C5（单品模式用）")
    key: str = Field("sell_price", description="价格指标（单品模式用）")


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


# ── Helpers ───────────────────────────────────────────────


def _load_ohlc_for_accumulation(
    sub_index: str, period: str
) -> tuple[pd.DataFrame | None, str]:
    """加载指数 OHLC 数据用于吸货分析。

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


def _fetch_item_price_series(
    good_id: str, period: str, platform: int = 1, key: str = "sell_price"
) -> tuple[pd.DataFrame | None, str]:
    """从 CSQAQ /info/chart 拉取单品价格序列并构造为 OHLC DataFrame。

    /info/chart 返回 {timestamp, main_data, num_data}，其中 main_data 是价格序列。
    按吸货分析周期将价格序列聚合为 OHLC：
    - 1hour: 原始（每小时一根）
    - 4hour: 每4根聚合一根
    - 1day: 每天一根（已是天级数据，直接用）
    - 7day: 每7根聚合一根

    返回 (df, data_source)，df 含 timestamp/open/high/low/close 列。
    """
    cache_key = f"accum_item:{good_id}:{key}:{platform}:{period}"

    # 先查内存缓存
    cached = ITEM_CACHE.get(cache_key)
    if cached is not None:
        df = cached if isinstance(cached, pd.DataFrame) else None
        if df is not None and len(df) >= 10:
            return df, "cached"

    days = _ITEM_PERIOD_DAYS.get(period, 365)
    settings = Settings()
    if not settings.api_token:
        return None, "no_token"

    try:
        client = CSQAQClient(settings)
        result = client.post("/info/chart", json={
            "good_id": good_id,
            "key": key,
            "platform": platform,
            "period": days,
            "style": "all_style",
        }, skip_rate_limit=True)
    except CSQAQAPIError as exc:
        LOGGER.warning("item chart fetch failed for good_id=%s: %s", good_id, exc)
        return None, f"api_error:{exc.code}"
    except Exception as exc:
        LOGGER.warning("item chart fetch failed for good_id=%s: %s", good_id, exc)
        return None, "fetch_failed"

    timestamps = result.get("timestamp", [])
    prices = result.get("main_data", [])
    if not timestamps or not prices or len(timestamps) != len(prices):
        return None, "invalid_data"

    # 构造 DataFrame：单价格序列 → 按周期聚合为 OHLC
    df = _build_ohlc_from_prices(timestamps, prices, period)
    if df is None or len(df) < 10:
        return None, "insufficient"

    # 缓存（5分钟 TTL，复用 ITEM_CACHE）
    ITEM_CACHE.set(cache_key, df)
    return df, "real"


def _build_ohlc_from_prices(
    timestamps: list, prices: list, period: str
) -> pd.DataFrame | None:
    """将价格点序列按周期聚合为 OHLC DataFrame。

    /info/chart 返回的数据通常是按天的价格点（period=365 → 363个点）。
    对于不同吸货分析周期：
    - 1day: 每个价格点作为一根日K（open=high=low=close=price）
    - 7day: 每7个价格点聚合成一根周K
    - 4hour/1hour: 数据粒度可能不够，退化为日K
    """
    if not timestamps or not prices:
        return None

    # 构造基础 DataFrame
    try:
        ts = pd.to_datetime([int(t) for t in timestamps], unit="ms", utc=True)
    except (ValueError, TypeError):
        try:
            ts = pd.to_datetime(timestamps, unit="ms", utc=True)
        except Exception:
            return None

    df = pd.DataFrame({
        "timestamp": ts,
        "close": pd.to_numeric(prices, errors="coerce"),
    })
    df = df.dropna(subset=["close"]).sort_values("timestamp").reset_index(drop=True)
    if len(df) < 2:
        return None

    # 单价格点没有真实OHLC，用 close 作为 open/high/low/close 的基础
    # 然后按周期聚合
    df["open"] = df["close"]
    df["high"] = df["close"]
    df["low"] = df["close"]

    # 按周期聚合
    if period == "7day":
        # 每7根聚合成一根周K
        df["group"] = df.index // 7
        agg = df.groupby("group").agg({
            "timestamp": "first",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }).reset_index(drop=True)
        df = agg[["timestamp", "open", "high", "low", "close"]]
    elif period in ("4hour", "1hour"):
        # /info/chart 数据粒度通常是天，无法真正按4小时/1小时聚合
        # 保持日K粒度（吸货分析对短周期的容忍度较高）
        pass
    # 1day: 直接用

    return df


# ── Endpoints ──────────────────────────────────────────────


def _monitor_client() -> CSQAQClient:
    """创建 CSQAQ 客户端用于库存监控接口调用。"""
    return CSQAQClient(Settings())


def _fetch_good_rank(client: CSQAQClient, good_id: str, page_size: int) -> list[dict[str, Any]]:
    """拉取持有该饰品的主力用户排行（封装 /monitor/get_good_rank）。"""
    try:
        result = client.post(
            "/monitor/get_good_rank",
            json={"good_id": good_id, "page_index": 1, "page_size": page_size},
            skip_rate_limit=True,
        )
    except CSQAQAPIError as exc:
        LOGGER.warning("good_rank fetch failed for good_id=%s: %s", good_id, exc)
        return []
    data = result.get("data") if isinstance(result, dict) else None
    return [item for item in (data or []) if isinstance(item, dict)]


def _fetch_good_trends(client: CSQAQClient, good_id: str, page_size: int) -> list[dict[str, Any]]:
    """拉取该饰品的近期库存变动（封装 /monitor/get_task_trends，按 good_id 筛选）。

    返回主力对该饰品的买卖动态（type 标识买入/卖出等行为）。
    """
    try:
        result = client.post(
            "/monitor/get_task_trends",
            json={"good_id": good_id, "page_index": 1, "page_size": page_size},
            skip_rate_limit=True,
        )
    except CSQAQAPIError as exc:
        LOGGER.warning("good_trends fetch failed for good_id=%s: %s", good_id, exc)
        return []
    data = result.get("data") if isinstance(result, dict) else None
    return [item for item in (data or []) if isinstance(item, dict)]


def _fetch_user_inventory(client: CSQAQClient, task_id: str) -> Any:
    """拉取单个用户的全部持仓（封装 /task/get_task_all）。

    用于跨品团队识别：获取该主力还持有哪些饰品。
    单个调用失败返回 None，不影响其他主力的拉取。
    """
    try:
        return client.post(
            "/task/get_task_all",
            json={"task_id": task_id},
            skip_rate_limit=True,
        )
    except CSQAQAPIError as exc:
        LOGGER.warning("user_inventory fetch failed for task_id=%s: %s", task_id, exc)
        return None
    except Exception as exc:
        LOGGER.warning("user_inventory fetch failed for task_id=%s: %s", task_id, exc)
        return None


@router.get("/item-inventory")
async def item_inventory(
    good_id: str = Query(..., description="饰品 good_id"),
    top_n: int = Query(20, ge=1, le=100, description="返回的主力/变动条数"),
) -> dict[str, Any]:
    """单品库存监控数据聚合（先看数据，不加算法）。

    一次返回该饰品的：
    1. ``holders`` — 持有量排行（主力手里的货量），来自 /monitor/get_good_rank
    2. ``trends`` — 近期库存变动（主力的买卖情况），来自 /monitor/get_task_trends

    供单品吸货页面直接展示原始库存数据，结合 K 线人工判断主力行为。
    """
    start = time.perf_counter()
    if not good_id:
        raise HTTPException(status_code=400, detail="good_id 不能为空")

    settings = Settings()
    if not settings.api_token:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request("/accumulation/item-inventory", latency_ms, error=False)
        return {
            "good_id": good_id,
            "holders": [],
            "trends": [],
            "data_source": "no_token",
            "description": "未配置 API token，无法拉取库存监控数据",
        }

    client = _monitor_client()
    holders = await asyncio.to_thread(_fetch_good_rank, client, good_id, top_n)
    trends = await asyncio.to_thread(_fetch_good_trends, client, good_id, top_n)

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/accumulation/item-inventory", latency_ms, error=False)
    LOGGER.info(
        "item-inventory good_id=%s: %d holders, %d trends (%.0fms)",
        good_id, len(holders), len(trends), latency_ms,
    )

    return {
        "good_id": good_id,
        "holders": holders,
        "trends": trends,
        "data_source": "real",
        "holder_count": len(holders),
        "trend_count": len(trends),
    }


@router.get("/team-analysis")
async def team_analysis(
    good_id: str = Query(..., description="种子饰品 good_id"),
    holder_top_n: int = Query(10, ge=1, le=30, description="取种子品 top-N 主力作为团队锚点"),
    min_overlap: int = Query(2, ge=1, le=20, description="关联品最少需要的种子主力重合数"),
) -> dict[str, Any]:
    """跨品主力团队识别分析。

    以选中饰品（种子品）的 top-N 持仓主力为锚点，拉取每个主力的全量持仓，
    构建 ``steam_id × good_id`` 持仓矩阵，识别：

    1. **关联品**：被多个种子主力共同持有的其他饰品（重合度高的疑似同团队操作标的）
    2. **核心团队**：跨多个品的主力（跨品数 ≥ 3 视为核心团队成员）
    3. **团队判定**：综合重合度与集中度的启发式判定 + 置信度

    结果缓存 5 分钟。由于需并发拉取 N 个用户的持仓（N=holder_top_n），
    耗时约 N × 1s（受 CSQAQ 限流）。
    """
    start = time.perf_counter()
    if not good_id:
        raise HTTPException(status_code=400, detail="good_id 不能为空")

    cache_key = f"team:{good_id}:{holder_top_n}:{min_overlap}"
    cached = _TEAM_CACHE.get(cache_key)
    if cached is not None:
        return cached

    settings = Settings()
    if not settings.api_token:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request("/accumulation/team-analysis", latency_ms, error=False)
        return {
            "seed_good_id": good_id,
            "seed_holder_count": 0,
            "analyzed_holder_count": 0,
            "related_items": [],
            "team_summary": {
                "core_team_size": 0,
                "core_team_hold_in_seed": 0,
                "core_team_ratio_in_seed": 0.0,
                "max_overlap_ratio": 0.0,
                "max_overlap_count": 0,
                "avg_cross_items_per_holder": 0.0,
                "related_item_count": 0,
                "is_likely_team_operated": False,
                "confidence": 0.0,
                "reason": "未配置 API token，无法拉取库存监控数据",
            },
            "holders_cross": [],
            "data_source": "no_token",
        }

    client = _monitor_client()

    # 1. 拉取种子品 top-N holders
    seed_holders = await asyncio.to_thread(_fetch_good_rank, client, good_id, holder_top_n)
    seed_holders = seed_holders[:holder_top_n]

    if not seed_holders:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request("/accumulation/team-analysis", latency_ms, error=False)
        result = {
            "seed_good_id": good_id,
            "seed_holder_count": 0,
            "analyzed_holder_count": 0,
            "related_items": [],
            "team_summary": {
                "core_team_size": 0,
                "core_team_hold_in_seed": 0,
                "core_team_ratio_in_seed": 0.0,
                "max_overlap_ratio": 0.0,
                "max_overlap_count": 0,
                "avg_cross_items_per_holder": 0.0,
                "related_item_count": 0,
                "is_likely_team_operated": False,
                "confidence": 0.0,
                "reason": "该饰品暂无持仓主力数据，可能未被监控",
            },
            "holders_cross": [],
            "data_source": "real",
        }
        _TEAM_CACHE.set(cache_key, result)
        return result

    # 2. 并发拉取每个 holder 的全量持仓
    # key 用 task_id（/task/get_task_all 需要 task_id），但 analyze_team 期望按 steam_id 索引
    # 这里建立 task_id → steam_id 映射，拉取后转成 {steam_id: inventory}
    holders_with_task = [
        h for h in seed_holders if h.get("task_id")
    ]
    inventories_raw: dict[str, Any] = {}
    if holders_with_task:
        # 并发拉取（client 内部 rate_limit 会自动串行化，避免 429）
        tasks = [
            asyncio.to_thread(_fetch_user_inventory, client, h["task_id"])
            for h in holders_with_task
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for h, res in zip(holders_with_task, results):
            steam_id = str(h.get("steam_id") or h.get("task_id") or "")
            if isinstance(res, Exception):
                LOGGER.warning("user_inventory failed for task_id=%s: %s", h.get("task_id"), res)
                inventories_raw[steam_id] = None
            else:
                inventories_raw[steam_id] = res

    # 3. 调用纯函数分析
    analysis = analyze_team(
        seed_good_id=good_id,
        seed_holders_raw=seed_holders,
        holders_inventory_raw=inventories_raw,
        min_overlap=min_overlap,
    )
    analysis["data_source"] = "real"

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/accumulation/team-analysis", latency_ms, error=False)
    summary = analysis.get("team_summary", {})
    LOGGER.info(
        "team-analysis good_id=%s: %d holders, %d related items, core_team=%d (%.0fms)",
        good_id,
        analysis.get("seed_holder_count", 0),
        summary.get("related_item_count", 0),
        summary.get("core_team_size", 0),
        latency_ms,
    )

    _TEAM_CACHE.set(cache_key, analysis)
    return analysis


@router.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """对指定标的执行吸货分析。

    支持两种模式：
    - 单品模式（good_id 非空）：从 CSQAQ /info/chart 拉取价格序列构造 OHLC
    - 指数模式（sub_index）：从本地缓存的指数 OHLC 加载

    单品模式优先。结果缓存 5 分钟。
    """
    start = time.perf_counter()
    period = req.period
    if period not in _SUPPORTED_PERIODS:
        raise HTTPException(status_code=400, detail=f"不支持的周期: {period}")

    # 缓存键：单品和指数分开
    if req.good_id:
        cache_key = f"analyze:item:{req.good_id}:{req.platform}:{req.key}:{period}"
        label = f"单品#{req.good_id}"
    else:
        cache_key = f"analyze:{req.sub_index}:{period}"
        label = req.sub_index

    cached = _ANALYSIS_CACHE.get(cache_key)
    if cached is not None:
        log_request(
            LOGGER,
            endpoint="/accumulation/analyze",
            sub_index=label,
            period=period,
            cached=True,
        )
        return {**cached, "cached": True}

    # 加载数据：单品模式 vs 指数模式
    if req.good_id:
        df, data_source = _fetch_item_price_series(
            req.good_id, period, req.platform, req.key
        )
    else:
        df, data_source = _load_ohlc_for_accumulation(req.sub_index, period)

    if df is None:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request("/accumulation/analyze", latency_ms, error=False)
        return {
            "sub_index": label,
            "period": period,
            "accumulation_score": 0.0,
            "phase": "neutral",
            "signals": {},
            "features": {},
            "data_source": data_source,
            "description": "无可用数据，请先执行数据初始化或检查 good_id/platform",
        }

    result = detect_accumulation(df, label, period)
    result["data_source"] = data_source

    _ANALYSIS_CACHE.set(cache_key, result)

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/accumulation/analyze",
        sub_index=label,
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
