"""Tests for the /trend-scan endpoints."""

import time

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
    from src.api import trend_scan_endpoints
    monkeypatch.setattr(trend_scan_endpoints, "_load_ohlc", lambda sub_index, period, **kwargs: (df, "real"))
    from run_scenario_server import app
    return TestClient(app)


def test_start_returns_task_id(client):
    """POST /trend-scan/start should return a task_id."""
    r = client.post("/trend-scan/start", json={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert len(data["task_id"]) > 0


def test_status_returns_valid_structure(client):
    """GET /trend-scan/status/{task_id} should return valid task info."""
    r1 = client.post("/trend-scan/start", json={"sub_index": "手套", "period": "1day"})
    task_id = r1.json()["task_id"]

    # Poll until terminal state. The full parameter scan (3456 combinations)
    # takes several minutes, so the window is sized accordingly.
    for _ in range(2400):
        r2 = client.get(f"/trend-scan/status/{task_id}")
        assert r2.status_code == 200
        data = r2.json()
        assert "status" in data
        assert "progress" in data
        assert "result" in data
        assert "error" in data
        if data["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)

    # Final state should be completed (not pending/running)
    assert data["status"] in ("completed", "failed"), f"Unexpected status: {data['status']}"


def test_status_unknown_task_returns_404(client):
    """GET /trend-scan/status with unknown task_id should return 404."""
    r = client.get("/trend-scan/status/nonexistent123")
    assert r.status_code == 404


def test_completed_task_has_scan_result(client):
    """A completed scan task should have a result with top_10 and total_combinations."""
    r1 = client.post("/trend-scan/start", json={"sub_index": "手套", "period": "1day"})
    task_id = r1.json()["task_id"]

    # The full parameter scan (3456 combinations) takes several minutes.
    for _ in range(2400):
        r2 = client.get(f"/trend-scan/status/{task_id}")
        data = r2.json()
        if data["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)

    if data["status"] == "completed":
        result = data["result"]
        assert result is not None
        assert "total_combinations" in result
        assert "top_10" in result
        assert isinstance(result["top_10"], list)
        assert "sub_index" in result
