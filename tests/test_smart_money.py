"""Tests for Smart Money price-action features."""

import pandas as pd

from src.features.smart_money import (
    add_smart_money_features,
    fair_value_gap,
    liquidity_grab,
    order_block,
)


def _df_from_records(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def test_liquidity_grab_detects_sweep_and_recovery():
    df = _df_from_records(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "swing_low": True},
            {"open": 100, "high": 101, "low": 98, "close": 100.5, "swing_low": False},
        ]
    )
    signal = liquidity_grab(df)
    assert signal.tolist() == [False, True]


def test_liquidity_grab_requires_recovery():
    df = _df_from_records(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "swing_low": True},
            {"open": 100, "high": 101, "low": 98, "close": 99, "swing_low": False},
        ]
    )
    signal = liquidity_grab(df)
    assert signal.tolist() == [False, False]


def test_order_block_revisit():
    df = _df_from_records(
        [
            {"open": 102, "high": 103, "low": 101, "close": 101, "swing_low": False},
            {"open": 100, "high": 101, "low": 99, "close": 100, "swing_low": True},
            {"open": 101.5, "high": 102, "low": 101, "close": 101.5, "swing_low": False},
        ]
    )
    signal = order_block(df)
    assert signal.tolist() == [False, False, True]


def test_fair_value_gap_revisit():
    df = _df_from_records(
        [
            {"open": 100, "high": 101, "low": 100, "close": 100.5},
            {"open": 102, "high": 103, "low": 102, "close": 102.5},
            {"open": 104, "high": 105, "low": 104, "close": 104.5},
            {"open": 102, "high": 102.5, "low": 101.5, "close": 101.6},
        ]
    )
    signal = fair_value_gap(df)
    assert signal.tolist() == [False, False, False, True]


def test_add_smart_money_features_columns():
    df = _df_from_records(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "swing_low": True},
            {"open": 100, "high": 101, "low": 98, "close": 100.5, "swing_low": False},
        ]
    )
    result = add_smart_money_features(df)
    assert "liquidity_grab" in result.columns
    assert "order_block" in result.columns
    assert "fair_value_gap" in result.columns
