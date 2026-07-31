"""Tests for the /data endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")

    # Create test parquet files
    import pandas as pd
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
        "open": [100.0] * 100,
        "high": [101.0] * 100,
        "low": [99.0] * 100,
        "close": [100.5] * 100,
    })
    df.to_parquet(tmp_path / "手套_1d.parquet", index=False)
    df.to_parquet(tmp_path / "匕首_4h.parquet", index=False)

    from src.api import data_endpoints
    monkeypatch.setattr(data_endpoints, "CACHE_DIR", tmp_path)

    from run_scenario_server import app
    return TestClient(app)


def test_cache_status_returns_files(client):
    """/data/cache-status should return parquet files with metadata."""
    r = client.get("/data/cache-status")
    assert r.status_code == 200
    data = r.json()
    assert "cache_dir" in data
    assert "total_files" in data
    assert "total_size_bytes" in data
    assert "files" in data
    assert data["total_files"] == 2

    filenames = [f["filename"] for f in data["files"]]
    assert "手套_1d.parquet" in filenames
    assert "匕首_4h.parquet" in filenames

    f = data["files"][0]
    assert "size_bytes" in f
    assert "bar_count" in f
    assert "modified_at" in f


def test_cache_status_empty_dir(tmp_path, monkeypatch):
    """Empty cache directory should return zero files."""
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    from src.api import data_endpoints
    monkeypatch.setattr(data_endpoints, "CACHE_DIR", empty_dir)

    from run_scenario_server import app
    c = TestClient(app)

    r = c.get("/data/cache-status")
    assert r.status_code == 200
    data = r.json()
    assert data["total_files"] == 0
    assert data["files"] == []


def test_refresh_returns_success(client):
    """/data/refresh should return success and bar_count."""
    r = client.post("/data/refresh", json={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()
    assert data["sub_index"] == "手套"
    assert data["success"] is True
    assert isinstance(data["bar_count"], int)


def test_refresh_invalid_period_returns_400(client):
    r = client.post("/data/refresh", json={"sub_index": "手套", "period": "10year"})
    assert r.status_code == 400
