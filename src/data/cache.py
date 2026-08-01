"""Local Parquet cache for OHLC data.

The cache avoids repeated API calls by storing downloaded K-line data on disk.
Each sub-index / period combination gets its own Parquet file named
``{sub_index_name}_{period}.parquet`` where the period is normalised to a
short suffix (``1h``, ``4h``, ``1d``, ``7d``).
"""

from pathlib import Path

import pandas as pd


_PERIOD_SUFFIX = {
    "1hour": "1h",
    "4hour": "4h",
    "1day": "1d",
    "7day": "7d",
}


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


def load(path: str | Path) -> pd.DataFrame | None:
    """Load a DataFrame from a Parquet file if it exists.

    Returns ``None`` when the file is missing, letting callers fall back to
    the API.
    """
    path = Path(path)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def exists(path: str | Path) -> bool:
    """Check whether a cache file exists."""
    return Path(path).exists()
