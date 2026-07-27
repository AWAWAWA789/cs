"""Tests for the local Parquet cache helpers."""

import pandas as pd
import pytest

from src.data.cache import cache_file_path, exists, load, normalise_period, save


@pytest.mark.parametrize(
    "period,expected",
    [
        ("1hour", "1h"),
        ("4hour", "4h"),
        ("1day", "1d"),
        ("7day", "7d"),
        ("unknown", "unknown"),
    ],
)
def test_normalise_period(period, expected):
    assert normalise_period(period) == expected


def test_cache_file_path(tmp_path):
    path = cache_file_path("手套", "4hour", tmp_path)
    assert path.name == "手套_4h.parquet"
    assert path.parent == tmp_path


def test_save_and_load_roundtrip(tmp_path):
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
        }
    )
    path = tmp_path / "test.parquet"

    save(df, path)
    loaded = load(path)

    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, df)


def test_load_missing_file_returns_none(tmp_path):
    path = tmp_path / "missing.parquet"
    assert load(path) is None
    assert not exists(path)


def test_exists_after_save(tmp_path):
    df = pd.DataFrame({"a": [1, 2]})
    path = tmp_path / "nested" / "file.parquet"

    save(df, path)

    assert exists(path)
