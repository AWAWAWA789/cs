"""Tests for the dual-strategy ensemble."""

from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.ensemble import EnsembleParams, generate_ensemble_signals
from src.strategy.signal import SignalParams
from src.strategy.trend_following_strategy import TrendFollowingParams


def _make_uptrend_with_pullback() -> pd.DataFrame:
    """Uptrend ending with a fib pullback and bullish pin bar."""
    return pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 2.5, 2.0, 2.5, 2.4, 2.54],
            "high": [1.2, 2.2, 1.8, 2.8, 2.3, 2.95, 2.6, 2.55],
            "low": [0.8, 1.8, 1.4, 2.2, 1.9, 2.7, 2.25, 2.3],
            "close": [1.0, 2.0, 1.5, 2.5, 2.0, 2.9, 2.5, 2.55],
        }
    )


def _make_uptrend_with_breakout() -> pd.DataFrame:
    """Uptrend ending with a bullish breakout above recent swing highs."""
    return pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.5, 5.0, 4.5, 6.0],
            "high": [2.0, 2.5, 2.0, 3.5, 3.0, 4.5, 4.0, 5.5, 5.0, 6.5],
            "low": [0.5, 1.5, 1.0, 2.5, 2.0, 3.5, 3.0, 4.5, 4.0, 5.5],
            "close": [2.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.5, 5.0, 4.5, 6.2],
        }
    )


def _make_long_uptrend_with_breakout() -> pd.DataFrame:
    """Long uptrend with order-2 swing points and a late breakout.

    The breakout fires two bars before the end so the backtest engine has room
    to open a position.
    """
    n = 40
    lows = []
    highs = []
    for i in range(n):
        base = i * 0.5
        if i % 4 == 2:
            lows.append(base - 1.5)
        else:
            lows.append(base)
        if i % 4 == 0:
            highs.append(base + 1 + 1.5)
        else:
            highs.append(base + 1)

    opens = [low + (high - low) * 0.25 for low, high in zip(lows, highs)]
    closes = [low + (high - low) * 0.75 for low, high in zip(lows, highs)]

    # Breakout bar
    lows[38] = 19.0
    highs[38] = 22.0
    opens[38] = 19.5
    closes[38] = 21.0
    lows[39] = 19.5
    highs[39] = 22.0
    opens[39] = 20.5
    closes[39] = 21.0

    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}
    )


def test_union_mode_captures_pullback_signal():
    df = _make_uptrend_with_pullback()
    params = EnsembleParams(
        pullback_params=SignalParams(swing_order=1, fib_tolerance=0.05),
        mode="union",
    )
    result = generate_ensemble_signals(df, params)
    assert result["signal_long"].iloc[-1]
    assert "ensemble_pullback" in result["signal_reason"].iloc[-1]


def test_union_mode_captures_trend_following_signal():
    df = _make_uptrend_with_breakout()
    params = EnsembleParams(
        trend_params=TrendFollowingParams(
            swing_order=1,
            confirmations=1,
            trend_strength_threshold=None,
        ),
        mode="union",
    )
    result = generate_ensemble_signals(df, params)
    assert result["signal_long"].iloc[-1]
    assert "ensemble_trend" in result["signal_reason"].iloc[-1]


def test_regime_switch_prefers_trend_in_strong_uptrend():
    df = _make_long_uptrend_with_breakout()
    params = EnsembleParams(
        trend_params=TrendFollowingParams(
            swing_order=1,
            confirmations=1,
            trend_strength_threshold=None,
        ),
        pullback_params=SignalParams(swing_order=1, confirmations=1),
        mode="regime_switch",
        adx_threshold=0.0,
        regime_confirmations=1,
    )
    result = generate_ensemble_signals(df, params)
    assert result["signal_long"].iloc[38]
    assert "ensemble_trend" in result["signal_reason"].iloc[38]


def test_regime_switch_fallback_to_pullback_when_adx_low():
    df = _make_uptrend_with_pullback()
    params = EnsembleParams(
        pullback_params=SignalParams(
            swing_order=1,
            fib_tolerance=0.05,
            use_smart_money=False,
        ),
        mode="regime_switch",
        adx_threshold=100.0,
    )
    result = generate_ensemble_signals(df, params)
    assert result["signal_long"].iloc[-1]
    assert "ensemble_pullback" in result["signal_reason"].iloc[-1]


def test_backtest_integration():
    df = _make_long_uptrend_with_breakout()
    params = EnsembleParams(
        trend_params=TrendFollowingParams(
            swing_order=1,
            confirmations=1,
            trend_strength_threshold=None,
        ),
        pullback_params=SignalParams(swing_order=1, confirmations=1),
        mode="regime_switch",
        adx_threshold=0.0,
        regime_confirmations=1,
    )
    signal_df = generate_ensemble_signals(df, params)
    result = run_backtest(signal_df, BacktestParams())
    assert len(result.trades) > 0


def test_dynamic_weight_mode_prefers_trend_in_strong_uptrend():
    df = _make_long_uptrend_with_breakout()
    params = EnsembleParams(
        trend_params=TrendFollowingParams(
            swing_order=1,
            confirmations=1,
            trend_strength_threshold=None,
        ),
        pullback_params=SignalParams(swing_order=1, confirmations=1),
        mode="dynamic_weight",
        dynamic_weight_adx_scale=1.0,
        dynamic_weight_min=0.2,
        dynamic_weight_max=0.8,
        regime_confirmations=1,
    )
    result = generate_ensemble_signals(df, params)
    assert "ensemble_trend_weight" in result.columns
    assert result["signal_long"].iloc[38]
    assert "ensemble_trend" in result["signal_reason"].iloc[38]


def test_dynamic_weight_mode_prefers_pullback_in_weak_trend():
    df = _make_uptrend_with_pullback()
    params = EnsembleParams(
        trend_params=TrendFollowingParams(
            swing_order=1,
            confirmations=1,
            trend_strength_threshold=None,
        ),
        pullback_params=SignalParams(swing_order=1, fib_tolerance=0.05),
        mode="dynamic_weight",
        dynamic_weight_adx_scale=100.0,
        dynamic_weight_min=0.2,
        dynamic_weight_max=0.8,
        regime_confirmations=1,
    )
    result = generate_ensemble_signals(df, params)
    assert result["signal_long"].iloc[-1]
    assert "ensemble_pullback" in result["signal_reason"].iloc[-1]


def test_signal_quality_filter_in_ensemble():
    df = _make_uptrend_with_pullback()
    params = EnsembleParams(
        pullback_params=SignalParams(
            swing_order=1,
            fib_tolerance=0.05,
            use_signal_quality=True,
        ),
        mode="union",
        use_signal_quality=True,
        min_signal_quality=0.0,
    )
    result = generate_ensemble_signals(df, params)
    assert "signal_quality" in result.columns
    assert result["signal_long"].iloc[-1]
