"""Tests for multi-timeframe alignment helpers."""

import pandas as pd

from src.features.multi_timeframe import add_higher_trend, align_higher_trend


def test_align_higher_trend_maps_forward():
    lower = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-01 00:00", "2024-01-01 04:00", "2024-01-02 00:00"]
            ).tz_localize("UTC"),
        }
    )
    higher = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]).tz_localize(
                "UTC"
            ),
            "trend": [1, -1],
        }
    )

    trend = align_higher_trend(lower, higher)
    assert trend.tolist() == [1, 1, -1]


def test_add_higher_trend_computes_trend_when_missing():
    lower = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01 00:00",
                    "2024-01-02 00:00",
                    "2024-01-03 00:00",
                    "2024-01-04 00:00",
                    "2024-01-05 00:00",
                    "2024-01-06 00:00",
                ]
            ).tz_localize("UTC"),
            "open": [1, 2, 3, 4, 5, 6],
            "high": [1, 2, 3, 4, 5, 6],
            "low": [1, 2, 3, 4, 5, 6],
            "close": [1, 2, 3, 4, 5, 6],
        }
    )
    # Six higher bars forming higher highs and higher lows with swing_order=1.
    higher = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-05",
                    "2024-01-06",
                ]
            ).tz_localize("UTC"),
            "open": [2.5, 1.5, 3.0, 2.0, 4.0, 3.5],
            "high": [3.0, 2.0, 4.0, 3.0, 5.0, 4.0],
            "low": [2.0, 1.0, 2.5, 1.5, 3.0, 2.5],
            "close": [2.5, 1.5, 3.0, 2.0, 4.0, 3.5],
        }
    )

    result = add_higher_trend(lower, higher, swing_order=1, confirmations=1)
    assert "higher_trend" in result.columns
    # Uptrend is confirmed once two swing highs and two swing lows are observed.
    assert result["higher_trend"].tolist() == [0, 0, 0, 0, 1, 1]
