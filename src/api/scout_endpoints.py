"""侦察机制 API endpoints（阶段 C+E）。

实现"侦察兵"产品定义：
- watchlist 订阅（E1）：用户关注的品列表
- 每日库存采集（C1）：触发 watchlist 内全部品的库存快照采集
- 阈值告警触发（E2）：分析后判定是否突破阈值
- 告警列表查询（E3）：前端查看历史告警
- 采集监控（C3）：采集成功率、缺失品
- 事后标注自动化（D3）：对到期的未标注 case 自动标注

端点：
- POST /scout/watchlist/add        — 加入关注
- GET  /scout/watchlist/list       — 关注列表
- DELETE /scout/watchlist/{good_id} — 移除关注
- POST /scout/collect-inventory   — 触发库存采集
- GET  /scout/inventory-status     — 采集监控
- POST /scout/run-scan             — 扫描 watchlist + 触发告警
- GET  /scout/alerts               — 告警列表
- POST /scout/auto-label           — 自动标注到期案例
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.logging import get_logger
from src.api.monitoring import record_request
from src.config import Settings

LOGGER = get_logger("csqaq.scout_api")

router = APIRouter(prefix="/scout", tags=["scout"])


# ── 路径约定 ──────────────────────────────────────────────


def _watchlist_path(cache_root: str) -> Path:
    return Path(cache_root) / "watchlist.json"


def _alerts_dir(cache_root: str) -> Path:
    return Path(cache_root) / "alerts"


def _load_watchlist(cache_root: str) -> list[dict[str, Any]]:
    """加载 watchlist，返回 list of {good_id, good_name, added_at, threshold}。"""
    path = _watchlist_path(cache_root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_watchlist(items: list[dict[str, Any]], cache_root: str) -> None:
    path = _watchlist_path(cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Request Models ─────────────────────────────────────────


class WatchlistAddRequest(BaseModel):
    good_id: str
    good_name: str = ""
    threshold: float = Field(0.6, ge=0.0, le=1.0, description="告警阈值")


class CollectInventoryRequest(BaseModel):
    force: bool = Field(False, description="True 时即使当日已采集也重采")


class RunScanRequest(BaseModel):
    """扫描 watchlist + 触发告警。"""
    alert_threshold: float = Field(0.6, ge=0.0, le=1.0)
    delta_threshold: float = Field(0.15, ge=0.0, le=1.0, description="较前日上升幅度阈值")


class AutoLabelRequest(BaseModel):
    """自动标注到期案例。"""
    category: str = "rifle"
    horizon: int = Field(30, ge=7, le=90)
    positive_threshold: float = 0.15
    negative_threshold: float = -0.10
    use_drawdown_constraint: bool = Field(
        True, description="启用回撤约束（F1）：正样本需 max_drawdown ≤ 8%"
    )
    max_drawdown_threshold: float = Field(0.08, ge=0.0, le=0.5)


# ── E1: watchlist 管理 ────────────────────────────────────


@router.post("/watchlist/add")
async def watchlist_add(req: WatchlistAddRequest) -> dict[str, Any]:
    """加入关注列表。已存在则更新 threshold。"""
    settings = Settings()
    items = _load_watchlist(settings.cache_path)

    # 去重更新
    existing = next((it for it in items if it.get("good_id") == req.good_id), None)
    if existing:
        existing["threshold"] = req.threshold
        existing["good_name"] = req.good_name or existing.get("good_name", "")
        action = "updated"
    else:
        items.append({
            "good_id": req.good_id,
            "good_name": req.good_name,
            "threshold": req.threshold,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        action = "added"

    _save_watchlist(items, settings.cache_path)
    return {"action": action, "good_id": req.good_id, "total": len(items)}


@router.get("/watchlist/list")
async def watchlist_list() -> dict[str, Any]:
    """列出全部关注品。"""
    settings = Settings()
    items = _load_watchlist(settings.cache_path)
    return {"total": len(items), "items": items}


@router.delete("/watchlist/{good_id}")
async def watchlist_remove(good_id: str) -> dict[str, Any]:
    """移除关注品。"""
    settings = Settings()
    items = _load_watchlist(settings.cache_path)
    before = len(items)
    items = [it for it in items if it.get("good_id") != good_id]
    _save_watchlist(items, settings.cache_path)
    return {"removed": before - len(items), "good_id": good_id, "total": len(items)}


# ── C1+C3: 库存采集 + 监控 ─────────────────────────────────


@router.post("/collect-inventory")
async def collect_inventory(req: CollectInventoryRequest) -> dict[str, Any]:
    """触发 watchlist 内全部品的当日库存快照采集。

    串行执行，受 1 req/s 限流。N 品约 N×2 秒。
    """
    start = time.perf_counter()
    settings = Settings()
    if not settings.api_token:
        raise HTTPException(status_code=503, detail="未配置 API token")

    items = _load_watchlist(settings.cache_path)
    if not items:
        return {"total": 0, "success": 0, "skipped": 0, "failed": 0,
                "message": "watchlist 为空"}

    from src.api.client import CSQAQClient
    from src.data.inventory_snapshot import collect_watchlist_snapshots

    client = CSQAQClient(settings)
    good_ids = [it["good_id"] for it in items]

    result = await asyncio.to_thread(
        collect_watchlist_snapshots,
        good_ids, client, settings.cache_path, req.force,
    )

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/scout/collect-inventory", latency_ms, error=False)
    return result


@router.get("/inventory-status")
async def inventory_status() -> dict[str, Any]:
    """查看最近 7 日采集成功率、缺失品列表。"""
    settings = Settings()
    items = _load_watchlist(settings.cache_path)
    if not items:
        return {"watchlist_size": 0, "recent_days": []}

    from src.data.inventory_snapshot import list_snapshot_dates

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    days: list[dict[str, Any]] = []
    for i in range(7):
        d = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from datetime import timedelta
        date_str = (d - timedelta(days=i)).strftime("%Y%m%d")
        collected = 0
        missing: list[str] = []
        for it in items:
            gid = it["good_id"]
            dates = list_snapshot_dates(gid, settings.cache_path)
            if date_str in dates:
                collected += 1
            else:
                missing.append(gid)
        days.append({
            "date": date_str,
            "collected": collected,
            "total": len(items),
            "success_rate": round(collected / len(items), 4) if items else 0.0,
            "missing": missing,
        })

    # 最近一次采集成功率
    latest = days[0] if days else None
    return {
        "watchlist_size": len(items),
        "today": today,
        "latest_success_rate": latest["success_rate"] if latest else 0.0,
        "recent_7days": days,
    }


# ── E2+E3: 扫描 + 告警 ────────────────────────────────────


@router.post("/run-scan")
async def run_scan(req: RunScanRequest) -> dict[str, Any]:
    """扫描 watchlist：双轨分析 → 突破阈值则触发告警。

    每个品分析后：
    - fused_score ≥ alert_threshold → 触发告警
    - 较前日 fused_score 上升 ≥ delta_threshold → 触发告警
    告警落盘到 ``data/alerts/{YYYYMMDD}.jsonl``
    """
    start = time.perf_counter()
    settings = Settings()
    if not settings.api_token:
        raise HTTPException(status_code=503, detail="未配置 API token")

    items = _load_watchlist(settings.cache_path)
    if not items:
        return {"total": 0, "alerts": 0, "message": "watchlist 为空"}

    from src.api.accumulation_endpoints import analyze_fused
    from src.api.client import CSQAQClient

    client = CSQAQClient(settings)
    alerts: list[dict[str, Any]] = []
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    # 读取前日告警（用于 delta 计算）
    yesterday = (datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ))
    from datetime import timedelta
    yesterday_str = (yesterday - timedelta(days=1)).strftime("%Y%m%d")
    prev_alerts_path = _alerts_dir(settings.cache_path) / f"{yesterday_str}.jsonl"
    prev_scores: dict[str, float] = {}
    if prev_alerts_path.exists():
        for line in prev_alerts_path.read_text(encoding="utf-8").splitlines():
            try:
                a = json.loads(line)
                prev_scores[a.get("good_id", "")] = a.get("fused_score", 0.0)
            except json.JSONDecodeError:
                continue

    for i, item in enumerate(items):
        good_id = item["good_id"]
        try:
            # 调用双轨分析（FastAPI Query 参数默认值会被注入）
            result = await analyze_fused(
                good_id=good_id,
                period="1day",
                platform=1,
                key="sell_price",
                include_team=False,
            )
            fused_score = result.get("fused_score", 0.0)
            prev_score = prev_scores.get(good_id, 0.0)
            delta = round(fused_score - prev_score, 4)

            threshold = item.get("threshold", req.alert_threshold)
            triggered = (
                fused_score >= threshold
                or (prev_score > 0 and delta >= req.delta_threshold)
            )

            if triggered:
                alert = {
                    "good_id": good_id,
                    "good_name": item.get("good_name", ""),
                    "fused_score": fused_score,
                    "prev_score": prev_score,
                    "delta": delta,
                    "pattern": result.get("pattern", ""),
                    "phase": result.get("phase", ""),
                    "evidence": result.get("evidence", []),
                    "feature_mode": result.get("feature_mode", ""),
                    "weights_source": result.get("weights_source", ""),
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                }
                alerts.append(alert)

            # 每品之间间隔 2 秒（双轨分析含 2 个 monitor 请求）
            if i < len(items) - 1:
                await asyncio.sleep(2.0)

        except Exception as exc:
            LOGGER.warning("run-scan good_id=%s failed: %s", good_id, exc)

    # 落盘告警
    alerts_dir = _alerts_dir(settings.cache_path)
    alerts_dir.mkdir(parents=True, exist_ok=True)
    alerts_path = alerts_dir / f"{today_str}.jsonl"
    with alerts_path.open("a", encoding="utf-8") as f:
        for a in alerts:
            f.write(json.dumps(a, ensure_ascii=False, default=str) + "\n")

    # 可选 webhook 推送
    _push_webhook(alerts)

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/scout/run-scan", latency_ms, error=False)
    return {
        "total": len(items),
        "alerts": len(alerts),
        "date": today_str,
        "alerts_path": str(alerts_path),
        "alerts": alerts,
        "latency_ms": round(latency_ms, 2),
    }


@router.get("/alerts")
async def get_alerts(date: str | None = None) -> dict[str, Any]:
    """查询告警列表。

    Args:
        date: YYYYMMDD，默认今日
    """
    settings = Settings()
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = _alerts_dir(settings.cache_path) / f"{date}.jsonl"
    if not path.exists():
        return {"date": date, "alerts": [], "total": 0}

    alerts: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            alerts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return {"date": date, "alerts": alerts, "total": len(alerts)}


def _push_webhook(alerts: list[dict[str, Any]]) -> None:
    """可选 webhook 推送（配置 ALERT_WEBHOOK_URL 时启用）。"""
    import os
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "")
    if not webhook_url or not alerts:
        return

    try:
        import requests
        text = "📦 主力吸货告警\n" + "\n".join(
            f"- {a.get('good_name') or a.get('good_id')}: "
            f"融合分 {a.get('fused_score', 0):.2f} ({a.get('pattern', '')})"
            for a in alerts
        )
        # 飞书/钉钉通用格式
        payload = {"msg_type": "text", "content": {"text": text}}
        requests.post(webhook_url, json=payload, timeout=5)
        LOGGER.info("webhook pushed %d alerts", len(alerts))
    except Exception as exc:
        LOGGER.warning("webhook push failed: %s", exc)


# ── D3: 自动标注 ───────────────────────────────────────────


@router.post("/auto-label")
async def auto_label(req: AutoLabelRequest) -> dict[str, Any]:
    """对到期的未标注案例自动标注。

    扫描案例库中 created_at 满 horizon 天且 label=None 的 case，
    回看未来 horizon 天的价格走势，按阈值标注。

    F1 升级：启用 use_drawdown_constraint 时，正样本需 max_drawdown ≤ 阈值。
    """
    start = time.perf_counter()
    settings = Settings()

    from src.scenario_engine.case_store import load_cases, save_labeled_parquet
    from src.scenario_engine.labeling import label_cases_with_horizon
    from src.data.item_cache import load_item_ohlc

    cases = load_cases(settings.cache_path, req.category)
    if not cases:
        return {"total": 0, "labeled": 0, "skipped": 0}

    # 筛选到期未标注
    now = datetime.now(timezone.utc)
    to_label: list[dict[str, Any]] = []
    for c in cases:
        if c.get("label") is not None:
            continue
        ts = c.get("timestamp") or c.get("created_at") or ""
        if not ts:
            continue
        try:
            # 兼容多种时间格式
            t = ts if "T" in ts else ts.replace(" ", "T")
            ct = datetime.fromisoformat(t.replace("Z", "+00:00"))
            if (now - ct).days >= req.horizon:
                to_label.append(c)
        except Exception:
            continue

    if not to_label:
        return {"total": len(cases), "labeled": 0, "skipped": len(cases),
                "message": "无到期未标注案例"}

    # 加载相关 good_id 的 OHLC（用于回看标注）
    good_ids = {c.get("good_id") for c in to_label if c.get("good_id")}
    ohlc_cache: dict[str, Any] = {}
    for gid in good_ids:
        df = load_item_ohlc(gid, "1day", settings.cache_path, req.category)
        if df is not None:
            ohlc_cache[gid] = df

    labeled = label_cases_with_horizon(
        to_label,
        ohlc_cache,
        horizon=req.horizon,
        positive_threshold=req.positive_threshold,
        negative_threshold=req.negative_threshold,
    )

    # 写回 parquet
    all_labeled = [c for c in cases if c.get("label") is not None] + labeled
    save_labeled_parquet(all_labeled, settings.cache_path, req.category)

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/scout/auto-label", latency_ms, error=False)
    return {
        "total_cases": len(cases),
        "to_label": len(to_label),
        "labeled": len(labeled),
        "positive": sum(1 for c in labeled if c.get("label") == "positive"),
        "negative": sum(1 for c in labeled if c.get("label") == "negative"),
        "neutral": sum(1 for c in labeled if c.get("label") == "neutral"),
        "ohlc_loaded": len(ohlc_cache),
        "latency_ms": round(latency_ms, 2),
    }
