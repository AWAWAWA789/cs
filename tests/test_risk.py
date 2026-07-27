"""Tests for risk management helpers."""

import pytest

from src.strategy.risk import position_size, stop_loss, take_profit_levels


def test_stop_loss_below_swing_low():
    sl = stop_loss(entry_price=150.0, swing_low=100.0)

    assert sl < 100.0
    assert sl <= 150.0


def test_stop_loss_does_not_exceed_entry():
    sl = stop_loss(entry_price=100.0, swing_low=150.0)

    assert sl == pytest.approx(100.0)


def test_take_profit_levels():
    tps = take_profit_levels(swing_low=100.0, swing_high=150.0)

    assert "1.272" in tps
    assert "1.618" in tps
    assert tps["1.272"] > 150.0
    assert tps["1.618"] > tps["1.272"]


def test_position_size():
    size = position_size(
        capital=10000.0,
        risk_fraction=0.02,
        entry_price=150.0,
        stop_loss_price=100.0,
    )

    assert size == pytest.approx(4.0)


def test_position_size_zero_when_stop_above_entry():
    size = position_size(
        capital=10000.0,
        risk_fraction=0.02,
        entry_price=100.0,
        stop_loss_price=150.0,
    )

    assert size == 0.0
