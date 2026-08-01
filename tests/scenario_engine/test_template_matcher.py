"""Tests for the scenario template matcher."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.template_matcher import (
    TemplateError,
    load_templates,
    match_templates,
)


def _pattern_df(
    pivots: list[tuple[int, str, float]],
    n: int = 80,
) -> pd.DataFrame:
    """Build a synthetic OHLC DataFrame around a list of swing pivots.

    Each pivot is ``(index, type, price)``.  The surrounding two bars are
    deliberately placed lower/higher so that ``identify_swing_points`` with
    ``order=2`` recognises the pivot.
    """
    indices = sorted({p[0] for p in pivots} | {0, n - 1})
    pivot_map = {idx: (typ, price) for idx, typ, price in pivots}

    sorted_pivots = sorted(pivots, key=lambda x: x[0])
    base_prices = np.zeros(n)
    for i in range(n):
        if i <= sorted_pivots[0][0]:
            base_prices[i] = sorted_pivots[0][2]
        elif i >= sorted_pivots[-1][0]:
            base_prices[i] = sorted_pivots[-1][2]
        else:
            left = [p for p in sorted_pivots if p[0] <= i][-1]
            right = [p for p in sorted_pivots if p[0] > i][0]
            weight = (i - left[0]) / (right[0] - left[0])
            base_prices[i] = left[2] + weight * (right[2] - left[2])

    df = pd.DataFrame(
        {
            "open": base_prices.copy(),
            "high": base_prices + 0.05,
            "low": base_prices - 0.05,
            "close": base_prices.copy(),
        }
    )

    # Make non-pivot bars realistically volatile so ATR is comparable to the
    # size of the pattern (otherwise the synthetic ATR is tiny and the
    # ``atr_multiple`` conditions reject the pattern).
    pivot_indices = {idx for idx, _, _ in pivots}
    for i in range(n):
        if i in pivot_indices:
            continue
        if any(abs(i - p[0]) <= 2 for p in pivots):
            continue
        df.loc[i, "high"] = base_prices[i] + 0.8
        df.loc[i, "low"] = base_prices[i] - 0.8

    for idx, typ, price in pivots:
        if typ == "high":
            for offset in (-2, -1, 1, 2):
                if 0 <= idx + offset < n:
                    df.loc[idx + offset, "high"] = price - 0.2 - 0.05 * abs(offset)
                    df.loc[idx + offset, "low"] = price - 0.25
                    df.loc[idx + offset, "close"] = price - 0.2
            df.loc[idx, "high"] = price + 0.4
            df.loc[idx, "low"] = price - 0.05
            df.loc[idx, "close"] = price
            df.loc[idx, "open"] = price
        else:
            for offset in (-2, -1, 1, 2):
                if 0 <= idx + offset < n:
                    df.loc[idx + offset, "low"] = price + 0.2 + 0.05 * abs(offset)
                    df.loc[idx + offset, "high"] = price + 0.25
                    df.loc[idx + offset, "close"] = price + 0.2
            df.loc[idx, "low"] = price - 0.4
            df.loc[idx, "high"] = price + 0.05
            df.loc[idx, "close"] = price
            df.loc[idx, "open"] = price

    return df


def test_load_default_templates_contains_required_ones():
    templates = load_templates()
    names = {t["name"] for t in templates}
    required = {
        "wave_extension_bullish",
        "five_wave_impulse_bearish",
        "triangle_bullish",
        "flag_bearish",
        "head_and_shoulders_top",
        "double_bottom_bullish",
    }
    assert required.issubset(names)
    assert len(names) == len(templates)


def test_match_templates_requires_ohlc():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="open, high, low, close"):
        match_templates(df)


def test_match_templates_does_not_add_volume():
    df = _pattern_df([(10, "low", 100.0), (20, "high", 110.0)])
    matches = match_templates(df, min_confidence=0.3)
    assert "volume" not in df.columns
    assert "volume" not in (matches[0].keys() if matches else [])


def test_wave_extension_bullish_is_detected():
    df = _pattern_df(
        [
            (10, "low", 100.0),
            (18, "high", 110.0),
            (24, "low", 104.0),
            (32, "high", 125.0),
        ]
    )
    # Break out above the third-wave high.
    df.loc[33:, "close"] = 126.0
    df.loc[33:, "high"] = 127.0
    df.loc[33:, "low"] = 125.0
    df.loc[32, "close"] = 125.0
    matches = match_templates(df, min_confidence=0.3)
    bullish = [m for m in matches if m["template_name"] == "wave_extension_bullish"]
    assert len(bullish) >= 1
    match = bullish[-1]
    assert match["direction"] == "bullish"
    assert match["support"] < match["resistance"] < match["target"]
    assert match["stop_loss"] < match["support"]
    assert 0.0 <= match["probability_prior"] <= 1.0


def test_five_wave_impulse_bullish_respects_elliott_rules():
    df = _pattern_df(
        [
            (8, "low", 100.0),
            (14, "high", 110.0),
            (20, "low", 105.0),
            (28, "high", 128.0),
            (34, "low", 115.0),
            (42, "high", 135.0),
        ]
    )
    # Break out above the wave-5 high.  Keep bars 43-44 below H5 so idx42
    # remains a swing high, then break out on bar 45.
    df.loc[43:44, "close"] = 134.0
    df.loc[43:44, "high"] = 134.5
    df.loc[43:44, "low"] = 133.5
    df.loc[45:, "close"] = 138.0
    df.loc[45:, "high"] = 139.0
    df.loc[45:, "low"] = 137.0
    df.loc[42, "close"] = 135.0
    matches = match_templates(df, min_confidence=0.3)
    bullish = [m for m in matches if m["template_name"] == "five_wave_impulse_bullish"]
    assert len(bullish) >= 1
    match = bullish[-1]
    # Wave 4 must not overlap wave 1: L4 > H1.
    assert match["support"] > 110.0


def test_head_and_shoulders_top_is_detected():
    df = _pattern_df(
        [
            (10, "high", 120.0),
            (18, "low", 110.0),
            (26, "high", 130.0),
            (34, "low", 110.0),
            (42, "high", 120.0),
        ]
    )
    # Push the close below the neckline to trigger the breakout.
    df.loc[43:, "close"] = 108.0
    df.loc[43:, "high"] = 109.0
    df.loc[43:, "low"] = 107.0
    df.loc[42, "close"] = 112.0

    matches = match_templates(df, min_confidence=0.3)
    tops = [m for m in matches if m["template_name"] == "head_and_shoulders_top"]
    assert len(tops) >= 1
    match = tops[-1]
    assert match["direction"] == "bearish"
    assert match["target"] < match["support"] < match["resistance"]


def test_double_bottom_bullish_is_detected():
    df = _pattern_df(
        [
            (10, "low", 100.0),
            (18, "high", 110.0),
            (26, "low", 100.0),
            (34, "high", 115.0),
        ]
    )
    # Break out above the neckline.
    df.loc[35:, "close"] = 116.0
    df.loc[35:, "high"] = 117.0
    df.loc[35:, "low"] = 115.0
    df.loc[34, "close"] = 114.0

    matches = match_templates(df, min_confidence=0.3)
    bottoms = [m for m in matches if m["template_name"] == "double_bottom_bullish"]
    assert len(bottoms) >= 1
    match = bottoms[-1]
    assert match["direction"] == "bullish"
    assert match["support"] < match["resistance"] < match["target"]


def test_min_confidence_filter_works():
    df = _pattern_df(
        [
            (10, "low", 100.0),
            (18, "high", 110.0),
            (24, "low", 104.0),
            (32, "high", 125.0),
        ]
    )
    df.loc[33:, "close"] = 126.0
    df.loc[33:, "high"] = 127.0
    df.loc[33:, "low"] = 125.0
    df.loc[32, "close"] = 125.0
    low_conf = match_templates(df, min_confidence=0.3)
    high_conf = match_templates(df, min_confidence=0.99)
    assert len(high_conf) <= len(low_conf)


def test_match_result_has_required_fields():
    df = _pattern_df(
        [
            (10, "low", 100.0),
            (18, "high", 110.0),
            (24, "low", 104.0),
            (32, "high", 125.0),
        ]
    )
    df.loc[33:, "close"] = 126.0
    df.loc[33:, "high"] = 127.0
    df.loc[33:, "low"] = 125.0
    df.loc[32, "close"] = 125.0
    matches = match_templates(df, min_confidence=0.3)
    assert matches
    match = matches[0]
    for field in (
        "template_name",
        "matched_index",
        "direction",
        "confidence",
        "support",
        "resistance",
        "target",
        "stop_loss",
        "suggestion",
        "probability_prior",
    ):
        assert field in match
