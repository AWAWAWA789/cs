"""Tests for adaptive temperature calibration."""

from __future__ import annotations

import numpy as np
import pytest

from src.scenario_engine.adaptive_calibration import (
    find_best_temperature,
    load_temperature,
    save_temperature,
)


def test_find_best_temperature_reduces_brier():
    """过度自信预测应通过升高温度降低 Brier 分数。"""
    rng = np.random.default_rng(42)
    probabilities = [0.9] * 40 + [0.1] * 40
    outcomes = [1] * 20 + [0] * 20 + [1] * 20 + [0] * 20
    best_temp = find_best_temperature(
        probabilities, outcomes, temperatures=[0.5, 1.0, 2.0, 5.0]
    )
    assert best_temp > 1.0


def test_find_best_temperature_returns_default_when_empty():
    assert find_best_temperature([], []) == 1.0


def test_save_and_load_temperature(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.scenario_engine.adaptive_calibration.DEFAULT_CALIBRATION_DIR", tmp_path
    )
    save_temperature("手套", 1.5)
    loaded = load_temperature("手套")
    assert loaded == pytest.approx(1.5, abs=1e-9)


def test_load_temperature_returns_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.scenario_engine.adaptive_calibration.DEFAULT_CALIBRATION_DIR", tmp_path
    )
    assert load_temperature("不存在的指数") == 1.0
