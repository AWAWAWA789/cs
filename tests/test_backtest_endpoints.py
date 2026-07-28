"""Tests for the backtest equity endpoint."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.backtest_endpoints import router as backtest_router
from src.api.scenario_endpoints import _load_ohlc


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
    """Build a FastAPI app with the backtest router and patched data loader."""
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    monkeypatch.setenv("CSQAQ_CACHE_PATH", "/tmp/csqaq_test_cache")

    import src.api.backtest_endpoints as backtest_endpoints

    monkeypatch.setattr(backtest_endpoints, "_load_ohlc", lambda sub_index, period, **kwargs: _make_ohlc())

    fast_app = FastAPI()
    fast_app.include_router(backtest_router)
    return fast_app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_equity_returns_curve_and_trades(client):
    response = client.get("/backtest/equity", params={"sub_index": "手套", "period": "1day"})
    assert response.status_code == 200
    data = response.json()
    assert "equity_curve" in data
    assert "trades" in data
    assert "total_return" in data
    assert data["sub_index"] == "手套"
    assert data["period"] == "1day"
    if data["trades"]:
        trade = data["trades"][0]
        assert "entry_time" in trade
        assert "exit_reason" in trade


def test_equity_invalid_period_returns_400(client):
    response = client.get("/backtest/equity", params={"sub_index": "手套", "period": "10year"})
    assert response.status_code == 400
