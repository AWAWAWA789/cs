"""In-memory cache for scenario generation results.

The cache is intentionally simple: it stores the latest successful generation
per ``(sub_index, period)`` tuple and expires entries after a configurable TTL.
A manual refresh query parameter bypasses the cache and deletes the stored
entry for that key.
"""

from __future__ import annotations

import time
from typing import Any


class ScenarioCache:
    """TTL-backed in-memory cache for /scenario/generate responses."""

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(sub_index: str, period: str) -> str:
        return f"{sub_index}:{period}"

    def get(self, sub_index: str, period: str) -> Any | None:
        """Return a cached value if it has not expired."""
        key = self._key(sub_index, period)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry["stored_at"] > self._ttl:
            del self._store[key]
            return None
        return entry["value"]

    def set(self, sub_index: str, period: str, value: Any) -> None:
        """Store a new value for the given key."""
        self._store[self._key(sub_index, period)] = {
            "stored_at": time.monotonic(),
            "value": value,
        }

    def invalidate(self, sub_index: str, period: str) -> bool:
        """Remove a single key. Returns True if it existed."""
        key = self._key(sub_index, period)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def invalidate_all(self) -> None:
        """Clear every cached entry."""
        self._store.clear()


# Global cache instance used by the scenario API endpoints.
SCENARIO_CACHE = ScenarioCache(ttl_seconds=300.0)
