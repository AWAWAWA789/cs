"""Tests for Swing High / Swing Low detection."""

import pandas as pd

from src.features.swing import identify_swing_points, swing_highs, swing_lows


def _make_df(highs, lows):
    return pd.DataFrame({"high": highs, "low": lows})


def test_identify_swing_high_basic():
    # order=2 requires 2 lower bars on each side.
    highs = [1, 2, 3, 4, 5, 4, 3, 2, 1]
    lows = highs  # lows not relevant for this assertion
    df = identify_swing_points(_make_df(highs, lows), order=2)

    assert df["swing_high"].tolist() == [False, False, False, False, True, False, False, False, False]


def test_identify_swing_low_basic():
    lows = [5, 4, 3, 2, 1, 2, 3, 4, 5]
    highs = lows
    df = identify_swing_points(_make_df(highs, lows), order=2)

    assert df["swing_low"].tolist() == [False, False, False, False, True, False, False, False, False]


def test_equal_neighbour_is_not_swing():
    # A flat top should not be considered a strict swing high.
    highs = [1, 2, 3, 3, 3, 2, 1]
    lows = highs
    df = identify_swing_points(_make_df(highs, lows), order=2)

    assert not df["swing_high"].any()


def test_swing_highs_filter():
    df = identify_swing_points(_make_df([1, 2, 3, 2, 1], [1, 2, 3, 2, 1]), order=1)
    highs = swing_highs(df)

    assert len(highs) == 1
    assert highs.index[0] == 2


def test_swing_lows_filter():
    df = identify_swing_points(_make_df([5, 4, 3, 4, 5], [5, 4, 3, 4, 5]), order=1)
    lows = swing_lows(df)

    assert len(lows) == 1
    assert lows.index[0] == 2
