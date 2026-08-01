"""team_analyzer 跨品主力团队识别单元测试。"""

from __future__ import annotations

from src.scenario_engine.team_analyzer import analyze_team


# ── 测试夹具 ───────────────────────────────────────────────

# 种子品 3 个主力
SEED_HOLDERS = [
    {"task_id": "t1", "steam_id": "s1", "steam_name": "Alice", "hold_count": 100, "hold_value": 5000},
    {"task_id": "t2", "steam_id": "s2", "steam_name": "Bob", "hold_count": 80, "hold_value": 4000},
    {"task_id": "t3", "steam_id": "s3", "steam_name": "Carol", "hold_count": 50, "hold_value": 2500},
]

# 3 个主力的全量持仓（都持有 Y，2 个持有 Z，1 个持有 W）
# 种子品 X 自身应被排除
INVENTORIES = {
    "s1": {
        "data": [
            {"good_id": "X", "good_name": "Seed", "hold_count": 100, "hold_value": 5000},  # 种子品，应排除
            {"good_id": "Y", "good_name": "Knife", "hold_count": 50, "hold_value": 3000},
            {"good_id": "Z", "good_name": "Gloves", "hold_count": 20, "hold_value": 1000},
            {"good_id": "W", "good_name": "Sticker", "hold_count": 10, "hold_value": 200},
        ]
    },
    "s2": {
        "data": [
            {"good_id": "Y", "good_name": "Knife", "hold_count": 40, "hold_value": 2400},
            {"good_id": "Z", "good_name": "Gloves", "hold_count": 15, "hold_value": 750},
        ]
    },
    "s3": {
        "data": [
            {"good_id": "Y", "good_name": "Knife", "hold_count": 30, "hold_value": 1800},
        ]
    },
}


def test_seed_good_excluded_from_related_items():
    """种子品自身应被排除出关联品列表。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=1)
    related_ids = {r["good_id"] for r in result["related_items"]}
    assert "X" not in related_ids


def test_overlap_count_and_ratio():
    """关联品 Y 应被 3 个主力共同持有（重合度 100%）。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=2)
    y = next(r for r in result["related_items"] if r["good_id"] == "Y")
    assert y["overlap_count"] == 3
    assert y["overlap_ratio"] == 1.0
    # 团队合计持仓 = 50 + 40 + 30 = 120
    assert y["total_hold_in_team"] == 120
    assert y["total_value_in_team"] == 7200.0


def test_min_overlap_filter():
    """min_overlap=3 时，只有 Y（3人重合）应入选，Z（2人）被过滤。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=3)
    related_ids = {r["good_id"] for r in result["related_items"]}
    assert "Y" in related_ids
    assert "Z" not in related_ids


def test_related_items_sorted_by_overlap_desc():
    """关联品应按重合数降序排列（Y=3 在 Z=2 之前）。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=2)
    overlaps = [r["overlap_count"] for r in result["related_items"]]
    assert overlaps == sorted(overlaps, reverse=True)


def test_holders_cross_counts():
    """主力跨品分布应正确统计跨品数。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=1)
    holders_by_name = {h["steam_name"]: h for h in result["holders_cross"]}
    # Alice 持有 Y/Z/W（排除种子品 X）= 3 个跨品
    assert holders_by_name["Alice"]["cross_item_count"] == 3
    # Bob 持有 Y/Z = 2 个跨品
    assert holders_by_name["Bob"]["cross_item_count"] == 2
    # Carol 持有 Y = 1 个跨品
    assert holders_by_name["Carol"]["cross_item_count"] == 1


def test_core_team_identification():
    """跨品数 >= core_cross_items(默认3) 的主力应标记为核心团队。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=1)
    holders_by_name = {h["steam_name"]: h for h in result["holders_cross"]}
    # Alice 跨 3 品 → 核心
    assert holders_by_name["Alice"]["is_core"] is True
    # Bob 跨 2 品 → 非核心
    assert holders_by_name["Bob"]["is_core"] is False


def test_team_likely_operated_when_strong_overlap():
    """存在重合度 >= 0.3 的关联品时应判定为疑似团队操作。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=2)
    summary = result["team_summary"]
    # Y 重合度 100% >= 0.3 → 疑似团队
    assert summary["is_likely_team_operated"] is True
    assert summary["max_overlap_ratio"] == 1.0
    assert summary["max_overlap_count"] == 3


def test_no_team_signal_when_disjoint():
    """主力持仓完全不相交时不应判定为团队。"""
    disjoint_inv = {
        "s1": {"data": [{"good_id": "A", "hold_count": 10}]},
        "s2": {"data": [{"good_id": "B", "hold_count": 10}]},
        "s3": {"data": [{"good_id": "C", "hold_count": 10}]},
    }
    result = analyze_team("X", SEED_HOLDERS, disjoint_inv, min_overlap=2)
    summary = result["team_summary"]
    # 无任何关联品（每个品只有1人持有）
    assert summary["related_item_count"] == 0
    assert summary["is_likely_team_operated"] is False
    assert summary["max_overlap_ratio"] == 0.0


def test_defensive_parsing_handles_malformed_data():
    """异常数据结构不应导致崩溃。"""
    # 3 个有效 holder（带缺字段的也保留）
    malformed_holders = [
        {"steam_id": "s1", "steam_name": "A", "hold_count": 10},
        {"steam_id": "s2", "steam_name": "B", "hold_count": 5},
        "not_a_dict",  # 非 dict，应被过滤
    ]
    # inventory 数据畸形：s1 是字符串、s2 的 data 是字符串、s3 缺 hold_count
    malformed_inv = {
        "s1": "not_a_dict",
        "s2": {"data": [{"good_id": "Y", "good_name": "Knife"}]},  # 缺 hold_count，应默认 0
    }
    # 不应抛异常；seed_holder_count 仅计有效 dict 记录（2 个）
    result = analyze_team("X", malformed_holders, malformed_inv, min_overlap=1)
    assert result["seed_holder_count"] == 2
    # Y 应被 s2 持有（hold_count 默认 0），但 s1 的 inventory 畸形被解析为空
    y_items = [r for r in result["related_items"] if r["good_id"] == "Y"]
    assert len(y_items) == 1
    assert y_items[0]["total_hold_in_team"] == 0


def test_empty_holders_returns_zero_team():
    """无种子主力时应返回空结果。"""
    result = analyze_team("X", [], {}, min_overlap=2)
    assert result["seed_holder_count"] == 0
    assert result["analyzed_holder_count"] == 0
    assert result["related_items"] == []
    assert result["holders_cross"] == []
    assert result["team_summary"]["is_likely_team_operated"] is False


def test_shared_steam_names_populated():
    """关联品应包含共同持有主力的名称列表。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=2)
    y = next(r for r in result["related_items"] if r["good_id"] == "Y")
    assert set(y["shared_steam_names"]) == {"Alice", "Bob", "Carol"}
    assert set(y["shared_steam_ids"]) == {"s1", "s2", "s3"}


def test_confidence_bounded_0_to_1():
    """置信度应在 [0, 1] 范围内。"""
    result = analyze_team("X", SEED_HOLDERS, INVENTORIES, min_overlap=2)
    conf = result["team_summary"]["confidence"]
    assert 0.0 <= conf <= 1.0
