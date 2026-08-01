"""库存特征提取与双轨融合单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.scenario_engine.inventory_signals import (
    compute_inventory_signals,
    build_inventory_evidence,
)
from src.scenario_engine.accumulation_detector import (
    fuse_scores,
    _classify_fusion_pattern,
)


# ── inventory_signals 测试 ────────────────────────────────


def _now() -> datetime:
    return datetime(2025, 6, 1, tzinfo=timezone.utc)


def _holder(hold_count: int, steam_id: str = "s1") -> dict:
    return {"hold_count": hold_count, "steam_id": steam_id, "task_id": steam_id, "hold_value": 0}


def _trend(t_type: int, count: int, days_ago: int, steam_id: str = "s1") -> dict:
    t = _now() - timedelta(days=days_ago)
    return {"type": t_type, "count": count, "time": t.timestamp(), "steam_id": steam_id}


class TestComputeInventorySignals:
    """库存特征计算测试。"""

    def test_empty_inputs_returns_neutral(self):
        """空输入应返回低库存分（仅 team 中性分 0.5 贡献协同分）。"""
        result = compute_inventory_signals([], [], None, now=_now())
        # 集中0 + 净流入0.5(无持仓中性) + 活跃0 + 团队0.5
        # = 0×0.35 + 0.5×0.30 + 0×0.20 + 0.5×0.15 = 0.225
        assert result["inventory_score"] == pytest.approx(0.225, abs=0.01)
        assert result["top3_concentration"] == 0.0
        assert result["total_hold"] == 0
        assert result["net_inflow_7d"] == 0

    def test_high_concentration_yields_high_score(self):
        """TOP3 集中度 50%+ 应得满分。"""
        holders = [_holder(100, "s1"), _holder(50, "s2"), _holder(30, "s3"), _holder(20, "s4")]
        result = compute_inventory_signals(holders, [], None, now=_now())
        # top3 = 180, total = 200, ratio = 0.9 → 满分
        assert result["top3_concentration"] == 0.9
        assert result["signals"]["concentration"] == 1.0

    def test_low_concentration_returns_low_score(self):
        """筹码分散应得低分。"""
        holders = [_holder(10, f"s{i}") for i in range(20)]  # 20 人各持 10，极分散
        result = compute_inventory_signals(holders, [], None, now=_now())
        assert result["top3_concentration"] < 0.2
        assert result["signals"]["concentration"] < 0.4

    def test_net_inflow_positive_increases_score(self):
        """近7日净流入为正应得高分。"""
        holders = [_holder(100, "s1"), _holder(50, "s2")]
        trends = [_trend(1, 30, 1, "s1"), _trend(3, 20, 2, "s2")]  # 买入入库+库存增加
        result = compute_inventory_signals(holders, trends, None, now=_now())
        assert result["net_inflow_7d"] == 50
        assert result["signals"]["net_inflow"] > 0.5

    def test_net_outflow_decreases_score(self):
        """近7日净流出应得低分。"""
        holders = [_holder(100, "s1"), _holder(50, "s2")]
        trends = [_trend(2, 50, 1, "s1"), _trend(4, 30, 2, "s2")]  # 卖出出库+库存减少
        result = compute_inventory_signals(holders, trends, None, now=_now())
        assert result["net_inflow_7d"] == -80
        assert result["signals"]["net_inflow"] < 0.3

    def test_old_trends_excluded_from_7d(self):
        """7 天前的变动不应计入净流入。"""
        holders = [_holder(100, "s1")]
        trends = [_trend(1, 100, 10, "s1")]  # 10 天前
        result = compute_inventory_signals(holders, trends, None, now=_now())
        assert result["net_inflow_7d"] == 0

    def test_holder_activity_ratio(self):
        """活跃度 = 有变动的主力数 / 总主力数。"""
        holders = [_holder(100, f"s{i}") for i in range(4)]
        trends = [_trend(1, 10, 1, "s0"), _trend(1, 10, 1, "s1")]  # 2 个活跃
        result = compute_inventory_signals(holders, trends, None, now=_now())
        assert result["active_holder_count"] == 2
        assert result["active_ratio"] == 0.5
        assert result["signals"]["holder_activity"] == 1.0

    def test_team_confidence_mapped_to_score(self):
        """团队置信度直接映射为协同分。"""
        result = compute_inventory_signals([], [], 0.8, now=_now())
        assert result["signals"]["team_synergy"] == 0.8

        result_none = compute_inventory_signals([], [], None, now=_now())
        assert result_none["signals"]["team_synergy"] == 0.5  # None → 中性

    def test_string_count_field_parsed(self):
        """count 字段为字符串时应正确解析。"""
        trends = [{"type": "1", "count": "30", "time": _now().timestamp(), "steam_id": "s1"}]
        holders = [_holder(100, "s1")]
        result = compute_inventory_signals(holders, trends, None, now=_now())
        assert result["net_inflow_7d"] == 30

    def test_malformed_entries_ignored(self):
        """畸形数据条目应被忽略。"""
        holders = [_holder(100, "s1"), {"bad": "data"}, {"hold_count": None}]
        trends = [{"no_type": True}, {"type": 1, "count": 10, "time": _now().timestamp()}]
        result = compute_inventory_signals(holders, trends, None, now=_now())
        # 不应崩溃，且能正确统计有效数据
        assert result["total_hold"] == 100


class TestBuildInventoryEvidence:
    """证据链生成测试。"""

    def test_high_concentration_evidence(self):
        result = compute_inventory_signals(
            [_holder(100, "s1"), _holder(50, "s2"), _holder(30, "s3"), _holder(20, "s4")],
            [],
            None,
            now=_now(),
        )
        evidence = build_inventory_evidence(result)
        assert any("TOP3" in e and "控盘" in e for e in evidence)

    def test_net_inflow_evidence(self):
        trends = [_trend(1, 50, 1, "s1")]
        result = compute_inventory_signals([_holder(100, "s1")], trends, None, now=_now())
        evidence = build_inventory_evidence(result)
        assert any("加仓" in e for e in evidence)

    def test_team_evidence_only_when_high(self):
        result_low = compute_inventory_signals([], [], 0.3, now=_now())
        assert not any("团队" in e for e in build_inventory_evidence(result_low))

        result_high = compute_inventory_signals([], [], 0.8, now=_now())
        assert any("团队" in e for e in build_inventory_evidence(result_high))


# ── 双轨融合测试 ──────────────────────────────────────────


class TestFuseScores:
    """融合规则测试。"""

    def test_strong_pattern_both_high(self):
        """双高 → strong 模式 + 加分。"""
        result = fuse_scores(0.7, 0.7)
        assert result["pattern"] == "strong"
        assert result["fused_score"] > 0.7
        assert result["phase"] == "accumulation"

    def test_hidden_pattern_kline_low_inv_high(self):
        """K低库高 → hidden 模式（隐蔽吸货）+ 加成。"""
        result = fuse_scores(0.3, 0.8)
        assert result["pattern"] == "hidden"
        # hidden 加成 0.15
        expected = 0.3 * 0.4 + 0.8 * 0.6 + 0.15
        assert result["fused_score"] == pytest.approx(min(1.0, expected), abs=0.01)

    def test_weak_pattern_kline_high_inv_low(self):
        """K高库低 → weak 模式 - 减分。"""
        result = fuse_scores(0.7, 0.2)
        assert result["pattern"] == "weak"
        expected = 0.7 * 0.6 + 0.2 * 0.4 - 0.05
        assert result["fused_score"] == pytest.approx(expected, abs=0.01)

    def test_none_pattern_both_low(self):
        """双低 → none 模式。"""
        result = fuse_scores(0.2, 0.2)
        assert result["pattern"] == "none"
        assert result["phase"] == "distribution"

    def test_score_clipped_to_unit_range(self):
        """融合分应在 [0, 1] 内。"""
        result = fuse_scores(1.0, 1.0)
        assert result["fused_score"] <= 1.0
        result = fuse_scores(0.0, 0.0)
        assert result["fused_score"] >= 0.0

    def test_phase_thresholds(self):
        """阶段阈值：≥0.6 吸货 / ≤0.3 出货。"""
        assert fuse_scores(0.7, 0.7)["phase"] == "accumulation"
        assert fuse_scores(0.1, 0.1)["phase"] == "distribution"
        # 中间值
        mid = fuse_scores(0.45, 0.45)
        assert mid["phase"] == "neutral"

    def test_classify_boundaries(self):
        """模式边界值测试。"""
        assert _classify_fusion_pattern(0.55, 0.55) == "strong"
        assert _classify_fusion_pattern(0.35, 0.35) == "none"
        assert _classify_fusion_pattern(0.55, 0.35) == "weak"
        assert _classify_fusion_pattern(0.35, 0.55) == "hidden"
