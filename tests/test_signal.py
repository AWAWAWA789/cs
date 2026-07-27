"""Tests for signal generation."""

import pandas as pd

from src.strategy.signal import SignalParams, generate_signals


def _make_uptrend_with_pullback():
    """Create a DataFrame that ends with an uptrend, fib pullback and bullish pin bar."""
    return pd.DataFrame(
        {
            # Uptrend: swing highs at 2.2, 2.8, 2.95; swing lows at 1.4, 1.9, 2.25.
            "open": [1.0, 2.0, 1.5, 2.5, 2.0, 2.5, 2.4, 2.54],
            "high": [1.2, 2.2, 1.8, 2.8, 2.3, 2.95, 2.6, 2.55],
            "low": [0.8, 1.8, 1.4, 2.2, 1.9, 2.7, 2.25, 2.3],
            "close": [1.0, 2.0, 1.5, 2.5, 2.0, 2.9, 2.5, 2.55],
        }
    )


def test_generate_long_signal():
    df = _make_uptrend_with_pullback()
    params = SignalParams(swing_order=1, fib_tolerance=0.05)
    result = generate_signals(df, params)

    assert result["signal_long"].iloc[-1] == True
    assert "fib" in result["signal_reason"].iloc[-1]
    assert "pin_bar" in result["signal_reason"].iloc[-1] or "engulfing" in result["signal_reason"].iloc[-1]


def test_no_signal_without_uptrend():
    df = pd.DataFrame(
        {
            "open": [5.0, 4.0, 4.5, 3.5, 4.0, 3.0],
            "high": [5.2, 4.2, 4.8, 3.8, 4.3, 3.2],
            "low": [4.8, 3.8, 4.2, 3.2, 3.7, 2.8],
            "close": [5.0, 4.0, 4.5, 3.5, 4.0, 3.0],
        }
    )
    params = SignalParams(swing_order=1, fib_tolerance=0.5)
    result = generate_signals(df, params)

    assert not result["signal_long"].any()


def test_no_signal_without_pattern():
    df = _make_uptrend_with_pullback()
    # Remove the pin bar / engulfing on the last bar by making it a doji.
    df.iloc[-1] = [2.55, 2.65, 2.45, 2.55]
    params = SignalParams(swing_order=1, fib_tolerance=0.05)
    result = generate_signals(df, params)

    assert not result["signal_long"].iloc[-1]
