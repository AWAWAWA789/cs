"""贝叶斯概率校准模块。

以模板理论概率或融合概率为先验 P(scenario)，以历史相似片段中该情景实际
发生的频率为似然 P(evidence|scenario)，输出后验 P(scenario|evidence)。
支持温度缩放与拉普拉斯平滑，所有计算仅依赖 OHLC 与时间，不依赖成交量。
"""

from __future__ import annotations

from typing import Any

import numpy as np


DEFAULT_TEMPERATURE = 1.0
DEFAULT_LAPLACE_ALPHA = 1.0
DEFAULT_HORIZON = 5


def _direction_to_int(direction: Any) -> int:
    """将方向描述转换为整数：1 看多、-1 看空、0 中性。"""
    if isinstance(direction, (int, float)):
        return int(np.sign(direction))
    if isinstance(direction, str):
        return {"bullish": 1, "bearish": -1, "both": 0, "neutral": 0}.get(
            direction.lower(), 0
        )
    return 0


def _label_for_direction(direction: int) -> str:
    """将方向整数映射为情景标签。"""
    if direction > 0:
        return "bullish"
    if direction < 0:
        return "bearish"
    return "neutral"


def _scenario_key(candidate: dict[str, Any]) -> str:
    """根据候选名称生成情景键；无名称时回退到方向标签。"""
    tmpl_name = candidate.get("template_name") or candidate.get("name", "")
    if tmpl_name:
        return tmpl_name
    direction = _direction_to_int(candidate.get("direction", 0))
    return _label_for_direction(direction)


def _temperature_scale(probs: np.ndarray, temperature: float) -> np.ndarray:
    """对概率分布进行温度缩放。"""
    if temperature <= 0:
        temperature = 1e-6
    log_probs = np.log(np.asarray(probs, dtype=float) + 1e-12)
    scaled = log_probs / temperature
    max_val = np.max(scaled)
    exps = np.exp(scaled - max_val)
    return exps / (np.sum(exps) + 1e-12)


def _laplace_smooth(counts: np.ndarray, alpha: float) -> np.ndarray:
    """对计数进行拉普拉斯平滑。"""
    alpha = max(0.0, alpha)
    return (counts + alpha) / (np.sum(counts) + alpha * len(counts))


def build_evidence_histogram(
    similarity_results: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
    horizon: int = DEFAULT_HORIZON,
) -> dict[str, dict[str, Any]]:
    """从历史相似片段中统计各方向情景实际发生的频率。

    若提供 candidates，则按 ``{scenario_key}_{direction}`` 键统计，
    区分不同 bullish / bearish 情景；否则按方向级聚合。

    Args:
        similarity_results: Phase 10 相似性搜索结果列表。
        candidates: 可选的候选情景列表，用于生成情景键。
        horizon: 用于计算收益率的 K 线数量。

    Returns:
        每个情景键对应的统计字典，包含 ``occurred``、``total`` 与
        ``likelihood``。
    """
    key_returns: dict[str, list[tuple[float, int]]] = {}
    key = f"future_return_{horizon}"

    labels = ("bullish", "bearish", "neutral")

    if candidates:
        candidate_keys = {_scenario_key(c): c for c in candidates}
        direction_only_keys = set(candidate_keys.keys()) <= set(labels)

        if direction_only_keys:
            # 候选未提供名称时回退到方向级聚合，保持与旧逻辑一致。
            for r in similarity_results:
                ret = r.get(key)
                if ret is None:
                    continue
                for label in labels:
                    key_returns.setdefault(label, []).append(
                        (float(ret), _direction_to_int(label))
                    )
        else:
            for r in similarity_results:
                ret = r.get(key)
                if ret is None:
                    continue
                ret_direction_int = _direction_to_int(ret)
                ret_direction = _label_for_direction(ret_direction_int)
                matched = r.get("matched_scenario") or r.get("scenario_key")
                if matched and matched in candidate_keys:
                    label = matched
                    expected_direction = _direction_to_int(
                        candidate_keys[matched].get("direction", 0)
                    )
                else:
                    label = ret_direction
                    expected_direction = ret_direction_int
                key_returns.setdefault(label, []).append(
                    (float(ret), expected_direction)
                )
    else:
        for r in similarity_results:
            ret = r.get(key)
            if ret is None:
                continue
            for label in labels:
                key_returns.setdefault(label, []).append(
                    (float(ret), _direction_to_int(label))
                )

    histogram: dict[str, dict[str, Any]] = {}
    for label, entries in key_returns.items():
        returns = [r for r, _ in entries]
        expected_direction = entries[0][1]
        occurred = sum(1 for r in returns if _direction_to_int(r) == expected_direction)
        total = len(returns)
        histogram[label] = {
            "occurred": occurred,
            "total": total,
            "likelihood": occurred / total if total > 0 else 0.5,
            "mean_return": float(np.mean(returns)) if returns else 0.0,
        }
    return histogram


def calibrate_probabilities(
    candidates: list[dict[str, Any]],
    similarity_results: list[dict[str, Any]],
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    laplace_alpha: float = DEFAULT_LAPLACE_ALPHA,
    horizon: int = DEFAULT_HORIZON,
    min_prior: float = 0.01,
) -> list[dict[str, Any]]:
    """对情景候选进行贝叶斯校准。

    后验 = 先验 × 似然 / 证据，其中证据为所有候选后验的归一化常数。
    先验来自候选自身的 ``probability`` 或 ``probability_prior``；似然来自
    历史相似片段中同方向实际发生的频率。

    Args:
        candidates: 融合后的情景候选列表。
        similarity_results: Phase 10 相似性搜索结果，用于估计似然。
        temperature: softmax 温度，控制后验分布的尖锐程度。
        laplace_alpha: 拉普拉斯平滑系数，用于处理历史片段不足的情况。
        horizon: 计算未来收益率的 K 线数量。
        min_prior: 先验概率下限，防止零先验导致后验为零。

    Returns:
        每个候选添加了 ``prior``、``likelihood``、``evidence``、
        ``posterior`` 与 ``calibrated_probability`` 字段的列表。
    """
    if not candidates:
        return []

    histogram = build_evidence_histogram(
        similarity_results, candidates=candidates, horizon=horizon
    )

    priors: list[float] = []
    likelihoods: list[float] = []

    for cand in candidates:
        prior = float(
            cand.get("probability")
            or cand.get("probability_prior")
            or cand.get("raw_score")
            or 0.5
        )
        prior = max(min_prior, min(1.0, prior))
        priors.append(prior)

        direction = _direction_to_int(cand.get("direction", 0))
        label = _label_for_direction(direction)
        key = _scenario_key(cand)
        evidence_info = histogram.get(
            key, histogram.get(label, {"total": 0, "likelihood": 0.5})
        )
        total = evidence_info.get("total", 0)
        raw_likelihood = evidence_info.get("likelihood", 0.5)

        if total == 0:
            likelihood = raw_likelihood
        else:
            occurred = float(raw_likelihood * total)
            counts = np.array([occurred, total - occurred], dtype=float)
            smoothed = _laplace_smooth(counts, laplace_alpha)
            likelihood = float(smoothed[0])
        likelihoods.append(likelihood)

    priors_arr = np.array(priors, dtype=float)
    likelihoods_arr = np.array(likelihoods, dtype=float)
    unnorm_posterior = priors_arr * likelihoods_arr
    evidence = np.sum(unnorm_posterior)
    if evidence <= 0:
        evidence = 1e-12

    posteriors = unnorm_posterior / evidence
    calibrated = _temperature_scale(posteriors, temperature)

    # 总证据样本量：用于向前端暴露"校准可信度"。当历史相似片段不足时，
    # 后验主要反映先验，概率分布会偏均匀，前端可据此提示"校准数据不足"。
    total_evidence_samples = sum(
        int(histogram.get(_scenario_key(c), {}).get("total", 0)
            if histogram.get(_scenario_key(c))
            else histogram.get(_label_for_direction(_direction_to_int(c.get("direction", 0))), {}).get("total", 0))
        for c in candidates
    )
    if total_evidence_samples >= 20:
        calibration_confidence = "adequate"
    elif total_evidence_samples >= 5:
        calibration_confidence = "limited"
    else:
        calibration_confidence = "low"

    calibrated_candidates: list[dict[str, Any]] = []
    for cand, prior, likelihood, posterior, cal_prob in zip(
        candidates, priors, likelihoods, posteriors, calibrated
    ):
        record = dict(cand)
        record["prior"] = round(float(prior), 6)
        record["likelihood"] = round(float(likelihood), 6)
        record["evidence"] = round(float(evidence), 6)
        record["posterior"] = round(float(posterior), 6)
        record["calibrated_probability"] = round(float(cal_prob), 6)
        record["probability"] = record["calibrated_probability"]
        record["calibration_confidence"] = calibration_confidence
        calibrated_candidates.append(record)

    return calibrated_candidates


def compute_brier_score(
    probabilities: list[float],
    outcomes: list[int],
) -> float:
    """计算 Brier 分数：概率预测与实际二值结果的均方误差。

    Args:
        probabilities: 模型输出的概率列表，取值范围 [0, 1]。
        outcomes: 实际结果列表，1 表示事件发生，0 表示未发生。

    Returns:
        Brier 分数，越低表示校准越好。
    """
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same length")
    if not probabilities:
        return 0.0

    probs = np.asarray(probabilities, dtype=float)
    outs = np.asarray(outcomes, dtype=int)
    return float(np.mean((probs - outs) ** 2))


def evaluate_calibration(
    calibrated_candidates: list[dict[str, Any]],
    similarity_results: list[dict[str, Any]],
    *,
    horizon: int = DEFAULT_HORIZON,
) -> dict[str, Any]:
    """评估校准质量并返回 Brier 分数等摘要指标。

    Args:
        calibrated_candidates: 已校准的情景候选列表。
        similarity_results: 历史相似片段结果。
        horizon: 未来收益 horizon。

    Returns:
        包含 ``brier_score``、``n_samples``、``mean_probability`` 与
        ``mean_outcome`` 的字典。
    """
    key = f"future_return_{horizon}"
    probs: list[float] = []
    outcomes: list[int] = []

    for cand in calibrated_candidates:
        direction = _direction_to_int(cand.get("direction", 0))
        if direction == 0:
            continue
        prob = float(cand.get("calibrated_probability", 0.0))
        probs.append(prob)
        # 用历史相似片段的平均同方向发生频率作为近似真实结果。
        label = _label_for_direction(direction)
        hits = sum(
            1
            for r in similarity_results
            if r.get(key) is not None
            and _label_for_direction(_direction_to_int(r.get(key, 0))) == label
        )
        total = sum(1 for r in similarity_results if r.get(key) is not None)
        outcome = 1 if total > 0 and hits / total >= 0.5 else 0
        outcomes.append(outcome)

    return {
        "brier_score": round(compute_brier_score(probs, outcomes), 6),
        "n_samples": len(probs),
        "mean_probability": round(float(np.mean(probs)) if probs else 0.0, 6),
        "mean_outcome": round(float(np.mean(outcomes)) if outcomes else 0.0, 6),
    }
