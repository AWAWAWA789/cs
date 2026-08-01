"""Tests for the /backtest/mvp endpoint."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """Create a test client with deterministic synthetic OHLC data."""
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

    from src.api import backtest_endpoints
    monkeypatch.setattr(backtest_endpoints, "_load_ohlc", lambda sub_index, period, **kwargs: (df, "real"))

    from run_scenario_server import app
    return TestClient(app)


def test_mvp_returns_metrics_equity_and_trades(client):
    """MVP backtest should return metrics, equity_curve, and trades."""
    r = client.get("/backtest/mvp", params={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()

    assert data["sub_index"] == "手套"
    assert data["period"] == "1day"
    assert "generated_at" in data

    # metrics 验证
    metrics = data["metrics"]
    assert "total_return" in metrics
    assert "max_drawdown" in metrics
    assert "sharpe_ratio" in metrics
    assert "win_rate" in metrics
    assert "total_trades" in metrics
    assert isinstance(metrics["total_trades"], int)

    # equity_curve 验证
    eq = data["equity_curve"]
    assert isinstance(eq, list)
    assert len(eq) > 0
    assert "timestamp" in eq[0]
    assert "equity" in eq[0]

    # trades 验证
    trades = data["trades"]
    assert isinstance(trades, list)
    if len(trades) > 0:
        t = trades[0]
        assert "entry_time" in t
        assert "entry_price" in t
        assert "exit_reason" in t
        assert "pnl" in t
        assert "return_pct" in t


def test_mvp_invalid_period_returns_400(client):
    """Invalid period should return 400."""
    r = client.get("/backtest/mvp", params={"sub_index": "手套", "period": "10year"})
    assert r.status_code == 400
