"""历史训练编排 API endpoints。

提供步枪千百战单品数据回填、案例库构建、训练触发与在线推理的统一入口。

端点：
- POST /training/backfill-candidates — 拉取步枪候选池 + 价格筛选 + 落盘
- POST /training/backfill-ohlc       — 批量回填两年日线到 Parquet
- GET  /training/backfill-status     — 查看已回填的样本量
- POST /training/build-cases         — 从已回填数据构建案例库（滑动切片）
- POST /training/label-cases        — 事后回看标注案例
- POST /training/train              — 训练规则权重 + 构建案例索引
- GET  /training/similar-cases      — 在线推理：检索历史相似案例
- GET  /training/stats              — 训练统计（案例数/命中率/权重）
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.logging import get_logger, log_request
from src.api.monitoring import record_request
from src.config import Settings

LOGGER = get_logger("csqaq.training_api")

router = APIRouter(prefix="/training", tags=["training"])


# ── Request Models ─────────────────────────────────────────


class BackfillCandidatesRequest(BaseModel):
    """候选池采集请求。"""
    category: str = Field("rifle", description="品类")
    price_min: float = Field(300.0, description="价格下限")
    price_max: float = Field(2500.0, description="价格上限")
    max_pages: int = Field(20, ge=1, le=50, description="最大翻页数")


class BackfillOhlcRequest(BaseModel):
    """批量回填 OHLC 请求。"""
    category: str = Field("rifle")
    period_days: int = Field(730, ge=30, le=1095, description="回填历史天数")
    limit: int | None = Field(None, ge=1, le=500, description="限制回填数量（测试用）")


class BuildCasesRequest(BaseModel):
    """构建案例库请求。"""
    category: str = Field("rifle")
    period: str = Field("1day")
    step_days: int = Field(7, ge=1, le=30, description="滑动切片步长（天）")


class LabelCasesRequest(BaseModel):
    """标注案例请求。"""
    category: str = Field("rifle")
    horizon: int = Field(30, ge=7, le=90, description="回看窗口（天）")
    positive_threshold: float = Field(0.15, description="正样本涨幅阈值")
    negative_threshold: float = Field(-0.10, description="负样本跌幅阈值")


class TrainRequest(BaseModel):
    """训练请求。"""
    category: str = Field("rifle")


# ── Endpoints ──────────────────────────────────────────────


@router.post("/backfill-candidates")
async def backfill_candidates(req: BackfillCandidatesRequest) -> dict[str, Any]:
    """采集步枪候选池 + 按价格筛选 + 落盘 JSON。

    流程：/info/get_page_list type=步枪 → /goods/getPriceByMarketHashName 筛选。
    受 1 req/s 限流，约 1-2 分钟。
    """
    start = time.perf_counter()
    settings = Settings()
    if not settings.api_token:
        raise HTTPException(status_code=503, detail="未配置 API token")

    from src.data.backfill import (
        fetch_rifle_candidates,
        filter_by_price,
        save_candidates,
    )
    from src.api.client import CSQAQClient

    client = CSQAQClient(settings)

    # 1. 拉候选池
    candidates = await asyncio.to_thread(
        fetch_rifle_candidates, client, 50, req.max_pages,
    )
    if not candidates:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request("/training/backfill-candidates", latency_ms, error=False)
        return {"total": 0, "filtered": 0, "error": "未拉到候选品"}

    # 2. 价格筛选
    filtered = await asyncio.to_thread(
        filter_by_price, client, candidates, req.price_min, req.price_max,
    )

    # 3. 落盘
    path = save_candidates(filtered, settings.cache_path, req.category)

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/training/backfill-candidates", latency_ms, error=False)
    LOGGER.info(
        "backfill-candidates: %d total → %d filtered (%.0fms)",
        len(candidates), len(filtered), latency_ms,
    )

    return {
        "category": req.category,
        "total_candidates": len(candidates),
        "filtered_count": len(filtered),
        "price_range": [req.price_min, req.price_max],
        "candidates_path": str(path),
        "latency_ms": round(latency_ms, 2),
    }


@router.post("/backfill-ohlc")
async def backfill_ohlc(req: BackfillOhlcRequest) -> dict[str, Any]:
    """批量回填两年日线到 Parquet。

    从候选品列表逐个拉 /info/chart period=730，落盘到
    ``{cache_root}/item_cache/{category}/{good_id}_1d.parquet``。

    受 1 req/s 限流，100 品约 200s。
    """
    start = time.perf_counter()
    settings = Settings()
    if not settings.api_token:
        raise HTTPException(status_code=503, detail="未配置 API token")

    from src.data.backfill import (
        load_candidates,
        backfill_rifle_ohlc,
    )

    candidates = load_candidates(settings.cache_path, req.category)
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail=f"无 {req.category} 候选品，请先调 /training/backfill-candidates",
        )

    stats = await asyncio.to_thread(
        backfill_rifle_ohlc,
        candidates,
        settings.cache_path,
        req.category,
        req.period_days,
        req.limit,
    )

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/training/backfill-ohlc", latency_ms, error=False)
    LOGGER.info("backfill-ohlc: %s (%.0fms)", stats, latency_ms)

    return {**stats, "latency_ms": round(latency_ms, 2)}


@router.get("/backfill-status")
async def backfill_status(
    category: str = Query("rifle"),
) -> dict[str, Any]:
    """查看已回填的样本量。"""
    settings = Settings()
    from src.data.backfill import load_candidates
    from src.data.item_cache import list_cached_items

    candidates = load_candidates(settings.cache_path, category)
    cached_items = list_cached_items(settings.cache_path, category, "1day")

    return {
        "category": category,
        "candidates_total": len(candidates),
        "ohlc_cached": len(cached_items),
        "cached_good_ids": cached_items[:50],  # 仅前 50 个预览
        "cache_root": str(settings.cache_path),
    }


@router.post("/build-cases")
async def build_cases(req: BuildCasesRequest) -> dict[str, Any]:
    """从已回填的日线构建案例库（滑动窗口切片）。

    对每个已落盘的单品，按 step_days 步长滑动切片，每片计算吸货特征向量，
    落盘到 ``data/cases/{category}_cases.jsonl``。
    """
    start = time.perf_counter()
    settings = Settings()

    from src.data.item_cache import list_cached_items, load_item_ohlc
    from src.scenario_engine.case_store import save_cases_batch
    from src.scenario_engine.accumulation_detector import detect_accumulation

    cached_good_ids = list_cached_items(settings.cache_path, req.category, req.period)
    if not cached_good_ids:
        raise HTTPException(
            status_code=400,
            detail=f"无 {req.category} 已落盘 OHLC，请先调 /training/backfill-ohlc",
        )

    # 加载候选品名映射
    from src.data.backfill import load_candidates
    candidates = load_candidates(settings.cache_path, req.category)
    name_map = {c["good_id"]: c.get("name", "") for c in candidates}

    total_cases = 0
    for good_id in cached_good_ids:
        df = load_item_ohlc(good_id, req.period, settings.cache_path, req.category)
        if df is None or len(df) < 60:
            continue

        # 滑动切片：从第 60 根开始，每 step_days 步切一片
        cases = []
        for i in range(60, len(df), req.step_days):
            window = df.iloc[:i + 1].copy()
            if len(window) < 60:
                continue
            ts = window.iloc[-1].get("timestamp")
            ts_str = str(ts) if ts is not None else ""

            result = detect_accumulation(window, sub_index=f"{req.category}#{good_id}", period=req.period)
            cases.append({
                "case_id": f"{req.category}_{good_id}_{i}",
                "good_id": good_id,
                "good_name": name_map.get(good_id, ""),
                "category": req.category,
                "timestamp": ts_str,
                "period": req.period,
                "features": result.get("features", {}),
                "kline_score": result.get("accumulation_score", 0.0),
                "signals": result.get("signals", {}),
                "duration_bars": result.get("duration_bars", 0),
                "label": None,  # 待标注
            })

        if cases:
            save_cases_batch(cases, settings.cache_path, req.category)
            total_cases += len(cases)

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/training/build-cases", latency_ms, error=False)
    LOGGER.info("build-cases: %d items → %d cases (%.0fms)", len(cached_good_ids), total_cases, latency_ms)

    return {
        "category": req.category,
        "items_processed": len(cached_good_ids),
        "cases_built": total_cases,
        "step_days": req.step_days,
        "latency_ms": round(latency_ms, 2),
    }


@router.post("/label-cases")
async def label_cases(req: LabelCasesRequest) -> dict[str, Any]:
    """事后回看标注案例。

    对每个案例，从其分析时点起，回看 horizon 天的价格走势，
    标注 positive/negative/neutral。
    """
    start = time.perf_counter()
    settings = Settings()

    from src.scenario_engine.case_store import load_cases, save_cases_batch
    from src.scenario_engine.labeling import label_cases_with_horizon

    cases = load_cases(settings.cache_path, req.category)
    if not cases:
        raise HTTPException(
            status_code=400,
            detail=f"无 {req.category} 案例库，请先调 /training/build-cases",
        )

    # 加载所有已落盘 OHLC 用于回看
    from src.data.item_cache import load_item_ohlc
    ohlc_cache: dict[str, Any] = {}
    good_ids = {c["good_id"] for c in cases}
    for gid in good_ids:
        df = load_item_ohlc(gid, "1day", settings.cache_path, req.category)
        if df is not None:
            ohlc_cache[gid] = df

    labeled = label_cases_with_horizon(
        cases, ohlc_cache,
        horizon=req.horizon,
        positive_threshold=req.positive_threshold,
        negative_threshold=req.negative_threshold,
    )

    # 重写案例库（带标注）
    save_cases_batch(labeled, settings.cache_path, req.category, overwrite=True)

    # 统计
    from collections import Counter
    label_dist = Counter(c.get("label") for c in labeled)

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/training/label-cases", latency_ms, error=False)
    LOGGER.info("label-cases: %d labeled → %s (%.0fms)", len(labeled), dict(label_dist), latency_ms)

    return {
        "category": req.category,
        "cases_labeled": len(labeled),
        "label_distribution": dict(label_dist),
        "horizon": req.horizon,
        "latency_ms": round(latency_ms, 2),
    }


@router.post("/train")
async def train(req: TrainRequest) -> dict[str, Any]:
    """训练规则权重 + 构建 KNN 案例索引。

    用已标注案例库 fit LogisticRegression，得到数据驱动的特征权重，
    替代拍脑袋的经验值。
    """
    start = time.perf_counter()
    settings = Settings()

    from src.scenario_engine.case_store import load_cases, load_labeled_cases
    from src.scenario_engine.trainer import train_rule_weights, build_case_index

    cases = load_cases(settings.cache_path, req.category)
    if not cases:
        raise HTTPException(
            status_code=400,
            detail=f"无 {req.category} 案例库，请先调 /training/build-cases + /training/label-cases",
        )

    labeled = load_labeled_cases(settings.cache_path, req.category)
    if not labeled:
        raise HTTPException(
            status_code=400,
            detail=f"无已标注案例，请先调 /training/label-cases",
        )

    # 训练
    weights_result = train_rule_weights(labeled, settings.cache_path, req.category)
    # 构建案例索引
    index_result = build_case_index(labeled, settings.cache_path, req.category)

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/training/train", latency_ms, error=False)
    LOGGER.info("train: %s (%.0fms)", weights_result, latency_ms)

    return {
        "category": req.category,
        "weights": weights_result,
        "case_index": index_result,
        "latency_ms": round(latency_ms, 2),
    }


@router.get("/similar-cases")
async def similar_cases(
    good_id: str = Query(..., description="查询饰品 good_id"),
    category: str = Query("rifle"),
    period: str = Query("1day"),
    top_k: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    """在线推理：检索历史相似案例。

    计算当前饰品的特征向量，在已训练的案例库中检索 top-K 相似案例，
    返回它们的标签与事后走势（用于人工判断当前是否在吸货）。
    """
    start = time.perf_counter()
    settings = Settings()

    from src.scenario_engine.case_retriever import retrieve_similar

    result = retrieve_similar(
        good_id=good_id,
        category=category,
        period=period,
        cache_root=settings.cache_path,
        top_k=top_k,
    )

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/training/similar-cases", latency_ms, error=False)

    return {**result, "latency_ms": round(latency_ms, 2)}


@router.get("/stats")
async def training_stats(
    category: str = Query("rifle"),
) -> dict[str, Any]:
    """训练统计：案例数、标注分布、命中率、当前权重。"""
    settings = Settings()

    from src.scenario_engine.case_store import load_cases, load_labeled_cases
    from src.scenario_engine.trainer import load_rule_weights

    all_cases = load_cases(settings.cache_path, category)
    labeled = load_labeled_cases(settings.cache_path, category)
    weights = load_rule_weights(settings.cache_path, category)

    # 标注分布
    from collections import Counter
    label_dist = Counter(c.get("label") for c in labeled if c.get("label"))

    # 命中率：positive 占 (positive + negative) 的比例
    pos = label_dist.get("positive", 0)
    neg = label_dist.get("negative", 0)
    hit_rate = pos / (pos + neg) if (pos + neg) > 0 else None

    return {
        "category": category,
        "total_cases": len(all_cases),
        "labeled_cases": len(labeled),
        "label_distribution": dict(label_dist),
        "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
        "rule_weights": weights,
        "trained": weights is not None,
    }
