"""历史训练数据批量回填编排器。

负责从 CSQAQ 拉取步枪千百战单品候选池，按价格区间筛选，并批量回填两年日线
到本地 Parquet 缓存，为后续案例库构建与训练提供数据基础。

流水线：
    1. 候选池采集：/info/get_page_list type=步枪 分页拉全量
    2. 价格筛选：   /goods/getPriceByMarketHashName 批量查现价，筛 300-2500
    3. 日线回填：   /info/chart period=730 逐品拉日线 → 落盘 parquet

受 CSQAQ 1 req/s 限流，批量回填耗时较长（100 品约 200s）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.logging import get_logger
from src.config import Settings
from src.data.item_cache import save_item_ohlc

LOGGER = get_logger("csqaq.backfill")

# 千百战价格区间（用户定义）
PRICE_MIN = 300.0
PRICE_MAX = 2500.0
PRICE_CORE_MIN = 500.0  # 核心区间下限

# 回填历史天数（两年 = 730 天，落在 /info/chart 上限 1095 内）
BACKFILL_DAYS = 730


def _to_float(val: Any, default: float = 0.0) -> float:
    """安全转 float。"""
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _to_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    return str(val)


def fetch_rifle_candidates(
    client: CSQAQClient,
    page_size: int = 50,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    """拉取步枪品类全量单品候选池。

    调 /info/get_page_list，type 映射为「不限_步枪」。

    Args:
        client: CSQAQ 客户端
        page_size: 每页大小（≤50 受 API 限制）
        max_pages: 最大页数（防止无限翻页）

    Returns:
        候选单品列表，每项含 good_id, name, market_hash_name 等字段。
    """
    candidates: list[dict[str, Any]] = []
    for page_idx in range(1, max_pages + 1):
        try:
            result = client.post("/info/get_page_list", json={
                "page_index": page_idx,
                "page_size": page_size,
                "filter": {"类型": ["不限_步枪"]},
            }, skip_rate_limit=False)
        except CSQAQAPIError as exc:
            LOGGER.warning("get_page_list page=%d failed: %s", page_idx, exc)
            break

        data = result.get("data") if isinstance(result, dict) else None
        items = data if isinstance(data, list) else []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            good_id = _to_str(item.get("good_id") or item.get("id"))
            if not good_id:
                continue
            candidates.append({
                "good_id": good_id,
                "name": _to_str(item.get("name") or item.get("value") or item.get("goods_name")),
                "market_hash_name": _to_str(item.get("market_hash_name") or item.get("hash_name")),
                "raw": item,
            })

        LOGGER.info("fetched rifle page %d: %d items (total %d)", page_idx, len(items), len(candidates))

        if len(items) < page_size:
            break  # 最后一页

    return candidates


def filter_by_price(
    client: CSQAQClient,
    candidates: list[dict[str, Any]],
    price_min: float = PRICE_MIN,
    price_max: float = PRICE_MAX,
    batch_size: int = 50,
) -> list[dict[str, Any]]:
    """按价格区间筛选候选品。

    调 /goods/getPriceByMarketHashName 批量查现价，保留区间内的品。

    Args:
        client: CSQAQ 客户端
        candidates: 候选品列表（需含 market_hash_name）
        price_min: 价格下限（含）
        price_max: 价格上限（含）
        batch_size: 批量查询大小（≤50 受 API 限制）

    Returns:
        筛选后的候选品列表，每项增加 ``price`` 字段。
    """
    filtered: list[dict[str, Any]] = []
    # 仅保留有 market_hash_name 的品
    with_hash = [c for c in candidates if c.get("market_hash_name")]
    LOGGER.info("filter_by_price: %d/%d candidates have market_hash_name", len(with_hash), len(candidates))

    for i in range(0, len(with_hash), batch_size):
        batch = with_hash[i:i + batch_size]
        names = [c["market_hash_name"] for c in batch]
        try:
            result = client.post("/goods/getPriceByMarketHashName", json={
                "market_hash_names": names,
            }, skip_rate_limit=False)
        except CSQAQAPIError as exc:
            LOGGER.warning("batch-price failed for batch %d: %s", i // batch_size, exc)
            continue

        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict):
            data = {}
        # data 通常是 {market_hash_name: {sell_price/buy_price/...}}
        for cand in batch:
            info = data.get(cand["market_hash_name"])
            if not isinstance(info, dict):
                continue
            price = _to_float(info.get("sell_price") or info.get("price"))
            if price == 0:
                continue
            if price_min <= price <= price_max:
                cand["price"] = price
                cand["is_core"] = price >= PRICE_CORE_MIN
                filtered.append(cand)

        LOGGER.info(
            "filter_by_price batch %d: %d in range (total %d)",
            i // batch_size, len(filtered), len(filtered),
        )

    return filtered


def backfill_item_ohlc(
    client: CSQAQClient,
    good_id: str,
    period_days: int = BACKFILL_DAYS,
    platform: int = 1,
    key: str = "sell_price",
) -> pd.DataFrame | None:
    """拉取单品两年日线并构造 OHLC DataFrame。

    复用 accumulation_endpoints._build_ohlc_from_prices 的构造逻辑。

    Returns:
        OHLC DataFrame 或 None（拉取失败时）
    """
    from src.api.accumulation_endpoints import _build_ohlc_from_prices

    try:
        result = client.post("/info/chart", json={
            "good_id": good_id,
            "key": key,
            "platform": platform,
            "period": period_days,
            "style": "all_style",
        }, skip_rate_limit=False)
    except CSQAQAPIError as exc:
        LOGGER.warning("chart fetch failed for good_id=%s: %s", good_id, exc)
        return None

    timestamps = result.get("timestamp", [])
    prices = result.get("main_data", [])
    if not timestamps or not prices or len(timestamps) != len(prices):
        return None

    return _build_ohlc_from_prices(timestamps, prices, "1day")


def backfill_rifle_ohlc(
    candidates: list[dict[str, Any]],
    cache_root: str | Path,
    category: str = "rifle",
    period_days: int = BACKFILL_DAYS,
    limit: int | None = None,
) -> dict[str, Any]:
    """批量回填步枪单品两年日线到 Parquet。

    Args:
        candidates: 经价格筛选后的候选品列表
        cache_root: 缓存根目录
        category: 品类目录名
        period_days: 回填历史天数
        limit: 限制回填数量（测试用），None 表示全部

    Returns:
        统计字典：{total, success, failed, skipped, duration_s}
    """
    settings = Settings()
    if not settings.api_token:
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "duration_s": 0, "error": "no_token"}

    client = CSQAQClient(settings)
    targets = candidates if limit is None else candidates[:limit]
    start = time.perf_counter()

    success = 0
    failed = 0
    skipped = 0

    for i, cand in enumerate(targets):
        good_id = cand["good_id"]
        name = cand.get("name", "")

        # 已落盘则跳过（增量回填）
        from src.data.item_cache import item_cache_path
        path = item_cache_path(good_id, "1day", cache_root, category)
        if path.exists():
            skipped += 1
            continue

        df = backfill_item_ohlc(client, good_id, period_days=period_days)
        if df is None or len(df) < 30:
            failed += 1
            LOGGER.warning("backfill failed/insufficient for good_id=%s (%s)", good_id, name)
            continue

        save_item_ohlc(df, good_id, "1day", cache_root, category)
        success += 1
        LOGGER.info(
            "backfilled [%d/%d] good_id=%s (%s): %d bars",
            i + 1, len(targets), good_id, name, len(df),
        )

    duration_s = time.perf_counter() - start
    stats = {
        "total": len(targets),
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "duration_s": round(duration_s, 2),
    }
    LOGGER.info("backfill complete: %s", stats)
    return stats


def save_candidates(
    candidates: list[dict[str, Any]],
    cache_root: str | Path,
    category: str = "rifle",
) -> Path:
    """落盘候选品列表到 JSON（供训练时复用）。"""
    dir_path = Path(cache_root) / "candidates"
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"{category}_candidates.json"
    # 移除 raw 字段避免污染
    clean = [{k: v for k, v in c.items() if k != "raw"} for c in candidates]
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2))
    return path


def load_candidates(
    cache_root: str | Path,
    category: str = "rifle",
) -> list[dict[str, Any]]:
    """加载已落盘的候选品列表。"""
    path = Path(cache_root) / "candidates" / f"{category}_candidates.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())
