"""双轨融合引擎。

将 Phase 10 的历史相似性搜索结果与 Phase 11 的预定义模板匹配结果进行融合，
输出统一的情景候选集合。融合规则完全基于价格行为与市场状态，不依赖成交量，
也不硬编码具体板块。
"""

from __future__ import annotations

from typing import Any

import numpy as np


DEFAULT_SIMILARITY_WEIGHT = 0.45
DEFAULT_TEMPLATE_WEIGHT = 0.55

DEFAULT_MUTUALLY_EXCLUSIVE_PAIRS: list[tuple[set[str], set[str]]] = [
    ({"double_bottom_bullish"}, {"double_top_bearish"}),
    ({"flag_bullish"}, {"flag_bearish"}),
    ({"five_wave_impulse_bullish"}, {"five_wave_impulse_bearish"}),
    ({"triangle_bullish"}, {"triangle_bearish"}),
    ({"wave_extension_bullish"}, {"wave_extension_bearish"}),
    ({"head_and_shoulders_top"}, {"head_and_shoulders_bottom"}),
]


SCENARIO_DIRECTIONS: dict[str, int] = {
    "bullish": 1,
    "bearish": -1,
    "both": 0,
    "neutral": 0,
}


def _direction_to_int(direction: Any) -> int:
    """将方向描述转换为整数：1 看多、-1 看空、0 中性。"""
    if isinstance(direction, (int, float)):
        return int(np.sign(direction))
    if isinstance(direction, str):
        return SCENARIO_DIRECTIONS.get(direction.lower(), 0)
    return 0


def _softmax(values: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """带温度缩放的 softmax 归一化。"""
    if len(values) == 0:
        return values
    arr = np.asarray(values, dtype=float)
    if temperature <= 0:
        temperature = 1e-6
    scaled = arr / temperature
    max_val = np.max(scaled)
    exps = np.exp(scaled - max_val)
    return exps / (np.sum(exps) + 1e-12)


def _similarity_candidates(
    similarity_results: list[dict[str, Any]],
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    """从历史相似性结果中提取方向候选。

    根据未来 5 根 K 线收益率的方向与幅度打分，最多返回 ``max_candidates`` 个。

    相似度置信度使用 ``exp(-distance / sigma)`` 映射到 (0, 1]，其中 ``sigma``
    取本批候选距离的中位数。这样可避免旧的 ``1 - distance`` 公式在 z-score
    归一化的 15 维状态向量上几乎恒为 0（典型最近邻距离 3-6），导致相似性
    轨道对融合完全没有贡献。
    """
    if not similarity_results:
        return []

    top = similarity_results[:max_candidates]
    positive_distances = [float(r.get("distance", 0.0)) for r in top if float(r.get("distance", 0.0)) > 0]
    sigma = float(np.median(positive_distances)) if positive_distances else 1.0
    if sigma <= 0:
        sigma = 1.0

    candidates: list[dict[str, Any]] = []
    for r in top:
        # 显式 None 判断：避免 ``or`` 把恰好为 0.0 的 5 日收益当作假值而
        # 错误地回退到 7 日收益，导致方向误判。
        ret = r.get("future_return_5")
        if ret is None:
            ret = r.get("future_return_7", 0.0)
        ret = float(ret)
        direction = _direction_to_int(ret)
        distance = float(r.get("distance", 0.0))
        confidence = float(np.exp(-distance / sigma))
        candidates.append(
            {
                "source": "similarity",
                "direction": direction,
                "confidence": confidence,
                "raw_score": abs(ret) * confidence,
                "future_return": ret,
                "distance": distance,
                "similarity": confidence,
            }
        )
    return candidates


def _template_candidates(
    template_results: list[dict[str, Any]],
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    """从模板匹配结果中提取概率与方向候选。"""
    if not template_results:
        return []

    sorted_matches = sorted(
        template_results,
        key=lambda m: m.get("confidence", 0.0),
        reverse=True,
    )

    candidates: list[dict[str, Any]] = []
    for m in sorted_matches[:max_candidates]:
        direction = _direction_to_int(m.get("direction", "both"))
        confidence = float(m.get("confidence", 0.0))
        prior = float(m.get("probability_prior", 0.5))
        candidates.append(
            {
                "source": "template",
                "template_name": m.get("template_name"),
                "direction": direction,
                "confidence": confidence,
                "raw_score": prior * confidence,
                "probability_prior": prior,
                "support": m.get("support"),
                "resistance": m.get("resistance"),
                "target": m.get("target"),
                "stop_loss": m.get("stop_loss"),
                "suggestion": m.get("suggestion", "neutral"),
            }
        )
    return candidates


def _resolve_conflict(
    sim: dict[str, Any],
    tmpl: dict[str, Any],
    similarity_weight: float,
    template_weight: float,
) -> dict[str, Any]:
    """对单个相似性候选与单个模板候选进行冲突处理。"""
    sim_dir = int(sim.get("direction", 0))
    tmpl_dir = int(tmpl.get("direction", 0))

    sim_score = float(sim.get("raw_score", 0.0))
    tmpl_score = float(tmpl.get("raw_score", 0.0))

    if sim_dir == tmpl_dir:
        # 同向强化：提升概率，加权平均取高分侧。
        fused_score = max(sim_score, tmpl_score) * 1.15
        confidence = min(
            1.0,
            (sim["confidence"] * similarity_weight + tmpl["confidence"] * template_weight)
            * 1.1,
        )
        direction = sim_dir if sim_dir != 0 else tmpl_dir
        conflict_strategy = "reinforce"
    elif sim_dir == 0 or tmpl_dir == 0:
        # 其中一方中性，按加权平均处理但不下调置信度。
        fused_score = similarity_weight * sim_score + template_weight * tmpl_score
        confidence = (
            sim["confidence"] * similarity_weight + tmpl["confidence"] * template_weight
        )
        direction = sim_dir if sim_dir != 0 else tmpl_dir
        conflict_strategy = "neutral_blend"
    else:
        # 反向折中：取加权平均并降低置信度。
        fused_score = similarity_weight * sim_score + template_weight * tmpl_score
        confidence = (
            sim["confidence"] * similarity_weight + tmpl["confidence"] * template_weight
        ) * 0.7
        direction = int(
            np.sign(similarity_weight * sim_dir + template_weight * tmpl_dir)
        )
        conflict_strategy = "compromise"

    return {
        "source": "fused",
        "direction": direction,
        "confidence": round(float(confidence), 6),
        "raw_score": round(float(fused_score), 6),
        "conflict_strategy": conflict_strategy,
        "similarity": sim,
        "template": tmpl,
    }


def _apply_mutual_exclusion(
    candidates: list[dict[str, Any]],
    exclusive_pairs: list[tuple[set[str], set[str]]] | None = None,
    discount: float = 0.6,
) -> list[dict[str, Any]]:
    """对同时触发的互斥模板对进行权重降级。"""
    pairs = exclusive_pairs or DEFAULT_MUTUALLY_EXCLUSIVE_PAIRS
    if not pairs:
        return candidates

    def _name(cand: dict[str, Any]) -> str | None:
        tmpl = cand.get("template")
        if isinstance(tmpl, dict):
            return tmpl.get("template_name") or cand.get("template_name")
        return cand.get("template_name")

    template_names = {_name(c) for c in candidates if _name(c)}
    active_pairs: set[int] = set()
    for idx, (set_a, set_b) in enumerate(pairs):
        if template_names & set_a and template_names & set_b:
            active_pairs.add(idx)

    if not active_pairs:
        return candidates

    adjusted = []
    for c in candidates:
        name = _name(c)
        multiplier = 1.0
        if name:
            for idx, (set_a, set_b) in enumerate(pairs):
                if idx in active_pairs and name in (set_a | set_b):
                    multiplier = min(multiplier, discount)
        if multiplier < 1.0:
            c = dict(c)
            c["raw_score"] = float(c.get("raw_score", 0.0)) * multiplier
            c["confidence"] = float(c.get("confidence", 0.0)) * multiplier
            c["mutual_exclusion_applied"] = True
        adjusted.append(c)
    return adjusted


def fuse_results(
    similarity_results: list[dict[str, Any]],
    template_results: list[dict[str, Any]],
    *,
    similarity_weight: float = DEFAULT_SIMILARITY_WEIGHT,
    template_weight: float = DEFAULT_TEMPLATE_WEIGHT,
    max_candidates: int = 5,
    temperature: float = 0.5,
    exclusive_pairs: list[tuple[set[str], set[str]]] | None = None,
    mutual_exclusion_discount: float = 0.6,
) -> list[dict[str, Any]]:
    """融合历史相似性搜索结果与模板匹配结果。

    Args:
        similarity_results: Phase 10 相似性搜索结果，每个元素至少包含
            ``distance`` 与 ``future_return_5``（或 ``future_return_7``）。
        template_results: Phase 11 模板匹配结果，每个元素包含 ``direction``、
            ``confidence``、``probability_prior`` 与可选的价位字段。
        similarity_weight: 相似性轨道权重。
        template_weight: 模板轨道权重。
        max_candidates: 每条轨道最多保留的候选数。
        temperature: 候选概率 softmax 温度，越小分布越尖锐。
        exclusive_pairs: 互斥模板名称对。默认为常见多空成对模板。
        mutual_exclusion_discount: 互斥同时触发时的权重折扣。

    Returns:
        融合后的情景候选列表，按概率降序排列。每个元素包含 ``name``、
        ``probability``、``direction``、``confidence``、``source``、
        ``support`` / ``resistance`` / ``target`` / ``stop_loss`` 等字段。
    """
    total_weight = similarity_weight + template_weight
    if total_weight <= 0:
        similarity_weight = template_weight = 0.5
    else:
        similarity_weight = similarity_weight / total_weight
        template_weight = template_weight / total_weight

    sim_cands = _similarity_candidates(similarity_results, max_candidates)
    tmpl_cands = _template_candidates(template_results, max_candidates)

    fused: list[dict[str, Any]] = []

    if sim_cands and tmpl_cands:
        # 为每个模板候选挑选最佳相似性候选，保留所有模板方向。
        for tmpl in tmpl_cands:
            best_sim = max(
                sim_cands,
                key=lambda s: _alignment_score(s, tmpl),
            )
            fused.append(
                _resolve_conflict(best_sim, tmpl, similarity_weight, template_weight)
            )
    elif sim_cands:
        for sim in sim_cands:
            fused.append(
                {
                    "source": "similarity",
                    "direction": sim["direction"],
                    "confidence": sim["confidence"],
                    "raw_score": sim["raw_score"],
                    "conflict_strategy": "single_track",
                    "similarity": sim,
                    "template": None,
                }
            )
    elif tmpl_cands:
        for tmpl in tmpl_cands:
            fused.append(
                {
                    "source": "template",
                    "template_name": tmpl.get("template_name"),
                    "direction": tmpl["direction"],
                    "confidence": tmpl["confidence"],
                    "raw_score": tmpl["raw_score"],
                    "conflict_strategy": "single_track",
                    "similarity": None,
                    "template": tmpl,
                    "support": tmpl.get("support"),
                    "resistance": tmpl.get("resistance"),
                    "target": tmpl.get("target"),
                    "stop_loss": tmpl.get("stop_loss"),
                    "suggestion": tmpl.get("suggestion"),
                }
            )

    # 合并来自同一模板的重复候选，保留得分最高者。
    by_template: dict[str, dict[str, Any]] = {}
    standalone = []
    for c in fused:
        name = c.get("template", {}).get("template_name") if c.get("template") else None
        if name:
            if name not in by_template or c["raw_score"] > by_template[name]["raw_score"]:
                by_template[name] = c
        else:
            standalone.append(c)

    fused = list(by_template.values()) + standalone

    # 互斥降级。
    fused = _apply_mutual_exclusion(fused, exclusive_pairs, mutual_exclusion_discount)

    if not fused:
        return []

    scores = np.array([c["raw_score"] for c in fused], dtype=float)
    probabilities = _softmax(scores, temperature)

    final: list[dict[str, Any]] = []
    for cand, prob in zip(fused, probabilities):
        record = dict(cand)
        record["name"] = _candidate_name(record)
        record["probability"] = round(float(prob), 6)
        tmpl_dict = record.get("template") or {}
        record["template_name"] = tmpl_dict.get("template_name") or record.get("template_name")
        record["support"] = record.get("support") or tmpl_dict.get("support")
        record["resistance"] = record.get("resistance") or tmpl_dict.get("resistance")
        record["target"] = record.get("target") or tmpl_dict.get("target")
        record["stop_loss"] = record.get("stop_loss") or tmpl_dict.get("stop_loss")
        record["suggestion"] = record.get("suggestion") or tmpl_dict.get("suggestion", "neutral")
        final.append(record)

    final.sort(key=lambda x: x["probability"], reverse=True)
    return final


def _alignment_score(sim: dict[str, Any], tmpl: dict[str, Any]) -> float:
    """衡量相似性候选与模板候选的方向一致性，用于挑选最佳配对。"""
    if sim["direction"] == tmpl["direction"]:
        return 1.0 + sim["confidence"] + tmpl["confidence"]
    if sim["direction"] == 0 or tmpl["direction"] == 0:
        return 0.5 + sim["confidence"] + tmpl["confidence"]
    return 0.0


def _candidate_name(candidate: dict[str, Any]) -> str:
    """为融合候选生成可读名称。"""
    tmpl = candidate.get("template")
    if tmpl and tmpl.get("template_name"):
        return f"fused_{tmpl['template_name']}"
    direction = candidate.get("direction", 0)
    if direction > 0:
        return "fused_bullish_similarity"
    if direction < 0:
        return "fused_bearish_similarity"
    return "fused_neutral_similarity"
