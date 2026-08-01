"""Tests for dynamic template weights based on market regime."""

from __future__ import annotations

import pytest

from src.scenario_engine.template_weights import compute_template_weights


def test_weights_sum_to_one_when_normalized():
    weights = compute_template_weights("uptrend")
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    assert all(w >= 0 for w in weights.values())


def test_uptrend_boosts_bullish_trend_templates():
    weights = compute_template_weights("uptrend")
    assert weights["wave_extension_bullish"] > weights["wave_extension_bearish"]
    assert weights["five_wave_impulse_bullish"] > weights["five_wave_impulse_bearish"]


def test_downtrend_boosts_bearish_trend_templates():
    weights = compute_template_weights("downtrend")
    assert weights["wave_extension_bearish"] > weights["wave_extension_bullish"]
    assert weights["five_wave_impulse_bearish"] > weights["five_wave_impulse_bullish"]


def test_choppy_boosts_consolidation_and_reversal():
    weights = compute_template_weights("choppy")
    assert (
        weights["triangle_bullish"]
        > weights["five_wave_impulse_bullish"]
    )
    assert (
        weights["head_and_shoulders_top"]
        > weights["wave_extension_bearish"]
    )


def test_unknown_market_state_raises():
    with pytest.raises(ValueError, match="Unknown market_state"):
        compute_template_weights("sideways_crash")


def test_non_normalized_weights_are_not_rescaled():
    weights = compute_template_weights("choppy", normalize=False)
    assert all(w >= 0 for w in weights.values())
    # Base weight is 1.0; multipliers should keep every weight >= 0.7.
    assert all(w >= 0.7 for w in weights.values())
