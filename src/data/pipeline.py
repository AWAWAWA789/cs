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


def resolve_sub_index_id(
    client: CSQAQClient, sub_index_name: str, skip_rate_limit: bool = False
) -> str:
    """Look up a sub-index id by its Chinese name.

    Exact matches take precedence; if none are found, the first name that
    contains ``sub_index_name`` as a substring is used.

    Args:
        client: CSQAQ API client.
        sub_index_name: Sub-index name to resolve.
        skip_rate_limit: Bypass client-side rate limiting. Intended for tests.

    Raises:
        ValueError: if no matching sub-index is found.
    """
    payload = get_current_data_init(client, skip_rate_limit=skip_rate_limit)
    sub_index_data = payload.get("sub_index_data", [])

    for item in sub_index_data:
        if item.get("name") == sub_index_name:
            return str(item.get("id"))

    for item in sub_index_data:
        name = item.get("name", "")
        if sub_index_name in name:
            return str(item.get("id"))

    raise ValueError(f"Sub-index name not found: {sub_index_name}")


def normalize_kline(data: dict | list) -> pd.DataFrame:
    """Convert raw CSQAQ K-line payload into a standard OHLC DataFrame.

    The API returns either:
    - A list of records: ``[{t, o, h, l, c, v}, ...]``
    - A dict of parallel arrays: ``{t: [...], o: [...], ...}``

    Timestamps are treated as milliseconds since epoch.
    """
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(data)

    df = df.rename(
        columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close"}
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True)
    return df[["timestamp", "open", "high", "low", "close"]]


def filter_from_2024(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows with timestamp >= 2024-01-01 UTC."""
    return df[df["timestamp"] >= _CUTOFF].reset_index(drop=True)


def fetch_ohlc(
    client: CSQAQClient,
    sub_index_id: str,
    period: str = "4hour",
    skip_rate_limit: bool = False,
) -> pd.DataFrame:
    """Fetch and normalise OHLC data for a given sub-index id and period.

    Args:
        client: CSQAQ API client.
        sub_index_id: Sub-index id.
        period: K-line period.
        skip_rate_limit: Bypass client-side rate limiting. Intended for tests.
    """
    raw = get_sub_kline(
        client, sub_index_id, period, skip_rate_limit=skip_rate_limit
    )
    return normalize_kline(raw)


def load_or_fetch(
    settings: Settings,
    client: CSQAQClient,
    *,
    sub_index_id: str | None = None,
    sub_index_name: str | None = None,
    period: str | None = None,
    force_refresh: bool = False,
    skip_rate_limit: bool = False,
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
        skip_rate_limit: Bypass client-side rate limiting. Intended for tests.

    Returns:
        A DataFrame of OHLC data filtered to 2024-01-01 onwards.
    """
    period = period or settings.default_period
    sub_index_name = sub_index_name or settings.sub_index_name
    sub_index_id = sub_index_id or settings.sub_index_id

    if not sub_index_id:
        if not sub_index_name:
            raise ValueError("Either sub_index_id or sub_index_name must be provided")
        sub_index_id = resolve_sub_index_id(
            client, sub_index_name, skip_rate_limit=skip_rate_limit
        )

    cache_path = cache_file_path(sub_index_name, period, settings.cache_path)

    if not force_refresh and exists(cache_path):
        df = load(cache_path)
        if df is not None:
            return filter_from_2024(df)

    df = fetch_ohlc(client, sub_index_id, period, skip_rate_limit=skip_rate_limit)
    save(df, cache_path)
    return filter_from_2024(df)
