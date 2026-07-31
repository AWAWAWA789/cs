"""Tests for the /ensemble/run endpoint."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    dates = pd.date_range("2024-01-01", periods=400, freq="D")
    rng = np.random.default_rng(42)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 400)))
    df = pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + rng.normal(0, 0.005, 400)),
        "high": close * (1 + np.abs(rng.normal(0, 0.01, 400))),
        "low": close * (1 - np.abs(rng.normal(0, 0.01, 400))),
        "close": close,
    })
    from src.api import ensemble_endpoints
    monkeypatch.setattr(ensemble_endpoints, "_load_ohlc", lambda sub_index, period: df)
    from run_scenario_server import app
    return TestClient(app)


def test_ensemble_returns_three_strategies(client):
    """/ensemble/run should return ensemble, pullback, and trend_following results."""
    r = client.get("/ensemble/run", params={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()

    assert data["sub_index"] == "手套"
    assert data["period"] == "1day"

    for key in ("ensemble", "pullback", "trend_following"):
        assert key in data
        strat = data[key]
        assert "strategy_name" in strat
        assert "metrics" in strat
        assert "equity_curve" in strat
        assert isinstance(strat["equity_curve"], list)
        assert "trade_count" in strat
        assert "total_return" in strat["metrics"]


def test_ensemble_invalid_period_returns_400(client):
    r = client.get("/ensemble/run", params={"sub_index": "手套", "period": "10year"})
    assert r.status_code == 400
