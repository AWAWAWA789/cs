#!/usr/bin/env python
"""每日库存快照采集 + 自动标注 + 增量训练调度（阶段 C+D 飞轮）。

设计为 cron / systemd timer 调用，建议每日 03:00 UTC 执行：
    0 3 * * * cd /workspace && python scripts/collect_inventory_daily.py >> logs/scout.log 2>&1

或 systemd timer:
    [Unit]
    Description=Daily inventory snapshot collection

    [Service]
    Type=oneshot
    WorkingDirectory=/workspace
    ExecStart=/usr/bin/env python scripts/collect_inventory_daily.py

流程（顺序执行，前一步失败不阻塞后续）：
1. 加载 watchlist
2. 采集当日库存快照（每个品 2 个请求，1 req/s 限流）
3. 自动标注到期案例（满 30 天未标注的）
4. 增量训练（标注后触发）

输出 JSON 汇总到 stdout，便于日志聚合。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# 让脚本能从项目根目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.client import CSQAQClient
from src.api.logging import get_logger
from src.config import Settings
from src.data.inventory_snapshot import collect_watchlist_snapshots

LOGGER = get_logger("csqaq.scout_daily")


def main() -> int:
    """每日调度入口。"""
    start = time.time()
    settings = Settings()
    if not settings.api_token:
        LOGGER.error("CSQAQ_API_TOKEN 未配置，跳过")
        return 1

    # 1. 加载 watchlist
    watchlist_path = Path(settings.cache_path) / "watchlist.json"
    if not watchlist_path.exists():
        LOGGER.info("watchlist 为空，跳过采集")
        print(json.dumps({"status": "skipped", "reason": "empty_watchlist"}))
        return 0

    items = json.loads(watchlist_path.read_text(encoding="utf-8"))
    if not items:
        LOGGER.info("watchlist 为空，跳过采集")
        print(json.dumps({"status": "skipped", "reason": "empty_watchlist"}))
        return 0

    good_ids = [it["good_id"] for it in items]
    LOGGER.info("启动每日采集: %d 个品", len(good_ids))

    # 2. 采集库存快照
    client = CSQAQClient(settings)
    collect_result = collect_watchlist_snapshots(
        good_ids, client, settings.cache_path, force=False,
    )
    LOGGER.info(
        "采集完成: success=%d skipped=%d failed=%d (%.1fs)",
        collect_result["success"], collect_result["skipped"],
        collect_result["failed"], collect_result["duration_sec"],
    )

    # 3. 自动标注（如有到期案例）
    label_result = {"labeled": 0}
    try:
        from src.scenario_engine.case_store import load_cases, save_labeled_parquet
        from src.scenario_engine.labeling import label_cases_with_horizon
        from src.data.item_cache import load_item_ohlc
        from datetime import datetime, timezone

        cases = load_cases(settings.cache_path, "rifle")
        now = datetime.now(timezone.utc)
        to_label = []
        for c in cases:
            if c.get("label") is not None:
                continue
            ts = c.get("timestamp") or ""
            if not ts:
                continue
            try:
                t = ts if "T" in ts else ts.replace(" ", "T")
                ct = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if (now - ct).days >= 30:
                    to_label.append(c)
            except Exception:
                continue

        if to_label:
            good_set = {c.get("good_id") for c in to_label if c.get("good_id")}
            ohlc_cache = {}
            for gid in good_set:
                df = load_item_ohlc(gid, "1day", settings.cache_path, "rifle")
                if df is not None:
                    ohlc_cache[gid] = df

            labeled = label_cases_with_horizon(to_label, ohlc_cache)
            label_result = {
                "to_label": len(to_label),
                "labeled": len(labeled),
                "positive": sum(1 for c in labeled if c.get("label") == "positive"),
                "negative": sum(1 for c in labeled if c.get("label") == "negative"),
                "neutral": sum(1 for c in labeled if c.get("label") == "neutral"),
            }
            all_labeled = [c for c in cases if c.get("label") is not None] + labeled
            save_labeled_parquet(all_labeled, settings.cache_path, "rifle")
            LOGGER.info("自动标注: %s", label_result)
    except Exception as exc:
        LOGGER.warning("自动标注失败（不影响整体）: %s", exc)
        label_result = {"error": str(exc)}

    # 4. 增量训练（标注后触发，可选）
    train_result = {"trained": False}
    try:
        labeled_cases = [c for c in load_cases(settings.cache_path, "rifle")
                         if c.get("label") is not None]
        if len(labeled_cases) >= 20:
            from src.scenario_engine.trainer import train_rule_weights
            result = train_rule_weights(labeled_cases, settings.cache_path, "rifle")
            train_result = {
                "trained": result.get("trained", False),
                "train_accuracy": result.get("train_accuracy"),
                "train_size": result.get("train_size"),
            }
            LOGGER.info("增量训练: %s", train_result)
        else:
            train_result = {"skipped": f"labeled_cases={len(labeled_cases)} < 20"}
    except Exception as exc:
        LOGGER.warning("增量训练失败（不影响整体）: %s", exc)
        train_result = {"error": str(exc)}

    duration = round(time.time() - start, 1)
    summary = {
        "status": "ok",
        "date": collect_result["date"],
        "collect": collect_result,
        "label": label_result,
        "train": train_result,
        "duration_sec": duration,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
