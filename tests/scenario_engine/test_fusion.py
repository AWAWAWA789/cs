"""Tests for the dual-track fusion engine."""

from __future__ import annotations

import pytest

from src.scenario_engine.fusion import (
    DEFAULT_MUTUALLY_EXCLUSIVE_PAIRS,
    fuse_results,
)


def _similarity_results(direction: int, distance: float = 0.3) -> list[dict]:
    future_return = 0.05 if direction > 0 else -0.05
    return [
        {
            "distance": distance,
            "future_return_5": future_return,
        }
    ]


def _template_results(name: str, direction: str, confidence: float = 0.8) -> list[dict]:
    return [
        {
            "template_name": name,
            "direction": direction,
            "confidence": confidence,
            "probability_prior": 0.55,
            "support": 90.0,
            "resistance": 110.0,
            "target": 120.0,
            "stop_loss": 85.0,
            "suggestion": "long" if direction == "bullish" else "short",
        }
    ]


def test_fuse_results_returns_normalized_probabilities():
    sim = _similarity_results(1)
    tmpl = _template_results("flag_bullish", "bullish")
    fused = fuse_results(sim, tmpl)
    assert fused
    total = sum(c["probability"] for c in fused)
    assert abs(total - 1.0) < 0.01


def test_same_direction_reinforces():
    sim = _similarity_results(1, distance=0.2)
    tmpl = _template_results("flag_bullish", "bullish", confidence=0.9)
    fused = fuse_results(sim, tmpl)
    bullish = [c for c in fused if c["direction"] == 1]
    assert bullish
    assert bullish[0]["conflict_strategy"] == "reinforce"


def test_opposite_direction_compromises():
    sim = _similarity_results(1, distance=0.2)
    tmpl = _template_results("flag_bearish", "bearish", confidence=0.9)
    fused = fuse_results(sim, tmpl)
    assert any(c["conflict_strategy"] == "compromise" for c in fused)


def test_mutual_exclusion_discounts():
    sim = _similarity_results(1)
    tmpl = (
        _template_results("flag_bullish", "bullish", confidence=0.9)
        + _template_results("flag_bearish", "bearish", confidence=0.9)
    )
    fused = fuse_results(sim, tmpl)
    names = {c.get("template_name") for c in fused}
    assert any(c.get("mutual_exclusion_applied") for c in fused)
    assert names & {"flag_bullish", "flag_bearish"}


def test_empty_inputs_return_empty():
    assert fuse_results([], []) == []
    assert fuse_results([{"distance": 0.5, "future_return_5": 0.01}], []) != []


def test_fusion_preserves_key_levels():
    sim = _similarity_results(1)
    tmpl = _template_results("double_bottom_bullish", "bullish")
    fused = fuse_results(sim, tmpl)
    assert fused
    for key in ("support", "resistance", "target", "stop_loss"):
        assert fused[0].get(key) is not None


def test_default_exclusive_pairs_cover_bull_bear():
    names = set()
    for a, b in DEFAULT_MUTUALLY_EXCLUSIVE_PAIRS:
        names.update(a)
        names.update(b)
    assert "flag_bullish" in names
    assert "flag_bearish" in names
