"""Build a market-state vector for each bar.

The state vector is a fixed, interpretable feature set used by the historical
similarity-search engine. It is computed from OHLC data and time only; no
volume information is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from src.features.signal_quality import (
    _confluence_quality,
    _structure_resonance,
    _trend_quality,
    add_signal_quality_features,
)
from src.features.trend_strength import add_trend_strength_features
from src.strategy.signal import SignalParams, generate_signals


_SCHEMA_PATH = Path(__file__).parents[2] / "config" / "state_vector_schema.json"

# 全局缓存：schema 文件在运行期间不变，避免每次重复读取与解析 JSON。
_SCHEMA_CACHE: dict[str | Path, dict] = {}
_COLUMNS_CACHE: dict[int, list[str]] = {}
_WEIGHTS_CACHE: dict[int, np.ndarray] = {}


def load_state_vector_schema(path: str | Path | None = None) -> dict:
    """Load the state-vector JSON schema.

    Args:
        path: Optional path to a custom schema file. Defaults to the bundled
            ``config/state_vector_schema.json``.

    Returns:
        Parsed schema dictionary.
    """
    path = Path(path or _SCHEMA_PATH)
    key = str(path)
    if key not in _SCHEMA_CACHE:
        with path.open("r", encoding="utf-8") as f:
            _SCHEMA_CACHE[key] = json.load(f)
    return _SCHEMA_CACHE[key]


def get_state_columns(schema: dict | None = None) -> list[str]:
    """Return the ordered list of state-vector column names from ``schema``."""
    schema = schema or load_state_vector_schema()
    cache_key = id(schema)
    if cache_key not in _COLUMNS_CACHE:
        _COLUMNS_CACHE[cache_key] = list(schema["fields"].keys())
    return _COLUMNS_CACHE[cache_key]


def get_state_weights(schema: dict | None = None) -> np.ndarray:
    """Return a NumPy array of state-vector feature weights in schema order."""
    schema = schema or load_state_vector_schema()
    cache_key = id(schema)
    if cache_key not in _WEIGHTS_CACHE:
        _WEIGHTS_CACHE[cache_key] = np.array(
            [field["weight"] for field in schema["fields"].values()], dtype=float
        )
    return _WEIGHTS_CACHE[cache_key]


def _last_swing_price(
    df: pd.DataFrame,
    price_col: str,
    swing_col: str,
) -> pd.Series:
    """Forward-fill the most recent swing price and fall back to the current price."""
    swing_price = df[price_col].where(df[swing_col]).ffill()
    return swing_price.fillna(df[price_col])


def _add_moving_average_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA20 / SMA50 and related relative-position columns."""
    result = df.copy()
    close = result["close"]
    result["sma20"] = close.rolling(window=20, min_periods=1).mean()
    result["sma50"] = close.rolling(window=50, min_periods=1).mean()
    result["price_vs_sma20"] = ((close - result["sma20"]) / result["sma20"]).clip(-2.0, 2.0)
    result["price_vs_sma50"] = ((close - result["sma50"]) / result["sma50"]).clip(-2.0, 2.0)
    result["sma20_vs_sma50"] = (
        (result["sma20"] - result["sma50"]) / result["sma50"]
    ).clip(-1.0, 1.0)
    return result


def _add_bollinger_features(df: pd.DataFrame, window: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Add Bollinger Band relative position column ``bb_position``."""
    result = df.copy()
    close = result["close"]
    middle = close.rolling(window=window, min_periods=1).mean()
    band = std * close.rolling(window=window, min_periods=1).std()
    upper = middle + band
    lower = middle - band
    width = (upper - lower).replace(0.0, np.nan)
    result["bb_position"] = ((close - lower) / width).clip(0.0, 1.0).fillna(0.5)
    return result


def _add_volatility_regime(df: pd.DataFrame, window: int = 50) -> pd.DataFrame:
    """Add ``volatility_regime`` column based on ATR% relative to its median."""
    result = df.copy()
    atr_percent = result["atr_percent"]
    median = atr_percent.rolling(window=window, min_periods=1).median()
    regime = pd.Series(1, index=result.index, dtype=int)
    low_mask = atr_percent < 0.6 * median
    high_mask = atr_percent > 1.4 * median
    regime = regime.where(~low_mask, 0)
    regime = regime.where(~high_mask, 2)
    result["volatility_regime"] = regime
    return result


def _add_swing_position_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add distance-to-swing and swing-position-ratio columns."""
    result = df.copy()
    close = result["close"]

    last_swing_low = _last_swing_price(result, "low", "swing_low")
    last_swing_high = _last_swing_price(result, "high", "swing_high")
    result["last_swing_low"] = last_swing_low
    result["last_swing_high"] = last_swing_high

    result["distance_to_swing_low"] = (
        (close - last_swing_low) / last_swing_low
    ).clip(-1.0, 1.0).fillna(0.0)
    result["distance_to_swing_high"] = (
        (close - last_swing_high) / last_swing_high
    ).clip(-1.0, 1.0).fillna(0.0)

    swing_range = (last_swing_high - last_swing_low).abs().replace(0.0, np.nan)
    result["swing_position_ratio"] = (
        (close - last_swing_low) / swing_range
    ).clip(0.0, 1.0).fillna(0.5)
    return result


def _add_signal_quality_components(df: pd.DataFrame) -> pd.DataFrame:
    """Add decomposed signal-quality columns: trend, structure, confluence."""
    result = df.copy()
    # Ensure ADX/DI exist for trend-quality.
    result = add_trend_strength_features(result)
    result["trend_quality"] = _trend_quality(result)
    result["structure_resonance"] = _structure_resonance(
        result, swing_low_col="last_swing_low", price_col="close", buffer=0.05
    )
    result["confluence_quality"] = _confluence_quality(result)
    return result


def compute_state_vector(
    df: pd.DataFrame,
    signal_params: SignalParams | None = None,
    state_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Compute the market-state vector for every bar in ``df``.

    The returned DataFrame contains all original columns plus the state-vector
    fields defined in ``config/state_vector_schema.json``.

    Args:
        df: OHLC DataFrame. Expected columns: ``open``, ``high``, ``low``,
            ``close`` and optionally ``timestamp``.
        signal_params: Optional signal-generation parameters. Defaults to a
            configuration that enables Smart Money, trend-following and
            signal-quality diagnostics.
        state_columns: Optional subset of state-vector columns to retain. When
            ``None`` all schema fields are produced.

    Returns:
        A DataFrame with state-vector columns appended.
    """
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        raise ValueError("df must contain open, high, low and close columns")

    params = signal_params or SignalParams(
        swing_order=2,
        fib_tolerance=0.03,
        confirmations=1,
        use_smart_money=True,
        use_trend_following=True,
        use_signal_quality=True,
    )

    result = generate_signals(df, params)
    result = add_trend_strength_features(result)
    result["adx_normalized"] = (result["adx"] / 100.0).clip(0.0, 1.0)
    result["di_plus_minus_diff"] = (result["di_plus"] - result["di_minus"]).clip(-100.0, 100.0)
    result["atr_percent"] = (result["atr"] / result["close"] * 100.0).fillna(0.0)

    result = _add_bollinger_features(result)
    result = _add_volatility_regime(result)
    result = _add_swing_position_features(result)
    result = _add_moving_average_features(result)
    result = _add_signal_quality_components(result)

    if state_columns is None:
        state_columns = get_state_columns()
    else:
        state_columns = list(state_columns)

    # Preserve a stable column order: original + state vector.
    original_cols = [c for c in df.columns if c not in state_columns]
    ordered_cols = original_cols + list(state_columns)
    missing = set(state_columns) - set(result.columns)
    if missing:
        raise RuntimeError(f"Missing state-vector columns: {missing}")
    return result[ordered_cols]
