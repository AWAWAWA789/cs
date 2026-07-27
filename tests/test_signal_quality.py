"""Tests for signal-quality filters."""

from __future__ import annotations

import pandas as pd

from src.features.signal_quality import (
    add_signal_quality_features,
    structure_resonance,
)
from src.strategy.signal import SignalParams, generate_signals


def test_structure_resonance_near_anchor():
    df = pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0],
            "signal_swing_low": [100.0, 100.0, 100.0],
        }
    )
    result = structure_resonance(df, buffer=0.05)
    assert result.all()


def test_structure_resonance_far_from_anchor():
    df = pd.DataFrame(
        {
            "close": [120.0, 130.0],
            "signal_swing_low": [100.0, 100.0],
        }
    )
    result = structure_resonance(df, buffer=0.05)
    assert not result.any()


def _make_liquidity_grab_near_swing_low():
    """Uptrend with a liquidity grab that ends far from the recent swing low.

    The last bar sweeps below the most recent swing low but closes well above
    it.  Without structure-resonance filtering this produces a Smart Money long
    signal; with resonance filtering the signal is removed because the close is
    too far from the anchor swing low.
    """
    return pd.DataFrame(
        {
            "open": [1.5, 3.0, 1.5, 4.0, 2.5, 5.0, 3.0, 6.0, 3.0],
            "high": [3.0, 4.0, 2.0, 5.0, 3.0, 6.0, 4.0, 7.0, 4.5],
            "low": [2.0, 2.5, 1.0, 3.0, 2.0, 4.0, 3.0, 5.0, 2.9],
            "close": [1.5, 3.5, 1.5, 4.5, 2.5, 5.5, 3.5, 6.5, 4.0],
        }
    )


def test_resonance_filter_removes_far_smart_money_signal():
    df = _make_liquidity_grab_near_swing_low()

    unfiltered = SignalParams(
        swing_order=1,
        fib_tolerance=0.5,
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.01,
        require_structure_resonance=False,
    )
    filtered = SignalParams(
        swing_order=1,
        fib_tolerance=0.5,
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.01,
        require_structure_resonance=True,
        structure_resonance_buffer=0.05,
    )

    base_df = generate_signals(df, unfiltered)
    filt_df = generate_signals(df, filtered)
    assert base_df["signal_long"].iloc[-1]
    assert not filt_df["signal_long"].iloc[-1]


def test_signal_quality_score_added_when_enabled():
    df = _make_liquidity_grab_near_swing_low()
    params = SignalParams(
        swing_order=1,
        fib_tolerance=0.5,
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.01,
        use_signal_quality=True,
    )
    result = generate_signals(df, params)
    assert "signal_quality" in result.columns
    # Non-signal bars receive a quality of 0.
    assert (result.loc[~result["signal_long"], "signal_quality"] == 0.0).all()
    # Signal bars receive a positive quality score.
    signal_scores = result.loc[result["signal_long"], "signal_quality"]
    assert (signal_scores > 0.0).all()


def test_min_signal_quality_filters_marginal_signals():
    df = _make_liquidity_grab_near_swing_low()
    low_threshold = SignalParams(
        swing_order=1,
        fib_tolerance=0.5,
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.01,
        use_signal_quality=True,
        min_signal_quality=0.0,
    )
    high_threshold = SignalParams(
        swing_order=1,
        fib_tolerance=0.5,
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.01,
        use_signal_quality=True,
        min_signal_quality=1.0,
    )
    low_df = generate_signals(df, low_threshold)
    high_df = generate_signals(df, high_threshold)
    assert low_df["signal_long"].sum() >= high_df["signal_long"].sum()


def test_add_signal_quality_features_scores_signal_bars_only():
    df = pd.DataFrame(
        {
            "open": [1.0, 1.82, 1.5, 2.5],
            "high": [1.2, 2.0, 1.8, 2.8],
            "low": [0.8, 1.78, 1.4, 2.2],
            "close": [1.0, 1.81, 1.5, 2.5],
            "signal_long": [False, True, False, False],
            "signal_swing_low": [None, 1.8, None, None],
        }
    )
    result = add_signal_quality_features(df)
    assert result["signal_quality"].iloc[0] == 0.0
    assert result["signal_quality"].iloc[2] == 0.0
    assert result["signal_quality"].iloc[3] == 0.0
    assert result["signal_quality"].iloc[1] > 0.0
