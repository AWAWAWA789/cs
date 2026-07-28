"""Dynamic Time Warping (DTW) search for price-shape similarity.

DTW aligns two price series elastically, making the search robust to small
(1-3 bar) temporal offsets that would confuse ordinary Euclidean matching.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.scenario_engine.normalization import z_score

try:
    from fastdtw import fastdtw  # type: ignore[import]

    _FASTDTW_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    _FASTDTW_AVAILABLE = False

try:
    from scipy.spatial.distance import cdist  # type: ignore[import]

    _SCIPY_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    _SCIPY_AVAILABLE = False


def _normalize_series(series: np.ndarray) -> np.ndarray:
    """Z-Score normalise a 1-D price series to focus on shape."""
    arr = np.asarray(series, dtype=float).ravel()
    return np.asarray(z_score(arr))


def _native_dtw_distance(
    a: np.ndarray,
    b: np.ndarray,
    radius: int = 3,
) -> float:
    """A pure NumPy DTW implementation with a Sakoe-Chiba band.

    The band width ``radius`` restricts how far the alignment path can stray
    from the diagonal, giving robustness to small offsets without excessive
    computation.
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    n, m = len(a), len(b)
    inf = float("inf")
    # Use a 2-D cost matrix; band enforcement is done during filling.
    cost = np.full((n + 1, m + 1), inf)
    cost[0, 0] = 0.0

    for i in range(1, n + 1):
        j_min = max(1, i - radius)
        j_max = min(m, i + radius)
        for j in range(j_min, j_max + 1):
            dist = abs(a[i - 1] - b[j - 1])
            cost[i, j] = dist + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])

    return float(cost[n, m])


def dtw_distance(
    query: np.ndarray | pd.Series,
    candidate: np.ndarray | pd.Series,
    radius: int = 3,
) -> float:
    """Return the DTW distance between two price series.

    If ``fastdtw`` is installed it is used for speed; otherwise a native
    band-constrained DTW implementation is used.

    Args:
        query: Query price series.
        candidate: Candidate price series.
        radius: Sakoe-Chiba band radius (1-3 bars by default).

    Returns:
        Non-negative DTW distance. Lower means more similar shape.
    """
    q = _normalize_series(np.asarray(query, dtype=float))
    c = _normalize_series(np.asarray(candidate, dtype=float))

    if _FASTDTW_AVAILABLE:
        distance, _ = fastdtw(q, c, radius=radius, dist=lambda x, y: abs(float(x) - float(y)))
        return float(distance)
    return _native_dtw_distance(q, c, radius=radius)


def dtw_search(
    df: pd.DataFrame,
    query_index: int | None = None,
    window: int = 20,
    n_neighbors: int = 10,
    radius: int = 3,
    step: int = 1,
) -> list[dict[str, Any]]:
    """Find historical price windows most similar in shape to the query window.

    Args:
        df: DataFrame containing ``close`` and optionally ``timestamp``.
        query_index: End index of the query window (inclusive). Defaults to the
            last row, so the query window is ``df[-window:]``.
        window: Length of the price window in bars.
        n_neighbors: Number of candidate windows to return.
        radius: DTW band radius; 1-3 bars gives shape robustness.
        step: Step size between candidate windows. Use 1 for exhaustive search.

    Returns:
        A list of dictionaries sorted by ascending DTW distance. Each entry
        contains the candidate window indices, timestamps and forward returns.
    """
    if query_index is None:
        query_index = len(df) - 1

    if not window - 1 <= query_index < len(df):
        raise ValueError("query_index out of bounds for the requested window")

    close = df["close"].to_numpy(dtype=float)
    query_start = query_index - window + 1
    query_series = close[query_start : query_index + 1]

    max_future = 7
    last_valid_start = len(df) - window - max_future
    if last_valid_start < 0:
        return []

    candidates = []
    for start in range(0, last_valid_start + 1, step):
        end = start + window - 1
        if end >= query_start and start <= query_index:
            # Exclude overlapping windows to avoid trivial matches.
            continue
        candidate = close[start : end + 1]
        distance = dtw_distance(query_series, candidate, radius=radius)
        candidates.append((distance, start, end))

    if not candidates:
        return []

    candidates.sort(key=lambda x: x[0])
    top = candidates[:n_neighbors]

    ts_col = "timestamp" if "timestamp" in df.columns else None
    results = []
    for distance, start, end in top:
        entry: dict[str, Any] = {
            "query_index": int(query_index),
            "query_start": int(query_start),
            "candidate_start": int(start),
            "candidate_end": int(end),
            "distance": float(distance),
        }
        if ts_col:
            entry["query_timestamp"] = str(df[ts_col].iloc[query_index])
            entry["candidate_start_timestamp"] = str(df[ts_col].iloc[start])
            entry["candidate_end_timestamp"] = str(df[ts_col].iloc[end])

        # Forward returns from the *end* of the candidate window.
        entry["future_return_5"] = (
            (float(close[end + 5]) - float(close[end])) / float(close[end])
            if end + 5 < len(close)
            else None)
        entry["future_return_7"] = (
            (float(close[end + 7]) - float(close[end])) / float(close[end])
            if end + 7 < len(close)
            else None)
        results.append(entry)
    return results
