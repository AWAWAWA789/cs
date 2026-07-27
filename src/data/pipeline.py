"""Generic data pipeline: fetch, normalise, filter and cache OHLC data.

The pipeline is sub-index agnostic. Callers provide either a concrete
``sub_index_id`` or a ``sub_index_name`` that will be resolved via the
``/current_data?type=init`` endpoint.
"""

from __future__ import annotations

import pandas as pd

from src.api.client import CSQAQClient
from src.api.endpoints import get_current_data_init, get_sub_kline
from src.config import Settings
from src.data.cache import cache_file_path, exists, load, save


_CUTOFF = pd.Timestamp("2024-01-01", tz="UTC")


def resolve_sub_index_id(client: CSQAQClient, sub_index_name: str) -> str:
    """Look up a sub-index id by its Chinese name.

    Raises:
        ValueError: if no matching sub-index is found.
    """
    payload = get_current_data_init(client, skip_rate_limit=True)
    sub_index_data = payload.get("sub_index_data", [])
    for item in sub_index_data:
        if item.get("name") == sub_index_name:
            return str(item.get("id"))
    raise ValueError(f"Sub-index name not found: {sub_index_name}")


def normalize_kline(data: dict) -> pd.DataFrame:
    """Convert raw CSQAQ K-line payload into a standard OHLC DataFrame.

    The raw payload contains parallel arrays keyed by ``t``, ``o``, ``h``,
    ``l``, ``c`` and optionally ``v``. Timestamps are assumed to be
    milliseconds since epoch.
    """
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(data["t"], unit="ms", utc=True),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
        }
    )
    return df


def filter_from_2024(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows with timestamp >= 2024-01-01 UTC."""
    return df[df["timestamp"] >= _CUTOFF].reset_index(drop=True)


def fetch_ohlc(
    client: CSQAQClient, sub_index_id: str, period: str = "4hour"
) -> pd.DataFrame:
    """Fetch and normalise OHLC data for a given sub-index id and period."""
    raw = get_sub_kline(client, sub_index_id, period, skip_rate_limit=True)
    return normalize_kline(raw)


def load_or_fetch(
    settings: Settings,
    client: CSQAQClient,
    *,
    sub_index_id: str | None = None,
    sub_index_name: str | None = None,
    period: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Load OHLC data from cache or fetch from API, then persist to cache.

    Args:
        settings: Application settings; used for cache path defaults.
        client: CSQAQ API client.
        sub_index_id: Explicit sub-index id. If omitted, ``sub_index_name``
            is resolved via the API.
        sub_index_name: Sub-index name used for cache file naming and id
            resolution.
        period: K-line period. Defaults to ``settings.default_period``.
        force_refresh: If True, ignore the cache and refetch from the API.

    Returns:
        A DataFrame of OHLC data filtered to 2024-01-01 onwards.
    """
    period = period or settings.default_period
    sub_index_name = sub_index_name or settings.sub_index_name
    sub_index_id = sub_index_id or settings.sub_index_id

    if not sub_index_id:
        if not sub_index_name:
            raise ValueError("Either sub_index_id or sub_index_name must be provided")
        sub_index_id = resolve_sub_index_id(client, sub_index_name)

    cache_path = cache_file_path(sub_index_name, period, settings.cache_path)

    if not force_refresh and exists(cache_path):
        df = load(cache_path)
        if df is not None:
            return filter_from_2024(df)

    df = fetch_ohlc(client, sub_index_id, period)
    save(df, cache_path)
    return filter_from_2024(df)
