"""预计算历史状态索引。

输入 OHLC DataFrame，构建并持久化状态向量索引，存储每条历史 K 线的状态向量、
时间戳与后续收益率。支持增量更新：只追加新 K 线，不重新计算已有数据。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.scenario_engine.state_vector import compute_state_vector, get_state_columns


DEFAULT_FUTURE_BARS = (5, 7, 10, 20)


def _compute_future_returns(
    close: pd.Series,
    future_bars: tuple[int, ...],
) -> pd.DataFrame:
    """为每个位置计算未来多 horizon 收益率。"""
    result: dict[str, pd.Series] = {}
    for bars in future_bars:
        key = f"future_return_{bars}"
        result[key] = (close.shift(-bars) - close) / close
    return pd.DataFrame(result, index=close.index)


def build_state_index(
    df: pd.DataFrame,
    state_columns: list[str] | None = None,
    future_bars: tuple[int, ...] = DEFAULT_FUTURE_BARS,
    extra_columns: list[str] | None = None,
) -> pd.DataFrame:
    """构建历史状态索引 DataFrame。

    Args:
        df: OHLC DataFrame，必须包含 ``timestamp``、``open``、``high``、
            ``low``、``close``。
        state_columns: 状态向量列名列表，默认使用 schema 定义。
        future_bars: 需要预计算的后续收益率 horizon。
        extra_columns: 需要额外保留的原始列名。

    Returns:
        包含 ``timestamp``、状态向量、未来收益率与可选额外列的 DataFrame。
    """
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        raise ValueError("df must contain open, high, low, close columns")

    state_columns = state_columns or get_state_columns()
    extra_columns = extra_columns or []

    state_df = compute_state_vector(df, state_columns=state_columns)
    returns_df = _compute_future_returns(state_df["close"], future_bars)

    cols = ["timestamp"] + list(state_columns) + list(returns_df.columns)
    for col in extra_columns:
        if col in state_df.columns and col not in cols:
            cols.append(col)

    result = pd.concat([state_df, returns_df], axis=1)[cols]
    return result.dropna(subset=state_columns).reset_index(drop=True)


def _index_path(
    base_dir: Path,
    sub_index_name: str,
    period: str,
) -> Path:
    """返回索引文件的持久化路径。"""
    base_dir.mkdir(parents=True, exist_ok=True)
    safe_period = str(period).replace("/", "_")
    safe_name = str(sub_index_name).replace("/", "_")
    return base_dir / f"{safe_name}_{safe_period}_state_index.parquet"


def save_index(
    index_df: pd.DataFrame,
    path: str | Path,
) -> Path:
    """将索引 DataFrame 保存为 parquet。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    index_df.to_parquet(path, index=False)
    return path


def load_index(path: str | Path) -> pd.DataFrame | None:
    """从 parquet 加载索引，文件不存在或解析失败时返回 ``None``。"""
    path = Path(path)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _merge_incremental(
    existing_df: pd.DataFrame | None,
    new_df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """合并已有索引与新索引，只追加新的时间戳。"""
    if existing_df is None or existing_df.empty:
        return new_df.reset_index(drop=True)

    existing_ts = set(existing_df[timestamp_col])
    filtered = new_df[~new_df[timestamp_col].isin(existing_ts)]
    if filtered.empty:
        return existing_df.reset_index(drop=True)

    combined = pd.concat([existing_df, filtered], ignore_index=True)
    combined = combined.sort_values(timestamp_col).reset_index(drop=True)
    return combined


def build_or_update_index(
    df: pd.DataFrame,
    sub_index_name: str,
    period: str,
    base_dir: str | Path = "data/scenario_index",
    *,
    state_columns: list[str] | None = None,
    future_bars: tuple[int, ...] = DEFAULT_FUTURE_BARS,
    extra_columns: list[str] | None = None,
    force_rebuild: bool = False,
) -> Path:
    """构建或增量更新预计算历史状态索引。

    Args:
        df: OHLC DataFrame。
        sub_index_name: 子指数名称，仅用于文件命名。
        period: K 线周期，仅用于文件命名。
        base_dir: 索引存储根目录。
        state_columns: 状态向量列名。
        future_bars: 预计算未来收益率 horizon。
        extra_columns: 需要额外保留的列。
        force_rebuild: 是否强制全量重建。

    Returns:
        保存后的索引文件路径。
    """
    base_dir = Path(base_dir)
    path = _index_path(base_dir, sub_index_name, period)

    new_index = build_state_index(
        df,
        state_columns=state_columns,
        future_bars=future_bars,
        extra_columns=extra_columns,
    )

    if force_rebuild:
        merged = new_index
    else:
        existing = load_index(path)
        merged = _merge_incremental(existing, new_index)

    save_index(merged, path)
    return path


def query_similar_states(
    index_path: str | Path,
    query_state: dict[str, float],
    state_columns: list[str] | None = None,
    n_neighbors: int = 10,
) -> list[dict[str, Any]]:
    """在预计算索引中查询与 ``query_state`` 最相似的历史状态。

    Args:
        index_path: 索引 parquet 文件路径。
        query_state: 当前状态向量字典。
        state_columns: 状态向量列名。
        n_neighbors: 返回的近邻数量。

    Returns:
        近邻结果列表，格式与 ``knn_search`` 类似。
    """
    index_df = load_index(index_path)
    if index_df is None or index_df.empty:
        return []

    state_columns = state_columns or get_state_columns()
    available = [c for c in state_columns if c in index_df.columns]
    if not available:
        return []

    train = index_df[available].to_numpy(dtype=float)
    query = np.array([float(query_state.get(c, 0.0)) for c in available], dtype=float)

    # 简单 z-score 归一化。
    mean = np.mean(train, axis=0)
    std = np.std(train, axis=0) + 1e-12
    train_scaled = (train - mean) / std
    query_scaled = (query - mean) / std

    diff = train_scaled - query_scaled
    distances = np.sqrt(np.sum(diff * diff, axis=1))
    order = np.argsort(distances)[:n_neighbors]

    results: list[dict[str, Any]] = []
    for idx in order:
        row = index_df.iloc[idx]
        result: dict[str, Any] = {
            "neighbor_index": int(idx),
            "distance": float(distances[idx]),
            "state": {c: float(row[c]) for c in available},
        }
        if "timestamp" in index_df.columns:
            result["neighbor_timestamp"] = str(row["timestamp"])
        for col in index_df.columns:
            if col.startswith("future_return_"):
                result[col] = float(row[col]) if pd.notna(row[col]) else None
        results.append(result)
    return results
