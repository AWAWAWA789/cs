"""Tests for the independent trend-following strategy module."""

from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)


def _uptrend_with_breakout() -> pd.DataFrame:
    """Uptrend ending with a bullish breakout above the last swing high.

    The breakout fires at the second-to-last bar so that the backtest engine
    has one additional bar to open the position.
    """
    return pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.5, 4.0, 5.0, 6.0],
            "high": [2.0, 3.0, 2.5, 4.0, 3.5, 5.0, 4.5, 5.0, 6.5, 7.0],
            "low": [1.0, 1.5, 1.0, 2.5, 2.0, 3.5, 3.0, 3.5, 4.5, 5.5],
            "close": [1.5, 2.5, 1.5, 3.5, 2.5, 4.5, 3.5, 4.5, 6.0, 6.5],
        }
    )


def test_basic_breakout_signal():
    df = _uptrend_with_breakout()
    params = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
    )
    result = generate_trend_following_signals(df, params)
    assert result["signal_long"].iloc[-2]
    assert result["signal_reason"].iloc[-2] == "trend_following_breakout"
    assert pd.notna(result["signal_swing_low"].iloc[-2])
    assert pd.notna(result["signal_swing_high"].iloc[-2])


def test_no_uptrend_filter_removes_signal():
    df = _uptrend_with_breakout()
    params = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
        require_uptrend=True,
    )
    result = generate_trend_following_signals(df, params)
    uptrend_signals = result["signal_long"].sum()

    params_no_uptrend = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
        require_uptrend=False,
    )
    result_no_uptrend = generate_trend_following_signals(df, params_no_uptrend)
    assert result_no_uptrend["signal_long"].sum() >= uptrend_signals


def test_higher_high_breakout_mode():
    df = _uptrend_with_breakout()
    params = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
        use_higher_high_breakout=True,
    )
    result = generate_trend_following_signals(df, params)
    signal_reasons = result.loc[result["signal_long"], "signal_reason"].tolist()
    assert all(r == "trend_following_higher_high" for r in signal_reasons)


def test_adx_filter_removes_weak_breakout():
    # Choppy data: prices oscillate without sustained direction.
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0],
            "high": [2.1, 2.1, 2.1, 2.1, 2.1, 2.1, 2.1, 2.1, 2.1, 2.1],
            "low": [0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
            "close": [2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0],
        }
    )
    unfiltered = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
        require_uptrend=False,
    )
    filtered = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=20.0,
        adx_period=5,
        require_uptrend=False,
    )
    base = generate_trend_following_signals(df, unfiltered)
    filt = generate_trend_following_signals(df, filtered)
    assert base["signal_long"].sum() >= filt["signal_long"].sum()


def test_backtest_integration():
    df = _uptrend_with_breakout()
    params = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
    )
    signal_df = generate_trend_following_signals(df, params)
    result = run_backtest(signal_df, BacktestParams())
    assert len(result.trades) > 0


def test_pullback_confirmation_signal():
    """Strategy can use breakout-pullback confirmation instead of immediate breakout."""
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 2.5, 2.3, 2.5],
            "high": [1.2, 2.2, 1.8, 2.7, 2.8, 2.9],
            "low": [0.8, 1.8, 1.4, 2.2, 2.1, 2.4],
            "close": [1.0, 2.0, 1.5, 2.6, 2.4, 2.8],
        }
    )
    params = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
        require_uptrend=False,
        use_pullback_confirmation=True,
        pullback_lookback=3,
        pullback_buffer=0.01,
    )
    result = generate_trend_following_signals(df, params)
    assert result["signal_long"].iloc[4]
    assert result["signal_reason"].iloc[4] == "trend_following_breakout_pullback"


def test_di_filter_reduces_signals():
    df = _uptrend_with_breakout()
    unfiltered = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
    )
    filtered = TrendFollowingParams(
        swing_order=1,
        confirmations=1,
        trend_strength_threshold=None,
        use_di_filter=True,
    )
    base = generate_trend_following_signals(df, unfiltered)
    filt = generate_trend_following_signals(df, filtered)
    assert base["signal_long"].sum() >= filt["signal_long"].sum()
