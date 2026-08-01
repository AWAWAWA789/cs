"""Tests for Bayesian probability calibration."""

from __future__ import annotations

import pytest

from src.scenario_engine.bayesian_calibration import (
    build_evidence_histogram,
    calibrate_probabilities,
    compute_brier_score,
    evaluate_calibration,
)


def _candidates() -> list[dict]:
    return [
        {"name": "bull", "direction": "bullish", "probability": 0.6},
        {"name": "bear", "direction": "bearish", "probability": 0.4},
    ]


def _similarity(direction: int, horizon: int = 5, n: int = 10) -> list[dict]:
    key = f"future_return_{horizon}"
    return [{key: 0.03 if direction > 0 else -0.03} for _ in range(n)]


def test_build_evidence_histogram_counts_matches():
    sim = _similarity(1, n=8) + _similarity(-1, n=4)
    hist = build_evidence_histogram(sim, horizon=5)
    # 每个方向键都包含全部历史片段，统计该方向实际发生的比例。
    assert hist["bullish"]["total"] == 12
    assert hist["bullish"]["occurred"] == 8
    assert hist["bearish"]["total"] == 12
    assert hist["bearish"]["occurred"] == 4
    assert abs(hist["bullish"]["likelihood"] - 8 / 12) < 1e-9


def test_calibrate_probabilities_sum_to_one():
    cands = _candidates()
    sim = _similarity(1, n=10) + _similarity(-1, n=5)
    calibrated = calibrate_probabilities(cands, sim)
    total = sum(c["calibrated_probability"] for c in calibrated)
    assert abs(total - 1.0) < 0.01


def test_calibrate_adds_bayesian_fields():
    cands = _candidates()
    sim = _similarity(1, n=10)
    calibrated = calibrate_probabilities(cands, sim)
    for c in calibrated:
        for key in ("prior", "likelihood", "evidence", "posterior", "calibrated_probability"):
            assert key in c


def test_temperature_scaling_changes_distribution():
    cands = _candidates()
    sim = _similarity(1, n=10) + _similarity(-1, n=10)
    cold = calibrate_probabilities(cands, sim, temperature=0.1)
    hot = calibrate_probabilities(cands, sim, temperature=2.0)
    cold_max = max(c["calibrated_probability"] for c in cold)
    hot_max = max(c["calibrated_probability"] for c in hot)
    assert cold_max > hot_max


def test_laplace_smooth_with_no_evidence():
    cands = _candidates()
    calibrated = calibrate_probabilities(cands, [], laplace_alpha=1.0)
    assert all(c["likelihood"] == 0.5 for c in calibrated)


def test_compute_brier_score():
    assert compute_brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0, abs=1e-9)
    assert compute_brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25, abs=1e-9)


def test_evaluate_calibration_returns_brier_score():
    cands = _candidates()
    sim = _similarity(1, n=10) + _similarity(-1, n=10)
    calibrated = calibrate_probabilities(cands, sim)
    metrics = evaluate_calibration(calibrated, sim)
    assert "brier_score" in metrics
    assert 0.0 <= metrics["brier_score"] <= 1.0


def test_likelihood_computed_without_truncation():
    """似然计数应保留浮点精度，避免 int() 截断。"""
    cands = [{"direction": 1, "probability": 0.6}]
    # 12 个历史片段，7 个同方向 -> raw_likelihood = 7/12
    sim = [{"future_return_5": 0.03} if i < 7 else {"future_return_5": -0.02} for i in range(12)]
    calibrated = calibrate_probabilities(cands, sim, laplace_alpha=1.0)
    # (7 + 1) / (12 + 2) = 8/14
    assert calibrated[0]["likelihood"] == pytest.approx(8 / 14, abs=1e-6)


def test_scenario_key_level_likelihood():
    """不同 bullish 情景在提供 matched_scenario 时应拥有不同似然。"""
    candidates = [
        {"name": "bullish_continuation", "direction": 1, "probability": 0.5},
        {"name": "dip_then_rise", "direction": 1, "probability": 0.5},
    ]
    similarity = [
        {"future_return_5": 0.05, "matched_scenario": "bullish_continuation"},
        {"future_return_5": 0.02, "matched_scenario": "dip_then_rise"},
        {"future_return_5": -0.01, "matched_scenario": "dip_then_rise"},
    ]
    result = calibrate_probabilities(candidates, similarity, laplace_alpha=0.0)
    cont_likelihood = next(r["likelihood"] for r in result if r["name"] == "bullish_continuation")
    dip_likelihood = next(r["likelihood"] for r in result if r["name"] == "dip_then_rise")
    # bullish_continuation 在 1 个样本中命中 1 次
    assert cont_likelihood == pytest.approx(1.0, abs=1e-6)
    # dip_then_rise 在 2 个样本中命中 1 次
    assert dip_likelihood == pytest.approx(0.5, abs=1e-6)
