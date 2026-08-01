"""Tests for multi-timeframe scenario fusion."""

from __future__ import annotations

import pytest

from src.scenario_engine.multi_timeframe_fusion import (
    DEFAULT_PERIOD_WEIGHTS,
    fuse_timeframes,
)


def _scenario(name: str, direction: int, prob: float) -> dict:
    return {
        "name": name,
        "direction": direction,
        "probability": prob,
        "confidence": prob,
        "support": 90.0,
        "resistance": 110.0,
        "target": 120.0,
        "stop_loss": 85.0,
        "suggestion": "long" if direction > 0 else "short",
        "template_name": name,
    }


def test_fuse_timeframes_returns_normalized_probabilities():
    scenarios = {
        "1day": [_scenario("bull", 1, 0.7)],
        "4hour": [_scenario("bull", 1, 0.6)],
        "1hour": [_scenario("bear", -1, 0.5)],
    }
    fused = fuse_timeframes(scenarios)
    total = sum(c["probability"] for c in fused)
    assert abs(total - 1.0) < 0.01


def test_daily_weight_is_highest():
    weights = DEFAULT_PERIOD_WEIGHTS
    assert weights["1day"] > weights["4hour"] >= weights["1hour"]


def test_fuse_timeframes_aggregates_same_direction():
    scenarios = {
        "1day": [_scenario("bull", 1, 0.7)],
        "4hour": [_scenario("bull", 1, 0.6)],
    }
    fused = fuse_timeframes(scenarios)
    bullish = [c for c in fused if c["direction"] == 1]
    assert len(bullish) == 1
    assert "1day" in bullish[0]["contributing_periods"]
    assert "4hour" in bullish[0]["contributing_periods"]


def test_period_aliases_are_normalized():
    scenarios = {
        "1d": [_scenario("bull", 1, 0.7)],
        "4h": [_scenario("bear", -1, 0.5)],
        "h1": [_scenario("bull", 1, 0.4)],
    }
    fused = fuse_timeframes(scenarios)
    assert fused


def test_empty_timeframes_return_empty():
    assert fuse_timeframes({}) == []
