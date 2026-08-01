"""Segment normalization and distance metrics for state vectors.

All functions are vectorised and accept either ``pandas.DataFrame`` or
``numpy.ndarray`` inputs. They are intentionally dependency-light so that the
scenario engine keeps working even when optional libraries such as Faiss are
missing.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def z_score(data: np.ndarray | pd.DataFrame, eps: float = 1e-12) -> np.ndarray:
    """Return a Z-Score normalised copy of ``data``.

    Each feature is transformed to zero mean and unit variance. Features with
    zero standard deviation are left unchanged.
    """
    arr = np.asarray(data, dtype=float)
    if arr.ndim == 1:
        mean = float(np.mean(arr))
        std = float(np.std(arr)) + eps
        return (arr - mean) / std

    mean = np.mean(arr, axis=0, keepdims=True)
    std = np.std(arr, axis=0, keepdims=True) + eps
    return (arr - mean) / std


def min_max_scale(
    data: np.ndarray | pd.DataFrame,
    feature_range: tuple[float, float] = (0.0, 1.0),
    eps: float = 1e-12,
) -> np.ndarray:
    """Return a Min-Max scaled copy of ``data`` mapped to ``feature_range``.

    Features with zero range are mapped to the lower bound of ``feature_range``.
    """
    arr = np.asarray(data, dtype=float)
    low, high = feature_range
    if arr.ndim == 1:
        min_ = float(np.min(arr))
        max_ = float(np.max(arr))
        denom = (max_ - min_) + eps
        return low + (arr - min_) / denom * (high - low)

    min_ = np.min(arr, axis=0, keepdims=True)
    max_ = np.max(arr, axis=0, keepdims=True)
    denom = (max_ - min_) + eps
    return low + (arr - min_) / denom * (high - low)


def robust_scale(
    data: np.ndarray | pd.DataFrame,
    quantile_range: tuple[float, float] = (25.0, 75.0),
    eps: float = 1e-12,
) -> np.ndarray:
    """Return a robustly scaled copy of ``data`` using median and IQR.

    The centre is subtracted and the result is divided by the inter-quartile
    range. This is less sensitive to outliers than Z-Score normalisation.
    """
    arr = np.asarray(data, dtype=float)
    q_low, q_high = quantile_range
    if arr.ndim == 1:
        median = float(np.median(arr))
        iqr = float(np.percentile(arr, q_high) - np.percentile(arr, q_low)) + eps
        return (arr - median) / iqr

    median = np.median(arr, axis=0, keepdims=True)
    q1 = np.percentile(arr, q_low, axis=0, keepdims=True)
    q3 = np.percentile(arr, q_high, axis=0, keepdims=True)
    iqr = (q3 - q1) + eps
    return (arr - median) / iqr


# ---------------------------------------------------------------------------
# Distance metrics
# ---------------------------------------------------------------------------

def _to_vector(value: np.ndarray | pd.Series | list[float]) -> np.ndarray:
    """Coerce ``value`` to a 1-D float NumPy array."""
    arr = np.asarray(value, dtype=float)
    return np.atleast_1d(arr).ravel()


def euclidean_distance(
    a: np.ndarray | pd.Series | list[float],
    b: np.ndarray | pd.Series | list[float],
) -> float:
    """Return the Euclidean (L2) distance between two vectors."""
    a_arr = _to_vector(a)
    b_arr = _to_vector(b)
    return float(np.linalg.norm(a_arr - b_arr))


def weighted_euclidean_distance(
    a: np.ndarray | pd.Series | list[float],
    b: np.ndarray | pd.Series | list[float],
    weights: np.ndarray | list[float] | None = None,
) -> float:
    """Return the weighted Euclidean distance between two vectors.

    Weights are normalised to sum to 1 so that the absolute scale of the
    provided weights does not affect the distance magnitude.
    """
    a_arr = _to_vector(a)
    b_arr = _to_vector(b)
    if weights is None:
        weights = np.ones_like(a_arr, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if weights.shape != a_arr.shape:
        raise ValueError("weights must have the same shape as the input vectors")
    weights = weights / (np.sum(weights) + 1e-12)
    return float(np.sqrt(np.sum(weights * (a_arr - b_arr) ** 2)))


def cosine_distance(
    a: np.ndarray | pd.Series | list[float],
    b: np.ndarray | pd.Series | list[float],
) -> float:
    """Return the cosine distance (1 - cosine similarity) between two vectors.

    A distance of 0 means the vectors point in the same direction; 2 means they
    point in opposite directions. Zero vectors are handled gracefully.
    """
    a_arr = _to_vector(a)
    b_arr = _to_vector(b)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0 if np.allclose(a_arr, b_arr) else 1.0
    similarity = float(np.dot(a_arr, b_arr) / (norm_a * norm_b))
    similarity = max(-1.0, min(1.0, similarity))
    return 1.0 - similarity


# ---------------------------------------------------------------------------
# Convenience dispatcher
# ---------------------------------------------------------------------------

_DISTANCE_FUNCTIONS = {
    "euclidean": euclidean_distance,
    "weighted_euclidean": weighted_euclidean_distance,
    "cosine": cosine_distance,
}


def compute_distance(
    a: np.ndarray | pd.Series | list[float],
    b: np.ndarray | pd.Series | list[float],
    metric: str = "euclidean",
    **kwargs: Any,
) -> float:
    """Dispatch to the requested distance metric.

    Args:
        a: First vector.
        b: Second vector.
        metric: One of ``euclidean``, ``weighted_euclidean`` or ``cosine``.
        **kwargs: Extra arguments forwarded to the metric, e.g. ``weights``.

    Raises:
        ValueError: If ``metric`` is not supported.
    """
    func = _DISTANCE_FUNCTIONS.get(metric)
    if func is None:
        raise ValueError(f"Unsupported metric: {metric}")
    return func(a, b, **kwargs)
