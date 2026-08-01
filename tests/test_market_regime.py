"""Tests for market-regime classification."""

from __future__ import annotations

import pandas as pd

from src.features.market_regime import classify_market_regime


def test_regime_uptrend_for_higher_highs_and_lows():
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.5, 5.0],
            "high": [1.5, 2.5, 2.0, 3.5, 3.0, 4.5, 4.0, 5.5],
            "low": [0.5, 1.5, 1.0, 2.5, 2.0, 3.5, 3.0, 4.5],
            "close": [1.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.5, 5.0],
        }
    )
    regime = classify_market_regime(df, swing_order=1, confirmations=2)
    # After enough swing points are observed the regime should be uptrend.
    assert regime.dropna().iloc[-1] == "uptrend"


def test_regime_downtrend_for_lower_highs_and_lows():
    df = pd.DataFrame(
        {
            "open": [5.0, 4.0, 4.5, 3.5, 4.0, 3.0, 3.5, 2.5],
            "high": [5.5, 4.5, 5.0, 4.0, 4.5, 3.5, 4.0, 3.0],
            "low": [4.5, 3.5, 4.0, 3.0, 3.5, 2.5, 3.0, 2.0],
            "close": [5.0, 4.0, 4.5, 3.5, 4.0, 3.0, 3.5, 2.5],
        }
    )
    regime = classify_market_regime(df, swing_order=1, confirmations=2)
    assert regime.dropna().iloc[-1] == "downtrend"


def test_regime_filter_reduces_signals():
    from src.strategy.signal import SignalParams, generate_signals

    # A short-term uptrend with a liquidity grab on the last bar.  The local
    # trend is up so a Smart Money signal fires, but the long-term regime
    # (slower swing/confirmation) is still unclear, so the filter removes it.
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.5, 5.0, 4.0],
            "high": [2.0, 3.0, 2.5, 4.0, 3.5, 5.0, 4.5, 6.0, 4.5],
            "low": [0.5, 1.5, 1.0, 2.5, 2.0, 3.0, 3.0, 4.0, 2.9],
            "close": [1.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.5, 5.0, 4.5],
        }
    )
    params_unfiltered = SignalParams(
        swing_order=1,
        fib_tolerance=0.5,
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.01,
        use_trend_following=False,
    )
    params_filtered = SignalParams(
        swing_order=1,
        fib_tolerance=0.5,
        confirmations=1,
        use_smart_money=True,
        liquidity_grab_buffer=0.01,
        use_trend_following=False,
        use_market_regime_filter=True,
        market_regime_confirmations=5,
    )

    unfiltered = generate_signals(df, params_unfiltered)
    filtered = generate_signals(df, params_filtered)
    assert unfiltered["signal_long"].sum() > 0
    assert filtered["signal_long"].sum() < unfiltered["signal_long"].sum()
