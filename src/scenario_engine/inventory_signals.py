"""库存行为特征提取（双轨融合的第二轨）。

从 holders / trends / team_confidence 提取库存行为特征，用于与 K 线行为评分融合。

核心理念：库存不会骗人——货真在谁手里、主力在加仓还是出货，是 K 线之外
的独立验证维度。K 线可以人为做线，但持仓分布与买卖流水难以伪造。

四项库存特征：
1. TOP3 集中度：头部主力持仓占比，越高越像控盘
2. 近7日净流入：买入量 - 卖出量，正=加仓吸货
3. 持有者活跃度：近7日有变动的主力占比，越高越像在动作
4. 团队协同：跨品团队置信度，越高越像有组织资金

纯函数，无 IO，可单元测试。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

# ── trends type 约定（CSQAQ monitor）──
# 1=买入入库 3=库存增加 5=转移入库 → 多方（加仓）
# 2=卖出出库 4=库存减少 6=转移出库 → 空方（减仓）
INFLOW_TYPES = {1, 3, 5}
OUTFLOW_TYPES = {2, 4, 6}

# 集中度阈值：TOP3 占比 ≥50% 视为高控盘
HIGH_CONCENTRATION = 0.50
# 活跃度阈值：近7日有变动的主力占比
ACTIVITY_LOOKBACK_DAYS = 7


def _to_int(val: Any, default: int = 0) -> int:
    """安全转 int，容错 CSQAQ 返回的字符串/None。"""
    try:
        if val is None:
            return default
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _to_float(val: Any, default: float = 0.0) -> float:
    """安全转 float。"""
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _to_str(val: Any, default: str = "") -> str:
    """安全转 str。"""
    if val is None:
        return default
    return str(val)


def _parse_time(val: Any) -> datetime | None:
    """解析时间字段，兼容时间戳（秒/毫秒）与 ISO 字符串。"""
    if val is None:
        return None
    # 时间戳（int 或数字字符串）
    try:
        ts = float(val)
        # 毫秒 vs 秒：13 位以上视为毫秒
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (TypeError, ValueError):
        pass
    # ISO 字符串
    try:
        s = str(val).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _score_concentration(top3_ratio: float) -> float:
    """集中度评分：TOP3 占比越高得分越高。

    50%+ → 满分（高控盘）
    20%  → 0.5
    0%   → 0
    """
    if top3_ratio <= 0:
        return 0.0
    if top3_ratio >= HIGH_CONCENTRATION:
        return 1.0
    # 线性映射 [0, 0.5] → [0, 1]
    return min(1.0, top3_ratio / HIGH_CONCENTRATION)


def _score_net_inflow(net: float, total_hold: float) -> float:
    """净流入评分：相对总持仓的净买入比例。

    net/total ≥ 10% → 满分（强力加仓）
    net/total = 0   → 0.5（中性）
    net/total ≤ -10% → 0（出货）
    """
    if total_hold <= 0:
        return 0.5  # 无持仓数据，中性
    ratio = net / total_hold
    if ratio >= 0.10:
        return 1.0
    if ratio <= -0.10:
        return 0.0
    # [-0.1, 0.1] → [0, 1]，0 处 = 0.5
    return 0.5 + ratio * 5.0


def _score_activity(active_ratio: float) -> float:
    """活跃度评分：近7日有变动的主力占比越高越像在动作。"""
    if active_ratio <= 0:
        return 0.0
    if active_ratio >= 0.5:
        return 1.0
    # [0, 0.5] → [0, 1]
    return active_ratio / 0.5


def _score_team_synergy(team_confidence: float | None) -> float:
    """团队协同评分：团队置信度直接映射。

    None（无团队数据）→ 0.5（中性，不奖不罚）
    """
    if team_confidence is None:
        return 0.5
    return max(0.0, min(1.0, team_confidence))


def compute_inventory_signals(
    holders: list[dict[str, Any]],
    trends: list[dict[str, Any]],
    team_confidence: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """计算库存行为特征与综合评分。

    Args:
        holders: 持有者列表（来自 /monitor/get_good_rank）。
            预期字段：hold_count, hold_value, steam_id/task_id。
        trends: 库存变动列表（来自 /monitor/get_task_trends）。
            预期字段：type, count, time, steam_id/task_id。
        team_confidence: 团队识别置信度（来自 team_analyzer）。None 表示无团队数据。
        now: 当前时间（测试注入用），默认 UTC now。

    Returns:
        库存特征字典，含 4 项子分 + 综合分 + 原始统计。
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=ACTIVITY_LOOKBACK_DAYS)

    # ── 1. 集中度 ──
    hold_counts = [_to_int(h.get("hold_count")) for h in holders]
    total_hold = sum(hold_counts)
    # 按持有量降序
    sorted_counts = sorted(hold_counts, reverse=True)
    top3_hold = sum(sorted_counts[:3])
    top3_ratio = (top3_hold / total_hold) if total_hold > 0 else 0.0

    # ── 2. 近7日净流入 ──
    recent_inflow = 0
    recent_outflow = 0
    active_holder_ids: set[str] = set()
    all_holder_ids: set[str] = set()

    for h in holders:
        hid = _to_str(h.get("steam_id") or h.get("task_id"))
        if hid:
            all_holder_ids.add(hid)

    for t in trends:
        t_type = _to_int(t.get("type"))
        t_count = _to_int(t.get("count"))
        t_time = _parse_time(t.get("time"))
        t_holder = _to_str(t.get("steam_id") or t.get("task_id"))

        is_recent = t_time is not None and t_time >= cutoff
        if t_type in INFLOW_TYPES:
            if is_recent:
                recent_inflow += t_count
                if t_holder:
                    active_holder_ids.add(t_holder)
        elif t_type in OUTFLOW_TYPES:
            if is_recent:
                recent_outflow += t_count
                if t_holder:
                    active_holder_ids.add(t_holder)

    net_inflow = recent_inflow - recent_outflow

    # ── 3. 持有者活跃度 ──
    holder_total = len(all_holder_ids) if all_holder_ids else len(holders)
    active_ratio = (len(active_holder_ids) / holder_total) if holder_total > 0 else 0.0

    # ── 4. 团队协同 ──
    synergy_score = _score_team_synergy(team_confidence)

    # ── 子分计算 ──
    concentration_score = _score_concentration(top3_ratio)
    net_inflow_score = _score_net_inflow(net_inflow, total_hold)
    activity_score = _score_activity(active_ratio)
    team_score = synergy_score

    signals = {
        "concentration": round(concentration_score, 4),
        "net_inflow": round(net_inflow_score, 4),
        "holder_activity": round(activity_score, 4),
        "team_synergy": round(team_score, 4),
    }

    # ── 综合分：4 项加权 ──
    # 集中度(0.35) + 净流入(0.30) + 活跃度(0.20) + 团队(0.15)
    inventory_score = (
        concentration_score * 0.35
        + net_inflow_score * 0.30
        + activity_score * 0.20
        + team_score * 0.15
    )
    inventory_score = max(0.0, min(1.0, inventory_score))

    return {
        "inventory_score": round(inventory_score, 4),
        "signals": signals,
        # 原始统计（供证据链生成用）
        "top3_concentration": round(top3_ratio, 4),
        "total_hold": total_hold,
        "top3_hold": top3_hold,
        "net_inflow_7d": net_inflow,
        "recent_inflow": recent_inflow,
        "recent_outflow": recent_outflow,
        "active_holder_count": len(active_holder_ids),
        "holder_total": holder_total,
        "active_ratio": round(active_ratio, 4),
        "team_confidence": team_confidence,
    }


def build_inventory_evidence(inv: dict[str, Any]) -> list[str]:
    """根据库存特征生成人话证据链。"""
    evidence: list[str] = []
    sig = inv.get("signals", {})
    stats = inv

    # 集中度
    top3 = stats.get("top3_concentration", 0)
    if top3 >= 0.50:
        evidence.append(f"TOP3 主力持仓占比 {top3*100:.0f}%，高度控盘")
    elif top3 >= 0.30:
        evidence.append(f"TOP3 主力持仓占比 {top3*100:.0f}%，筹码较集中")
    elif top3 > 0:
        evidence.append(f"TOP3 主力持仓占比 {top3*100:.0f}%，筹码分散")

    # 净流入
    net = stats.get("net_inflow_7d", 0)
    if net > 0:
        evidence.append(f"近7日净流入 {net} 件，主力加仓")
    elif net < 0:
        evidence.append(f"近7日净流出 {abs(net)} 件，主力减仓")
    else:
        evidence.append("近7日库存变动平稳")

    # 活跃度
    active = stats.get("active_ratio", 0)
    if active >= 0.5:
        evidence.append(f"近7日 {stats.get('active_holder_count',0)} 个主力有动作（活跃度 {active*100:.0f}%）")
    elif active > 0:
        evidence.append(f"近7日少量主力有动作（活跃度 {active*100:.0f}%）")

    # 团队
    tc = stats.get("team_confidence")
    if tc is not None and tc >= 0.6:
        evidence.append(f"识别到跨品团队（置信度 {tc*100:.0f}%），疑似有组织资金")

    return evidence
