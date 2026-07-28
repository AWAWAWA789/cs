"""Tests for CalibrationStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.scenario_engine.calibration_store import CalibrationStore


def test_record_and_lookup(tmp_path: Path) -> None:
    store = CalibrationStore(base_dir=tmp_path)
    store.record_prediction(
        sub_index="手套",
        period="1day",
        timestamp="2026-07-28T00:00:00+00:00",
        scenario_key="bullish_continuation",
        probability=0.7,
    )
    store.record_outcome(
        sub_index="手套",
        period="1day",
        timestamp="2026-07-28T00:00:00+00:00",
        scenario_key="bullish_continuation",
        future_return_5=0.03,
        future_return_7=0.05,
    )
    rows = store.load_records("手套", "1day")
    assert len(rows) == 1
    assert rows[0]["future_return_5"] == pytest.approx(0.03, abs=1e-9)
    assert rows[0]["probability"] == pytest.approx(0.7, abs=1e-9)


def test_unmatched_predictions_remain(tmp_path: Path) -> None:
    store = CalibrationStore(base_dir=tmp_path)
    store.record_prediction(
        sub_index="手套",
        period="1day",
        timestamp="2026-07-29T00:00:00+00:00",
        scenario_key="dip_then_rise",
        probability=0.5,
    )
    rows = store.load_records("手套", "1day")
    assert len(rows) == 1
    assert rows[0].get("future_return_5") is None


def test_multiple_predictions_same_period(tmp_path: Path) -> None:
    store = CalibrationStore(base_dir=tmp_path)
    store.record_prediction(
        sub_index="手套",
        period="1day",
        timestamp="2026-07-28T00:00:00+00:00",
        scenario_key="bullish_continuation",
        probability=0.7,
    )
    store.record_prediction(
        sub_index="手套",
        period="1day",
        timestamp="2026-07-29T00:00:00+00:00",
        scenario_key="bearish_reversal",
        probability=0.3,
    )
    rows = store.load_records("手套", "1day")
    assert len(rows) == 2
