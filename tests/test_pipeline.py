"""Tests for the generic data pipeline."""

import pandas as pd
import pytest
import responses

from src.api.client import CSQAQClient
from src.config import Settings
from src.data.pipeline import (
    fetch_ohlc,
    filter_from_2024,
    load_or_fetch,
    normalize_kline,
    resolve_sub_index_id,
)


@pytest.fixture
def settings(monkeypatch, tmp_path):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "test-token")
    monkeypatch.setenv("CSQAQ_BASE_URL", "https://api.csqaq.com/api/v1")
    monkeypatch.setenv("CSQAQ_CACHE_PATH", str(tmp_path))
    monkeypatch.setenv("SUB_INDEX_NAME", "手套")
    monkeypatch.setenv("DEFAULT_PERIOD", "4hour")
    return Settings()


@pytest.fixture
def client(settings):
    return CSQAQClient(settings)


def test_normalize_kline_converts_timestamp_and_columns():
    raw = {
        "t": [1704067200000, 1704153600000],  # 2024-01-01, 2024-01-02 UTC
        "o": [100.0, 101.0],
        "c": [101.0, 102.0],
        "h": [102.0, 103.0],
        "l": [99.0, 100.0],
        "v": [0, 0],
    }

    df = normalize_kline(raw)

    assert list(df.columns) == ["timestamp", "open", "high", "low", "close"]
    assert df["timestamp"].iloc[0] == pd.Timestamp("2024-01-01", tz="UTC")
    assert df["close"].iloc[1] == 102.0


def test_filter_from_2024_keeps_only_recent_rows():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2023-12-31", "2024-01-01", "2024-06-01"], utc=True
            ),
            "close": [1.0, 2.0, 3.0],
        }
    )

    filtered = filter_from_2024(df)

    assert len(filtered) == 2
    assert filtered["timestamp"].iloc[0] == pd.Timestamp("2024-01-01", tz="UTC")


@responses.activate
def test_resolve_sub_index_id(client):
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={
            "code": 200,
            "msg": "Success",
            "data": {
                "sub_index_data": [
                    {"id": "1", "name": "手套"},
                    {"id": "2", "name": "匕首"},
                ]
            },
        },
        status=200,
    )

    assert resolve_sub_index_id(client, "手套") == "1"
    assert resolve_sub_index_id(client, "匕首") == "2"


@responses.activate
def test_resolve_sub_index_id_raises_when_not_found(client):
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={
            "code": 200,
            "msg": "Success",
            "data": {"sub_index_data": [{"id": "1", "name": "手套"}]},
        },
        status=200,
    )

    with pytest.raises(ValueError, match="Sub-index name not found"):
        resolve_sub_index_id(client, "步枪")


@responses.activate
def test_fetch_ohlc(client):
    responses.get(
        "https://api.csqaq.com/api/v1/sub/kline?id=1&type=4hour",
        json={
            "code": 200,
            "msg": "Success",
            "data": {
                "t": [1704067200000],
                "o": [100.0],
                "c": [101.0],
                "h": [102.0],
                "l": [99.0],
                "v": [0],
            },
        },
        status=200,
    )

    df = fetch_ohlc(client, "1", "4hour")

    assert len(df) == 1
    assert df["close"].iloc[0] == 101.0


@responses.activate
def test_load_or_fetch_uses_cache_when_available(settings, client, tmp_path):
    cache_df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2023-06-01", "2024-01-02"], utc=True
            ),
            "open": [1.0, 2.0],
            "high": [1.0, 2.0],
            "low": [1.0, 2.0],
            "close": [1.0, 2.0],
        }
    )
    cache_path = tmp_path / "手套_4h.parquet"
    cache_df.to_parquet(cache_path, index=False)

    df = load_or_fetch(settings, client, sub_index_id="1")

    assert len(df) == 1
    assert df["timestamp"].iloc[0] == pd.Timestamp("2024-01-02", tz="UTC")


@responses.activate
def test_load_or_fetch_fetches_and_caches_when_missing(settings, client):
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={
            "code": 200,
            "msg": "Success",
            "data": {"sub_index_data": [{"id": "1", "name": "手套"}]},
        },
        status=200,
    )
    responses.get(
        "https://api.csqaq.com/api/v1/sub/kline?id=1&type=4hour",
        json={
            "code": 200,
            "msg": "Success",
            "data": {
                "t": [1704067200000, 1704153600000],
                "o": [100.0, 101.0],
                "c": [101.0, 102.0],
                "h": [102.0, 103.0],
                "l": [99.0, 100.0],
                "v": [0, 0],
            },
        },
        status=200,
    )

    df = load_or_fetch(settings, client)

    assert len(df) == 2
    assert df["close"].iloc[-1] == 102.0
