"""Tests for the pre-computed state index builder."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.index_builder import (
    build_or_update_index,
    build_state_index,
    load_index,
    query_similar_states,
    save_index,
)


def _make_ohlc(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )


def test_build_state_index_has_required_columns():
    df = _make_ohlc(120)
    index_df = build_state_index(df)
    assert "timestamp" in index_df.columns
    assert any(c.startswith("future_return_") for c in index_df.columns)


def test_build_state_index_requires_ohlc():
    df = pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=10), "close": range(10)})
    with pytest.raises(ValueError, match="open, high, low, close"):
        build_state_index(df)


def test_save_and_load_index(tmp_path: Path):
    df = _make_ohlc(80)
    index_df = build_state_index(df)
    path = tmp_path / "index.parquet"
    save_index(index_df, path)
    loaded = load_index(path)
    assert loaded is not None
    assert len(loaded) == len(index_df)


def test_incremental_update_appends_only_new_rows(tmp_path: Path):
    df = _make_ohlc(100)
    base_dir = tmp_path / "index"
    path = build_or_update_index(df, "test", "1d", base_dir=base_dir)
    first_len = len(load_index(path))

    df2 = _make_ohlc(110)
    build_or_update_index(df2, "test", "1d", base_dir=base_dir)
    second_len = len(load_index(path))
    assert second_len > first_len

    # 重复更新不应再追加。
    build_or_update_index(df2, "test", "1d", base_dir=base_dir)
    third_len = len(load_index(path))
    assert third_len == second_len


def test_query_similar_states_returns_neighbors(tmp_path: Path):
    df = _make_ohlc(150)
    path = tmp_path / "index.parquet"
    save_index(build_state_index(df), path)

    query = {c: 0.0 for c in df.columns if c not in ("timestamp", "open", "high", "low", "close")}
    results = query_similar_states(path, query, n_neighbors=5)
    assert len(results) == 5
    assert all("distance" in r for r in results)
