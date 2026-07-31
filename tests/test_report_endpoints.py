"""Tests for the /reports endpoints."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with a temporary reports directory."""
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")

    # Create test report files
    (tmp_path / "test_report.json").write_text(json.dumps({"key": "value"}))
    (tmp_path / "empty.json").write_text("{}")
    (tmp_path / "not_json.txt").write_text("hello")

    from src.api import report_endpoints
    monkeypatch.setattr(report_endpoints, "REPORTS_DIR", tmp_path)

    from run_scenario_server import app
    return TestClient(app)


def test_list_returns_json_files(client):
    """/reports/list should return only .json files."""
    r = client.get("/reports/list")
    assert r.status_code == 200
    data = r.json()
    assert "reports" in data
    filenames = [f["filename"] for f in data["reports"]]
    assert "test_report.json" in filenames
    assert "empty.json" in filenames
    assert "not_json.txt" not in filenames


def test_list_file_has_metadata(client):
    """Each report file should have filename, size_bytes, and modified_at."""
    r = client.get("/reports/list")
    files = r.json()["reports"]
    assert len(files) > 0
    f = files[0]
    assert "filename" in f
    assert "size_bytes" in f
    assert "modified_at" in f
    assert isinstance(f["size_bytes"], int)
    assert f["size_bytes"] > 0


def test_get_returns_content(client):
    """/reports/get should return the parsed JSON content."""
    r = client.get("/reports/get", params={"filename": "test_report.json"})
    assert r.status_code == 200
    data = r.json()
    assert data["filename"] == "test_report.json"
    assert data["content"] == {"key": "value"}


def test_get_nonexistent_returns_404(client):
    r = client.get("/reports/get", params={"filename": "nonexistent.json"})
    assert r.status_code == 404


def test_get_path_traversal_blocked(client):
    """Path traversal attempts should return 404, not expose files."""
    r = client.get("/reports/get", params={"filename": "../../../etc/passwd"})
    assert r.status_code == 404


def test_get_absolute_path_blocked(client):
    """Absolute paths should be blocked."""
    r = client.get("/reports/get", params={"filename": "/etc/passwd"})
    assert r.status_code == 404
