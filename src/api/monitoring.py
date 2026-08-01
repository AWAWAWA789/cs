"""Runtime monitoring and alerting for the scenario API.

Keeps a small in-memory rolling window of request latencies and outcomes.
Exposes aggregated metrics and logs alerts when thresholds are breached.
"""

from __future__ import annotations

import dataclasses
import json
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from src.api.logging import get_logger


LOGGER = get_logger("csqaq.monitoring")


@dataclasses.dataclass(frozen=True)
class RequestRecord:
    """A single request observation."""

    endpoint: str
    latency_ms: float
    error: bool
    timestamp: float


@dataclasses.dataclass
class AlertThresholds:
    """Configurable alert thresholds."""

    failure_rate: float = 0.05
    latency_p99_ms: float = 2000.0
    brier_drift: float = 0.05


class MetricsCollector:
    """Thread-safe rolling-window metrics collector."""

    def __init__(self, window_seconds: float = 300.0) -> None:
        self._window_seconds = window_seconds
        self._records: deque[RequestRecord] = deque()
        self._lock = threading.Lock()
        self._thresholds = AlertThresholds()
        self._brier_baseline: float | None = None
        self._brier_baseline_path: Path | None = None

    def record(
        self,
        endpoint: str,
        latency_ms: float,
        error: bool = False,
    ) -> None:
        """Record a request observation."""
        now = time.time()
        record = RequestRecord(
            endpoint=endpoint,
            latency_ms=float(latency_ms),
            error=error,
            timestamp=now,
        )
        with self._lock:
            self._records.append(record)
            self._evict_old(now)

    def update_brier_baseline(self, brier_score: float) -> None:
        """Set the current Brier baseline for drift detection."""
        self._brier_baseline = float(brier_score)

    def set_brier_baseline_path(self, path: Path | str | None) -> None:
        """Set the directory from which to load a persisted Brier baseline."""
        self._brier_baseline_path = Path(path) if path else None

    def _load_brier_baseline(self) -> float | None:
        """Return the Brier baseline from memory or from disk."""
        if self._brier_baseline is not None:
            return self._brier_baseline
        if self._brier_baseline_path is None:
            return None
        path = self._brier_baseline_path / "brier_baseline.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return float(data.get("brier_score", data.get("value", 0.0)))

    def _evict_old(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._records and self._records[0].timestamp < cutoff:
            self._records.popleft()

    def _recent_records(self) -> list[RequestRecord]:
        now = time.time()
        with self._lock:
            self._evict_old(now)
            return list(self._records)

    def metrics(self) -> dict[str, Any]:
        """Return aggregated metrics for the current window."""
        records = self._recent_records()
        if not records:
            return {
                "window_seconds": self._window_seconds,
                "request_count": 0,
                "failure_count": 0,
                "failure_rate": 0.0,
                "latency_p50_ms": 0.0,
                "latency_p99_ms": 0.0,
                "brier_baseline": self._brier_baseline,
            }

        latencies = sorted(r.latency_ms for r in records)
        failure_count = sum(1 for r in records if r.error)
        request_count = len(records)
        failure_rate = failure_count / request_count
        p50 = latencies[len(latencies) // 2]
        p99_idx = int(len(latencies) * 0.99) or len(latencies) - 1
        p99 = latencies[p99_idx]

        per_endpoint: dict[str, dict[str, Any]] = {}
        for endpoint in {r.endpoint for r in records}:
            ep_records = [r for r in records if r.endpoint == endpoint]
            ep_latencies = sorted(r.latency_ms for r in ep_records)
            ep_failures = sum(1 for r in ep_records if r.error)
            per_endpoint[endpoint] = {
                "request_count": len(ep_records),
                "failure_rate": ep_failures / len(ep_records),
                "latency_p99_ms": ep_latencies[
                    int(len(ep_latencies) * 0.99) or len(ep_latencies) - 1
                ],
            }

        return {
            "window_seconds": self._window_seconds,
            "request_count": request_count,
            "failure_count": failure_count,
            "failure_rate": round(failure_rate, 6),
            "latency_p50_ms": round(p50, 3),
            "latency_p99_ms": round(p99, 3),
            "brier_baseline": self._brier_baseline,
            "per_endpoint": per_endpoint,
        }

    def check_alerts(self, current_brier: float | None = None) -> list[dict[str, Any]]:
        """Check thresholds and return active alerts."""
        records = self._recent_records()
        alerts: list[dict[str, Any]] = []

        if records:
            latencies = sorted(r.latency_ms for r in records)
            failure_count = sum(1 for r in records if r.error)
            failure_rate = failure_count / len(records)
            p99_idx = int(len(latencies) * 0.99) or len(latencies) - 1
            p99 = latencies[p99_idx]

            if failure_rate > self._thresholds.failure_rate:
                alerts.append(
                    {
                        "metric": "failure_rate",
                        "value": round(failure_rate, 4),
                        "threshold": self._thresholds.failure_rate,
                        "severity": "critical",
                    }
                )
            if p99 > self._thresholds.latency_p99_ms:
                alerts.append(
                    {
                        "metric": "latency_p99_ms",
                        "value": round(p99, 3),
                        "threshold": self._thresholds.latency_p99_ms,
                        "severity": "warning",
                    }
                )

        baseline = self._load_brier_baseline()
        if baseline is not None and current_brier is not None:
            drift = current_brier - baseline
            if drift > self._thresholds.brier_drift:
                alerts.append(
                    {
                        "metric": "brier_drift",
                        "value": round(drift, 4),
                        "threshold": self._thresholds.brier_drift,
                        "current_brier": round(current_brier, 4),
                        "baseline": round(baseline, 4),
                        "severity": "warning",
                    }
                )
        return alerts

    def log_alerts(self) -> None:
        """Log any active alerts."""
        for alert in self.check_alerts():
            LOGGER.warning(
                "Monitoring alert: %(metric)s=%(value)s exceeds threshold %(threshold)s",
                alert,
            )


# Singleton collector used across API endpoints.
COLLECTOR = MetricsCollector()


def record_request(endpoint: str, latency_ms: float, error: bool = False) -> None:
    """Record a request and immediately check for alerts."""
    COLLECTOR.record(endpoint, latency_ms, error)
    COLLECTOR.log_alerts()


monitoring_router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@monitoring_router.get("/metrics")
def metrics() -> dict[str, Any]:
    """Return current rolling-window metrics and active alerts."""
    return {
        "metrics": COLLECTOR.metrics(),
        "alerts": COLLECTOR.check_alerts(),
        "thresholds": dataclasses.asdict(COLLECTOR._thresholds),
    }
