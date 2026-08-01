"""Tests for the API monitoring collector."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.monitoring import COLLECTOR, MetricsCollector, monitoring_router


@pytest.fixture
def collector():
    return MetricsCollector(window_seconds=60.0)


def test_metrics_empty(collector):
    m = collector.metrics()
    assert m["request_count"] == 0
    assert m["failure_rate"] == 0.0


def test_failure_rate_calculation(collector):
    for _ in range(95):
        collector.record("/scenario/generate", 100.0, error=False)
    for _ in range(5):
        collector.record("/scenario/generate", 100.0, error=True)
    assert collector.metrics()["failure_rate"] == 0.05
    assert collector.check_alerts() == []


def test_failure_rate_alert(collector):
    for _ in range(10):
        collector.record("/scenario/generate", 100.0, error=True)
    alerts = collector.check_alerts()
    assert any(a["metric"] == "failure_rate" for a in alerts)


def test_latency_p99_alert(collector):
    for i in range(100):
        collector.record("/scenario/generate", float(i * 30), error=False)
    alerts = collector.check_alerts()
    assert any(a["metric"] == "latency_p99_ms" for a in alerts)


def test_window_eviction():
    collector = MetricsCollector(window_seconds=0.01)
    collector.record("/scenario/generate", 100.0, error=False)
    time.sleep(0.05)
    assert collector.metrics()["request_count"] == 0


@pytest.fixture
def monitoring_client(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    fast_app = FastAPI()
    fast_app.include_router(monitoring_router)
    return TestClient(fast_app)


def test_monitoring_metrics_endpoint(monitoring_client):
    response = monitoring_client.get("/monitoring/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "alerts" in data
    assert "thresholds" in data


def test_brier_drift_alert(collector, tmp_path, monkeypatch):
    baseline_path = tmp_path / "brier_baseline.json"
    baseline_path.write_text('{"brier_score": 0.20}')
    collector.set_brier_baseline_path(str(tmp_path))

    alerts = collector.check_alerts(current_brier=0.27)
    drift_alerts = [a for a in alerts if a["metric"] == "brier_drift"]
    assert len(drift_alerts) == 1
    assert drift_alerts[0]["value"] == pytest.approx(0.07, abs=1e-6)
    assert drift_alerts[0]["baseline"] == pytest.approx(0.20, abs=1e-6)


def test_brier_drift_no_alert_when_within_threshold(collector, tmp_path):
    baseline_path = tmp_path / "brier_baseline.json"
    baseline_path.write_text('{"brier_score": 0.20}')
    collector.set_brier_baseline_path(str(tmp_path))

    alerts = collector.check_alerts(current_brier=0.24)
    drift_alerts = [a for a in alerts if a["metric"] == "brier_drift"]
    assert drift_alerts == []


def test_brier_drift_no_alert_without_current_brier(collector, tmp_path):
    baseline_path = tmp_path / "brier_baseline.json"
    baseline_path.write_text('{"brier_score": 0.20}')
    collector.set_brier_baseline_path(str(tmp_path))

    alerts = collector.check_alerts()
    drift_alerts = [a for a in alerts if a["metric"] == "brier_drift"]
    assert drift_alerts == []
