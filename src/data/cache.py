"""Local Parquet cache for OHLC data.

The cache avoids repeated API calls by storing downloaded K-line data on disk.
Each sub-index / period combination gets its own Parquet file named
``{sub_index_name}_{period}.parquet`` where the period is normalised to a
short suffix (``1h``, ``4h``, ``1d``, ``7d``).

A small in-memory TTL layer (``load_cached``) sits in front of the disk
``load`` so that the hot path — repeated reads of the same parquet file
within a single process — does not pay the I/O + deserialization cost on
every call. Entries are invalidated automatically when ``save`` writes to
the same path.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd


_PERIOD_SUFFIX = {
    "1hour": "1h",
    "4hour": "4h",
    "1day": "1d",
    "7day": "7d",
}

# ── In-memory TTL layer ──────────────────────────────────────
# Maps ``str(path)`` → ``(stored_at_monotonic, df)``. Kept intentionally
# tiny because at most a handful of (sub_index, period) files are hot at
# any time. The TTL is short on purpose: the freshness decision (real vs
# stale_cache vs synthetic) lives in ``scenario_endpoints._load_ohlc``;
# this layer only avoids re-reading the same bytes within that window.
_PARQUET_MEM_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}
_PARQUET_MEM_TTL: float = 60.0


def normalise_period(period: str) -> str:
    """Return the short suffix for a known period.

    Unknown periods are returned unchanged, which preserves flexibility for
    future API additions while keeping the documented naming convention.
    """
    return _PERIOD_SUFFIX.get(period, period)


def cache_file_path(sub_index_name: str, period: str, cache_dir: str | Path) -> Path:
    """Build the cache file path for a given sub-index and period."""
    suffix = normalise_period(period)
    filename = f"{sub_index_name}_{suffix}.parquet"
    return Path(cache_dir) / filename


def save(df: pd.DataFrame, path: str | Path) -> None:
    """Save a DataFrame to a Parquet file, creating parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    # Drop any stale in-memory entry so the next read picks up the new file.
    invalidate_mem_cache(path)


def load(path: str | Path) -> pd.DataFrame | None:
    """Load a DataFrame from a Parquet file if it exists.

    Returns ``None`` when the file is missing, letting callers fall back to
    the API. This bypasses the in-memory layer — use :func:`load_cached`
    for the hot path.
    """
    path = Path(path)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def invalidate_mem_cache(path: str | Path) -> None:
    """Drop a single path from the in-memory parquet layer, if present."""
    _PARQUET_MEM_CACHE.pop(str(Path(path)), None)


def invalidate_all_mem_cache() -> None:
    """Clear every entry in the in-memory parquet layer."""
    _PARQUET_MEM_CACHE.clear()


def load_cached(path: str | Path, *, ttl: float = _PARQUET_MEM_TTL) -> pd.DataFrame | None:
    """Load a DataFrame, using the in-memory TTL layer to avoid disk reads.

    Behaves like :func:`load` for the cold path but returns the cached
    DataFrame when the same path was read within the last ``ttl`` seconds.
    A negative ``ttl`` disables the in-memory layer (useful for tests that
    need to observe on-disk state directly).
    """
    key = str(Path(path))
    if ttl >= 0:
        entry = _PARQUET_MEM_CACHE.get(key)
        if entry is not None:
            stored_at, df = entry
            if time.monotonic() - stored_at <= ttl:
                return df
            # Expired — drop the entry before re-reading from disk.
            del _PARQUET_MEM_CACHE[key]

    df = load(path)
    if df is not None and ttl >= 0:
        _PARQUET_MEM_CACHE[key] = (time.monotonic(), df)
    return df


def exists(path: str | Path) -> bool:
    """Check whether a cache file exists."""
    return Path(path).exists()
