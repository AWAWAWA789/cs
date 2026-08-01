"""单品 OHLC 落盘缓存层。

历史训练需要批量回填大量单品两年日线，原 `accumulation_endpoints._fetch_item_price_series`
仅做内存 60s TTL 缓存，重启即失。本模块提供持久化的 Parquet 落盘能力。

落盘路径约定：
    {cache_root}/item_cache/{category}/{good_id}_{period_suffix}.parquet

其中 category 是品类（rifle/knife/glove...），用于按品类批量加载训练。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.cache import load, save

_PERIOD_SUFFIX = {
    "1hour": "1h",
    "4hour": "4h",
    "1day": "1d",
    "7day": "7d",
}


def item_cache_path(
    good_id: str,
    period: str,
    cache_root: str | Path,
    category: str = "rifle",
) -> Path:
    """构建单品 OHLC 落盘路径。

    Args:
        good_id: 饰品 good_id
        period: 周期（1hour/4hour/1day/7day）
        cache_root: 缓存根目录（通常 Settings().cache_path）
        category: 品类目录名

    Returns:
        完整路径，如 ``data/cache/item_cache/rifle/2_1d.parquet``
    """
    suffix = _PERIOD_SUFFIX.get(period, period)
    return Path(cache_root) / "item_cache" / category / f"{good_id}_{suffix}.parquet"


def save_item_ohlc(
    df: pd.DataFrame,
    good_id: str,
    period: str,
    cache_root: str | Path,
    category: str = "rifle",
) -> Path:
    """落盘单品 OHLC 数据。

    Args:
        df: 含 timestamp/open/high/low/close 列的 DataFrame
        good_id: 饰品 good_id
        period: 周期
        cache_root: 缓存根目录
        category: 品类

    Returns:
        实际写入的路径
    """
    path = item_cache_path(good_id, period, cache_root, category)
    save(df, path)
    return path


def load_item_ohlc(
    good_id: str,
    period: str,
    cache_root: str | Path,
    category: str = "rifle",
) -> pd.DataFrame | None:
    """加载单品 OHLC 数据。

    Returns:
        DataFrame 或 None（文件不存在时）
    """
    path = item_cache_path(good_id, period, cache_root, category)
    return load(path)


def list_cached_items(
    cache_root: str | Path,
    category: str = "rifle",
    period: str = "1day",
) -> list[str]:
    """列出某品类下已落盘的 good_id 列表。

    用于训练前统计已回填的样本量。
    """
    suffix = _PERIOD_SUFFIX.get(period, period)
    dir_path = Path(cache_root) / "item_cache" / category
    if not dir_path.exists():
        return []
    pattern = f"*_{suffix}.parquet"
    return [
        p.stem.rsplit("_", 1)[0]
        for p in dir_path.glob(pattern)
    ]
