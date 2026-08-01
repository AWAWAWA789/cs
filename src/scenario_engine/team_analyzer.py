"""跨品主力团队识别引擎。

基于"同一批 Steam 用户在多个饰品上集中持仓"的假设，识别疑似大团队 / 大资金
协同操作。

算法流程：
1. 以种子品（用户选中的 good_id）的 top-N holders 为锚点
2. 拉取每个 holder 的全部持仓（跨品库存快照）
3. 构建 ``steam_id × good_id`` 持仓矩阵
4. 找出被多个种子主力共同持有的其他品（关联品）
5. 通过重合度、跨品数、集中度判定是否疑似团队操作

核心指标：
- 关联品重合度 = 持有该关联品的种子主力数 / 种子主力总数
- 核心团队规模 = 跨品数 ≥ 阈值的主力数
- 团队集中度 = 核心团队在种子品的合计持仓 / 种子品监控总持仓

纯函数设计：输入原始数据，输出结构化结果，无 IO，便于单元测试与缓存。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.api.logging import get_logger

LOGGER = get_logger("csqaq.team_analyzer")

# ── 启发式阈值 ────────────────────────────────────────────
# 这些阈值基于经验设定，可在调用方覆盖。
DEFAULT_MIN_OVERLAP = 2          # 关联品至少需要几个种子主力同时持有
DEFAULT_CORE_CROSS_ITEMS = 3     # 核心团队成员至少跨多少个品
DEFAULT_CORE_HOLD_RATIO = 0.4    # 核心团队在种子品的持仓占比阈值
DEFAULT_OVERLAP_RATIO = 0.3      # 关联品重合度阈值


def _to_int(value: Any, default: int = 0) -> int:
    """安全转 int，容错 None / 字符串 / 浮点。"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default


def _to_float(value: Any, default: float = 0.0) -> float:
    """安全转 float。"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _to_str(value: Any, default: str = "") -> str:
    """安全转 str，None → 空串。"""
    if value is None:
        return default
    return str(value)


def _extract_holder_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """从 /monitor/get_good_rank 返回的单条 holder 中抽取关键字段（防御性）。

    CSQAQ 字段可能为 task_id / steam_id / steam_name / avatar / hold_count /
    hold_value，但不同接口返回可能略有差异，这里统一兜底。
    """
    return {
        "task_id": _to_str(raw.get("task_id")),
        "steam_id": _to_str(raw.get("steam_id") or raw.get("steamid") or raw.get("uid")),
        "steam_name": _to_str(raw.get("steam_name") or raw.get("name") or raw.get("nickname")),
        "avatar": _to_str(raw.get("avatar")),
        "hold_count": _to_int(raw.get("hold_count") or raw.get("count")),
        "hold_value": _to_float(raw.get("hold_value") or raw.get("value")),
    }


def _extract_inventory_item(raw: dict[str, Any]) -> dict[str, Any]:
    """从 /task/get_task_all 返回的单条持仓中抽取关键字段（防御性）。

    返回字段统一为 good_id / good_name / good_img / hold_count / hold_value。
    """
    return {
        "good_id": _to_str(raw.get("good_id") or raw.get("id") or raw.get("goods_id")),
        "good_name": _to_str(raw.get("good_name") or raw.get("name") or raw.get("value")),
        "good_img": _to_str(raw.get("good_img") or raw.get("img") or raw.get("image")),
        "hold_count": _to_int(raw.get("hold_count") or raw.get("count") or raw.get("num")),
        "hold_value": _to_float(raw.get("hold_value") or raw.get("value") or raw.get("total_value")),
    }


def _parse_inventory_list(raw: Any) -> list[dict[str, Any]]:
    """解析 user-inventory 响应为持仓列表（防御性）。

    /task/get_task_all 返回结构可能是 ``{data: [...]}`` 或 ``{data: {list: [...]}}``
    或直接 ``[...]``，这里统一兜底。
    """
    items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        candidates = raw
    elif isinstance(raw, dict):
        data = raw.get("data")
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            inner = data.get("list") or data.get("items") or data.get("goods")
            candidates = inner if isinstance(inner, list) else []
        else:
            candidates = []
    else:
        candidates = []

    for item in candidates:
        if not isinstance(item, dict):
            continue
        parsed = _extract_inventory_item(item)
        if not parsed["good_id"]:
            continue
        items.append(parsed)
    return items


def _parse_holders(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """解析 holders 原始列表为统一字段。"""
    return [_extract_holder_fields(h) for h in raw if isinstance(h, dict)]


def analyze_team(
    seed_good_id: str,
    seed_holders_raw: list[dict[str, Any]],
    holders_inventory_raw: dict[str, Any],
    *,
    min_overlap: int = DEFAULT_MIN_OVERLAP,
    core_cross_items: int = DEFAULT_CORE_CROSS_ITEMS,
    core_hold_ratio: float = DEFAULT_CORE_HOLD_RATIO,
    overlap_ratio_threshold: float = DEFAULT_OVERLAP_RATIO,
) -> dict[str, Any]:
    """执行跨品主力团队识别分析。

    Args:
        seed_good_id: 种子品 good_id（用户选中的饰品）
        seed_holders_raw: 种子品 holder 排行原始数据（/monitor/get_good_rank 的 data）
        holders_inventory_raw: ``{steam_id: <user-inventory 原始响应>}``，每个
            seed holder 的全量持仓数据
        min_overlap: 关联品最少需要的种子主力重合数
        core_cross_items: 核心团队成员至少跨多少个品
        core_hold_ratio: 核心团队在种子品的持仓占比阈值（判定疑似团队）
        overlap_ratio_threshold: 关联品重合度阈值

    Returns:
        结构化分析结果（见模块文档字符串）。
    """
    holders = _parse_holders(seed_holders_raw)
    seed_holder_count = len(holders)

    # 种子品总持仓（用于集中度计算）
    seed_total_hold = sum(h["hold_count"] for h in holders)

    # ── 1. 构建 steam_id → 跨品持仓映射 ───────────────────
    # steam_cross[steam_id] = {good_id: {hold_count, good_name, good_img, hold_value}}
    steam_cross: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    # holder 基础信息（用于结果展示）
    steam_meta: dict[str, dict[str, Any]] = {}
    # 种子主力在种子品的持仓（用于集中度）
    seed_hold_by_steam: dict[str, int] = {}

    for h in holders:
        steam_id = h["steam_id"]
        if not steam_id:
            continue
        steam_meta[steam_id] = {
            "steam_id": steam_id,
            "steam_name": h["steam_name"],
            "avatar": h["avatar"],
            "task_id": h["task_id"],
            "hold_in_seed": h["hold_count"],
        }
        seed_hold_by_steam[steam_id] = h["hold_count"]

        # 拉取该 holder 的全量持仓
        inv_raw = holders_inventory_raw.get(steam_id) or holders_inventory_raw.get(h["task_id"])
        inventory = _parse_inventory_list(inv_raw)
        # 排除种子品自身（避免把种子品计入跨品）
        for item in inventory:
            gid = item["good_id"]
            if gid == seed_good_id:
                continue
            steam_cross[steam_id][gid] = {
                "hold_count": item["hold_count"],
                "hold_value": item["hold_value"],
                "good_name": item["good_name"],
                "good_img": item["good_img"],
            }

    # ── 2. 构建关联品统计：哪些品被多个种子主力同时持有 ────
    # related_good[good_id] = {holders: [steam_id, ...], total_hold, total_value, good_name, good_img}
    related_good: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "holders": [],
            "total_hold": 0,
            "total_value": 0.0,
            "good_name": "",
            "good_img": "",
        }
    )

    for steam_id, goods in steam_cross.items():
        for gid, info in goods.items():
            entry = related_good[gid]
            entry["holders"].append(steam_id)
            entry["total_hold"] += info["hold_count"]
            entry["total_value"] += info["hold_value"]
            if not entry["good_name"]:
                entry["good_name"] = info["good_name"]
            if not entry["good_img"]:
                entry["good_img"] = info["good_img"]

    # 过滤：重合数 < min_overlap 的关联品不视为团队信号
    related_items: list[dict[str, Any]] = []
    for gid, entry in related_good.items():
        overlap_count = len(entry["holders"])
        if overlap_count < min_overlap:
            continue
        overlap_ratio = overlap_count / seed_holder_count if seed_holder_count else 0.0
        related_items.append({
            "good_id": gid,
            "good_name": entry["good_name"],
            "good_img": entry["good_img"],
            "overlap_count": overlap_count,
            "overlap_ratio": round(overlap_ratio, 4),
            "total_hold_in_team": entry["total_hold"],
            "total_value_in_team": round(entry["total_value"], 2),
            "shared_steam_ids": entry["holders"],
            "shared_steam_names": [
                steam_meta.get(sid, {}).get("steam_name", sid) for sid in entry["holders"]
            ],
        })

    # 按重合度降序，同重合度按总持仓降序
    related_items.sort(key=lambda x: (x["overlap_count"], x["total_hold_in_team"]), reverse=True)

    # ── 3. 主力跨品分布 ─────────────────────────────────
    holders_cross: list[dict[str, Any]] = []
    for steam_id, meta in steam_meta.items():
        cross_goods = steam_cross.get(steam_id, {})
        cross_good_ids = list(cross_goods.keys())
        cross_count = len(cross_good_ids)
        holders_cross.append({
            "steam_id": steam_id,
            "steam_name": meta["steam_name"],
            "avatar": meta["avatar"],
            "hold_in_seed": meta["hold_in_seed"],
            "cross_item_count": cross_count,
            "cross_good_ids": cross_good_ids,
            "is_core": cross_count >= core_cross_items,
        })
    # 按跨品数降序，同数按种子品持仓降序
    holders_cross.sort(key=lambda x: (x["cross_item_count"], x["hold_in_seed"]), reverse=True)

    # ── 4. 团队指标汇总 ─────────────────────────────────
    core_team = [h for h in holders_cross if h["is_core"]]
    core_team_size = len(core_team)
    core_team_hold_in_seed = sum(h["hold_in_seed"] for h in core_team)
    core_team_ratio = (
        core_team_hold_in_seed / seed_total_hold if seed_total_hold else 0.0
    )
    max_overlap_ratio = related_items[0]["overlap_ratio"] if related_items else 0.0
    max_overlap_count = related_items[0]["overlap_count"] if related_items else 0
    avg_cross = (
        sum(h["cross_item_count"] for h in holders_cross) / len(holders_cross)
        if holders_cross
        else 0.0
    )

    # 疑似团队判定（启发式）：
    # 条件 A：存在重合度 >= overlap_ratio_threshold 且重合数 >= min_overlap 的关联品
    has_strong_overlap = any(
        r["overlap_ratio"] >= overlap_ratio_threshold for r in related_items
    )
    # 条件 B：核心团队规模 >= 2 且在种子品集中度 >= core_hold_ratio
    has_core_team = core_team_size >= 2 and core_team_ratio >= core_hold_ratio

    is_likely_team = has_strong_overlap or has_core_team

    # 置信度：综合最大重合度与核心团队集中度
    confidence = min(
        1.0,
        max_overlap_ratio * 0.5 + min(1.0, core_team_ratio) * 0.5,
    )

    # 判定理由
    reasons: list[str] = []
    if has_strong_overlap:
        top = related_items[0]
        reasons.append(
            f"发现关联品「{top['good_name'] or top['good_id']}」被 "
            f"{top['overlap_count']}/{seed_holder_count} 个种子主力共同持有"
            f"（重合度 {top['overlap_ratio']:.0%}）"
        )
    if has_core_team:
        reasons.append(
            f"核心团队 {core_team_size} 人（跨≥{core_cross_items}品），"
            f"占种子品持仓 {core_team_ratio:.0%}"
        )
    if not reasons:
        reasons.append("未发现明显跨品协同持仓信号，主力分散或独立操作")

    return {
        "seed_good_id": seed_good_id,
        "seed_holder_count": seed_holder_count,
        "analyzed_holder_count": len(steam_meta),
        "related_items": related_items,
        "team_summary": {
            "core_team_size": core_team_size,
            "core_team_hold_in_seed": core_team_hold_in_seed,
            "core_team_ratio_in_seed": round(core_team_ratio, 4),
            "max_overlap_ratio": round(max_overlap_ratio, 4),
            "max_overlap_count": max_overlap_count,
            "avg_cross_items_per_holder": round(avg_cross, 2),
            "related_item_count": len(related_items),
            "is_likely_team_operated": is_likely_team,
            "confidence": round(confidence, 4),
            "reason": "；".join(reasons),
        },
        "holders_cross": holders_cross,
    }
