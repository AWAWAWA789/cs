"""每日库存快照采集器（阶段 C）。

CSQAQ 的 `/monitor/get_good_rank` 和 `/monitor/get_task_trends` 只返回**当前**
快照，无历史接口。无法回答"3 个月前这个品的主力持仓是什么"，导致库存信号
永远无法被回测。

本模块提供：
1. `collect_snapshot(good_id, client)`：采集单品的 holders + trends + 即时算分
2. `save_snapshot(snapshot, cache_root)`：落盘到
   ``data/inventory/{good_id}/{YYYYMMDD}.parquet``
3. `load_snapshots(good_id, start, end, cache_root)`：加载区间快照
4. `collect_watchlist_snapshots(...)`：批量采集 watchlist 内全部品

存储策略：单品单日一个 parquet，含原始数据 + computed_signals。
trends 仅保留当日采集到的窗口（近 7 日），不存全量历史，单品单日 <100KB。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.api.client import CSQAQClient, CSQAQAPIError
from src.api.logging import get_logger
from src.scenario_engine.inventory_signals import compute_inventory_signals

LOGGER = get_logger("csqaq.inventory_snapshot")


def _today_str(now: datetime | None = None) -> str:
    """返回 UTC 当日 YYYYMMDD。"""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d")


def snapshot_path(
    good_id: str,
    date: str | None = None,
    cache_root: str | Path = "./data/cache",
) -> Path:
    """构建快照落盘路径。

    Args:
        good_id: 饰品 good_id
        date: YYYYMMDD，默认今日
        cache_root: 缓存根目录

    Returns:
        完整路径 ``{cache_root}/inventory/{good_id}/{YYYYMMDD}.parquet``
    """
    if date is None:
        date = _today_str()
    return Path(cache_root) / "inventory" / good_id / f"{date}.parquet"


def _fetch_holders(client: CSQAQClient, good_id: str, page_size: int = 50) -> list[dict[str, Any]]:
    """拉取持有该饰品的主力用户排行（封装 /monitor/get_good_rank）。"""
    try:
        result = client.post(
            "/monitor/get_good_rank",
            json={"good_id": good_id, "page_index": 1, "page_size": page_size},
            skip_rate_limit=True,
        )
    except CSQAQAPIError as exc:
        LOGGER.warning("holders fetch failed good_id=%s: %s", good_id, exc)
        return []
    data = result.get("data") if isinstance(result, dict) else None
    return [item for item in (data or []) if isinstance(item, dict)]


def _fetch_trends(client: CSQAQClient, good_id: str, page_size: int = 50) -> list[dict[str, Any]]:
    """拉取该饰品的近期库存变动（封装 /monitor/get_task_trends）。"""
    try:
        result = client.post(
            "/monitor/get_task_trends",
            json={"good_id": good_id, "page_index": 1, "page_size": page_size},
            skip_rate_limit=True,
        )
    except CSQAQAPIError as exc:
        LOGGER.warning("trends fetch failed good_id=%s: %s", good_id, exc)
        return []
    data = result.get("data") if isinstance(result, dict) else None
    return [item for item in (data or []) if isinstance(item, dict)]


def collect_snapshot(
    good_id: str,
    client: CSQAQClient,
    now: datetime | None = None,
) -> dict[str, Any]:
    """采集单品的库存快照（holders + trends + 即时算分）。

    Args:
        good_id: 饰品 good_id
        client: CSQAQ 客户端
        now: 当前时间（测试注入）

    Returns:
        结构化快照字典：
        - good_id, date, collected_at
        - holders: list[dict]
        - trends: list[dict]
        - computed_signals: dict（4 项子分 + inventory_score + 原始统计）
    """
    if now is None:
        now = datetime.now(timezone.utc)

    holders = _fetch_holders(client, good_id)
    trends = _fetch_trends(client, good_id)

    # 即时算分（不带 team_confidence，团队识别在分析时即时算）
    computed = compute_inventory_signals(holders, trends, team_confidence=None, now=now)

    return {
        "good_id": str(good_id),
        "date": _today_str(now),
        "collected_at": now.isoformat(),
        "holders": holders,
        "trends": trends,
        "computed_signals": {
            "top3_concentration": computed["top3_concentration"],
            "total_hold": computed["total_hold"],
            "net_inflow_7d": computed["net_inflow_7d"],
            "active_holder_count": computed["active_holder_count"],
            "holder_total": computed["holder_total"],
            "concentration": computed["signals"]["concentration"],
            "net_inflow": computed["signals"]["net_inflow"],
            "holder_activity": computed["signals"]["holder_activity"],
            "inventory_score": computed["inventory_score"],
        },
    }


def save_snapshot(
    snapshot: dict[str, Any],
    cache_root: str | Path = "./data/cache",
) -> Path:
    """落盘库存快照到 parquet。

    单品单日一个文件，便于按 good_id + 日期范围加载。
    holders/trends 存为 JSON 字符串列（避免 parquet struct 兼容问题）。
    """
    good_id = str(snapshot["good_id"])
    date = snapshot["date"]
    path = snapshot_path(good_id, date, cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 展平为单行 DataFrame
    row = {
        "good_id": good_id,
        "date": date,
        "collected_at": snapshot["collected_at"],
        "holders_json": json.dumps(snapshot["holders"], ensure_ascii=False),
        "trends_json": json.dumps(snapshot["trends"], ensure_ascii=False),
        **snapshot["computed_signals"],
    }
    df = pd.DataFrame([row])
    df.to_parquet(path, index=False)
    return path


def load_snapshots(
    good_id: str,
    start: str | None = None,
    end: str | None = None,
    cache_root: str | Path = "./data/cache",
) -> pd.DataFrame:
    """加载单品的库存快照区间。

    Args:
        good_id: 饰品 good_id
        start: 起始日期 YYYYMMDD（含），默认不限
        end: 结束日期 YYYYMMDD（含），默认不限
        cache_root: 缓存根目录

    Returns:
        DataFrame，每行一个日期的快照。无数据时返回空 DataFrame。
    """
    dir_path = Path(cache_root) / "inventory" / good_id
    if not dir_path.exists():
        return pd.DataFrame()

    files = sorted(dir_path.glob("*.parquet"))
    rows = []
    for f in files:
        date_str = f.stem
        if start and date_str < start:
            continue
        if end and date_str > end:
            continue
        try:
            rows.append(pd.read_parquet(f))
        except Exception as exc:
            LOGGER.warning("load_snapshots skip %s: %s", f, exc)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def load_snapshot_for_date(
    good_id: str,
    date: str,
    cache_root: str | Path = "./data/cache",
) -> dict[str, Any] | None:
    """加载单品指定日期的库存快照。

    Returns:
        快照字典或 None（无数据）
    """
    path = snapshot_path(good_id, date, cache_root)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        LOGGER.warning("load_snapshot_for_date %s failed: %s", path, exc)
        return None
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    # 反序列化 holders/trends
    row["holders"] = json.loads(row.get("holders_json", "[]"))
    row["trends"] = json.loads(row.get("trends_json", "[]"))
    row.pop("holders_json", None)
    row.pop("trends_json", None)
    return row


def list_snapshot_dates(
    good_id: str,
    cache_root: str | Path = "./data/cache",
) -> list[str]:
    """列出某品已采集的所有日期（YYYYMMDD 升序）。"""
    dir_path = Path(cache_root) / "inventory" / good_id
    if not dir_path.exists():
        return []
    return sorted(p.stem for p in dir_path.glob("*.parquet"))


def collect_watchlist_snapshots(
    good_ids: list[str],
    client: CSQAQClient,
    cache_root: str | Path = "./data/cache",
    force: bool = False,
) -> dict[str, Any]:
    """批量采集 watchlist 内全部品的当日快照。

    串行执行（client 内置 1 req/s 限流），失败品不中断整体流程。

    Args:
        good_ids: 待采集的 good_id 列表
        client: CSQAQ 客户端
        cache_root: 缓存根目录
        force: True 时即使当日已有快照也重新采集

    Returns:
        采集结果汇总：{total, success, skipped, failed, duration_sec, failures}
    """
    start_ts = time.time()
    today = _today_str()
    success = 0
    skipped = 0
    failures: list[dict[str, str]] = []

    for i, good_id in enumerate(good_ids):
        # 已有当日快照则跳过（除非 force）
        existing = snapshot_path(good_id, today, cache_root)
        if existing.exists() and not force:
            skipped += 1
            continue

        try:
            snap = collect_snapshot(good_id, client)
            save_snapshot(snap, cache_root)
            success += 1
            LOGGER.info(
                "collect_watchlist [%d/%d] good_id=%s score=%.3f saved",
                i + 1, len(good_ids), good_id,
                snap["computed_signals"]["inventory_score"],
            )
        except Exception as exc:
            failures.append({"good_id": good_id, "error": str(exc)})
            LOGGER.warning("collect_watchlist good_id=%s failed: %s", good_id, exc)

    duration = round(time.time() - start_ts, 1)
    return {
        "total": len(good_ids),
        "success": success,
        "skipped": skipped,
        "failed": len(failures),
        "failures": failures,
        "duration_sec": duration,
        "date": today,
    }
