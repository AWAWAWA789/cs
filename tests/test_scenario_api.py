"""Tests for the Phase 13 scenario API endpoints."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.scenario_endpoints import router as scenario_router


def _make_ohlc(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(13)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )


@pytest.fixture
def app(monkeypatch):
    """Build a FastAPI app with the scenario router and patched data loader."""
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    monkeypatch.setenv("CSQAQ_CACHE_PATH", "/tmp/csqaq_test_cache")

    # Always use deterministic synthetic data so tests never hit the network.
    import src.api.scenario_endpoints as endpoints

    monkeypatch.setattr(
        endpoints,
        "_load_ohlc",
        lambda sub_index, period, **kwargs: (_make_ohlc(), "real"),
    )

    fast_app = FastAPI()
    fast_app.include_router(scenario_router)
    return fast_app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_generate_returns_scenarios(client):
    response = client.get("/scenario/generate", params={"sub_index": "手套", "period": "1day"})
    assert response.status_code == 200
    data = response.json()
    assert data["sub_index"] == "手套"
    assert data["period"] == "1day"
    assert "scenarios" in data
    assert 2 <= len(data["scenarios"]) <= 4
    assert data["cached"] is False
    assert "generation_time_ms" in data


def test_generate_cache_hit(client):
    client.get("/scenario/generate", params={"sub_index": "手套", "period": "1day"})
    response = client.get("/scenario/generate", params={"sub_index": "手套", "period": "1day"})
    assert response.status_code == 200
    assert response.json()["cached"] is True


def test_generate_refresh_clears_cache(client):
    client.get("/scenario/generate", params={"sub_index": "手套", "period": "1day"})
    response = client.get(
        "/scenario/generate",
        params={"sub_index": "手套", "period": "1day", "refresh": "true"},
    )
    assert response.status_code == 200
    assert response.json()["cached"] is False


def test_generate_probability_sum_is_one(client):
    response = client.get("/scenario/generate", params={"sub_index": "手套", "period": "1day"})
    scenarios = response.json()["scenarios"]
    total = sum(s["probability"] for s in scenarios)
    assert abs(total - 1.0) < 0.01


def test_history_returns_matches(client):
    response = client.get("/scenario/history", params={"sub_index": "手套", "period": "1day"})
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "knn"
    assert isinstance(data["matches"], list)


def test_templates_returns_matches(client):
    response = client.get("/scenario/templates", params={"sub_index": "手套", "period": "1day"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["matches"], list)


def test_ohlc_returns_data(client):
    response = client.get("/scenario/ohlc", params={"sub_index": "手套", "period": "1day"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert "ohlc" in data
    sample = data["ohlc"][0]
    assert set(sample.keys()) >= {"timestamp", "open", "high", "low", "close"}


def test_explain_returns_constrained_prompt(client):
    scenario = {
        "name": "上涨延续",
        "direction_label": "bullish",
        "probability": 0.45,
        "support": 120.0,
        "resistance": 135.0,
        "target": 140.0,
        "stop_loss": 118.0,
        "position_size": 0.02,
        "wave_sketch": [{"label": "current", "price": 128.0}],
    }
    response = client.post(
        "/scenario/explain",
        json={"scenario": scenario, "context": {"sub_index": "手套", "period": "1day"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert "prompt" in data
    assert "explanation" in data
    assert "wave_sketch_description" in data
    assert "仅解释" in data["prompt"]
    assert "不得重新判断" in data["prompt"]
    assert "上涨延续" in data["explanation"]


def test_meta_returns_supported_periods(client):
    response = client.get("/scenario/meta")
    assert response.status_code == 200
    data = response.json()
    assert "1day" in data["supported_periods"]
    assert data["default_period"] == "1day"


def test_invalid_period_returns_400(client):
    response = client.get("/scenario/generate", params={"sub_index": "手套", "period": "10year"})
    assert response.status_code == 400


def test_history_dtw_method(client):
    response = client.get(
        "/scenario/history",
        params={"sub_index": "手套", "period": "1day", "method": "dtw", "n_neighbors": 5},
    )
    assert response.status_code == 200
    assert response.json()["method"] == "dtw"


def test_history_respects_n_neighbors(client):
    response = client.get(
        "/scenario/history",
        params={"sub_index": "手套", "period": "1day", "method": "knn", "n_neighbors": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["matches"]) <= 3


def test_templates_respects_min_confidence(client):
    response = client.get(
        "/scenario/templates",
        params={"sub_index": "手套", "period": "1day", "min_confidence": 0.95},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(m["confidence"] >= 0.95 for m in data["matches"])


def test_monitoring_records_requests(client):
    from src.api.monitoring import COLLECTOR

    before = COLLECTOR.metrics()["request_count"]
    client.get("/scenario/meta")
    after = COLLECTOR.metrics()["request_count"]
    assert after > before
