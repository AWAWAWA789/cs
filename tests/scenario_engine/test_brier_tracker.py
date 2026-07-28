"""Tests for the Brier score tracker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.scenario_engine.brier_tracker import (
    compute_brier,
    evaluate_direction_accuracy_report,
    generate_brier_report,
)


def test_compute_brier_perfect_calibration():
    """When probability always equals outcome, Brier score is zero."""
    probs = [1.0, 0.0, 1.0, 0.0]
    outcomes = [1, 0, 1, 0]
    result = compute_brier(probs, outcomes)
    assert result["brier_score"] == 0.0
    assert result["n_samples"] == 4


def test_compute_brier_always_wrong():
    """When probability is always opposite to outcome, Brier score is one."""
    probs = [1.0, 1.0, 0.0, 0.0]
    outcomes = [0, 0, 1, 1]
    result = compute_brier(probs, outcomes)
    assert result["brier_score"] == 1.0


def test_compute_brier_empty_inputs():
    """Empty inputs should return zero statistics without error."""
    result = compute_brier([], [])
    assert result["brier_score"] == 0.0
    assert result["n_samples"] == 0


def test_compute_brier_length_mismatch_raises():
    """Mismatched lengths should raise ValueError."""
    with pytest.raises(ValueError):
        compute_brier([0.5], [1, 0])


def test_compute_brier_known_value():
    """Brier score for a single 0.7 probability and positive outcome is 0.09."""
    result = compute_brier([0.7], [1])
    assert result["brier_score"] == pytest.approx(0.09, abs=1e-6)


def test_evaluate_direction_accuracy_report_structure():
    """The evaluated report should contain aggregate and per-sub-index Brier."""
    report = {
        "sub_indices": ["手套", "匕首"],
        "horizons": [5, 7],
        "walk_forward_params": {"min_bars": 200, "step_bars": 20},
        "per_sub_index": {
            "手套": {
                "samples": [
                    {"probability": 0.8, "hit_5": True, "hit_7": False},
                    {"probability": 0.6, "hit_5": True, "hit_7": True},
                ]
            },
            "匕首": {
                "samples": [
                    {"probability": 0.7, "hit_5": False, "hit_7": False},
                    {"probability": 0.9, "hit_5": True, "hit_7": True},
                ]
            },
        },
    }
    result = evaluate_direction_accuracy_report(report)
    assert set(result.keys()) >= {"aggregate", "per_sub_index", "sub_indices", "horizons"}
    assert "horizon_5" in result["aggregate"]
    assert "horizon_7" in result["aggregate"]
    assert result["per_sub_index"]["手套"]["horizon_5"]["n_samples"] == 2


def test_evaluate_direction_accuracy_report_skips_neutral():
    """Neutral predictions (hit is None) should be excluded from Brier."""
    report = {
        "sub_indices": ["手套"],
        "horizons": [5],
        "walk_forward_params": {},
        "per_sub_index": {
            "手套": {
                "samples": [
                    {"probability": 0.8, "hit_5": True},
                    {"probability": 0.6, "hit_5": None},
                ]
            }
        },
    }
    result = evaluate_direction_accuracy_report(report)
    assert result["aggregate"]["horizon_5"]["n_samples"] == 1


def test_generate_brier_report_writes_json(tmp_path: Path):
    """generate_brier_report should read a direction report and write JSON."""
    input_path = tmp_path / "direction_accuracy.json"
    output_path = tmp_path / "brier.json"
    report = {
        "sub_indices": ["手套"],
        "horizons": [5],
        "walk_forward_params": {},
        "per_sub_index": {
            "手套": {
                "samples": [
                    {"probability": 1.0, "hit_5": True},
                    {"probability": 0.0, "hit_5": False},
                ]
            }
        },
    }
    input_path.write_text(json.dumps(report), encoding="utf-8")

    result_path = generate_brier_report(input_path, output_path)
    assert result_path == output_path
    assert output_path.exists()

    content = json.loads(output_path.read_text(encoding="utf-8"))
    assert content["aggregate"]["horizon_5"]["brier_score"] == 0.0
