"""K-Nearest-Neighbour search over historical state vectors.

The module prefers Faiss for speed, falls back to scikit-learn, and finally to
a vectorised brute-force implementation so that the same interface works in all
environments.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.scenario_engine.normalization import min_max_scale, robust_scale, z_score
from src.scenario_engine.state_vector import get_state_columns, get_state_weights

try:
    import faiss  # type: ignore[import]

    _FAISS_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    _FAISS_AVAILABLE = False

try:
    from sklearn.neighbors import NearestNeighbors  # type: ignore[import]

    _SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    _SKLEARN_AVAILABLE = False


_NORMALIZERS = {
    "z_score": z_score,
    "min_max": min_max_scale,
    "robust": robust_scale,
}


def _scale_data(
    train: np.ndarray,
    query: np.ndarray,
    normalizer: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit a normalizer on ``train`` and apply it to both ``train`` and ``query``."""
    func = _NORMALIZERS.get(normalizer)
    if func is None:
        raise ValueError(f"Unsupported normalizer: {normalizer}")

    # Fit on training matrix; transform query with the same parameters.
    train_scaled = func(train)
    # Manual scaling for query to reuse fitted parameters would require a scaler
    # object. To keep the API dependency-light we stack query, transform the
    # combined matrix, and split. This is safe for search because the query is
    # not used when fitting the normalizer.
    combined = np.vstack([train, query.reshape(1, -1)])
    combined_scaled = func(combined)
    return combined_scaled[:-1], combined_scaled[-1]


def _apply_weights(
    train: np.ndarray,
    query: np.ndarray,
    weights: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply feature weights so that a standard L2 search yields weighted distance."""
    if weights is None:
        return train, query
    weights = np.asarray(weights, dtype=float)
    weights = weights / (np.sum(weights) + 1e-12)
    w_sqrt = np.sqrt(weights)
    return train * w_sqrt, query * w_sqrt


def _compute_future_returns(
    df: pd.DataFrame,
    idx: int,
    future_bars: tuple[int, ...],
) -> dict[str, float | None]:
    """Return forward returns from ``idx`` for the requested bar counts."""
    close = df["close"].to_numpy()
    entry = float(close[idx])
    returns: dict[str, float | None] = {}
    for bars in future_bars:
        key = f"future_return_{bars}"
        if idx + bars < len(close):
            returns[key] = (float(close[idx + bars]) - entry) / entry
        else:
            returns[key] = None
    return returns


def _format_result(
    df: pd.DataFrame,
    query_index: int,
    neighbor_index: int,
    distance: float,
    state_columns: list[str],
) -> dict[str, Any]:
    """Build a single neighbour result dictionary."""
    row = df.iloc[neighbor_index]
    ts_col = "timestamp" if "timestamp" in df.columns else None
    result: dict[str, Any] = {
        "query_index": int(query_index),
        "neighbor_index": int(neighbor_index),
        "distance": float(distance),
        "state": {col: float(row[col]) for col in state_columns},
    }
    if ts_col:
        result["query_timestamp"] = str(df[ts_col].iloc[query_index])
        result["neighbor_timestamp"] = str(row[ts_col])
    result.update(_compute_future_returns(df, neighbor_index, (5, 7)))
    return result


def knn_search(
    df: pd.DataFrame,
    state_columns: list[str] | None = None,
    query_index: int | None = None,
    n_neighbors: int = 10,
    normalizer: str = "z_score",
    metric: str = "euclidean",
    weights: np.ndarray | list[float] | None = None,
) -> list[dict[str, Any]]:
    """Return the Top-N historical bars that are most similar to a query state.

    Args:
        df: DataFrame containing state-vector columns and ``close``.
        state_columns: Ordered list of state-vector columns. Defaults to the
            schema-defined fields.
        query_index: Index of the query bar. Defaults to the last row.
        n_neighbors: Number of neighbours to return.
        normalizer: One of ``z_score``, ``min_max`` or ``robust``.
        metric: ``euclidean`` or ``weighted_euclidean``. For weighted search
            ``weights`` are applied before L2 distance calculation.
        weights: Feature weights. Defaults to schema weights when
            ``metric == 'weighted_euclidean'``.

    Returns:
        A list of neighbour dictionaries, sorted by ascending distance. Each
        entry contains the neighbour index, distance, timestamps and forward
        5- and 7-bar returns.
    """
    state_columns = state_columns or get_state_columns()
    if query_index is None:
        query_index = len(df) - 1

    if not 0 <= query_index < len(df):
        raise ValueError("query_index out of bounds")

    raw_states = df[state_columns].to_numpy(dtype=float)
    valid_mask = ~np.isnan(raw_states).any(axis=1)

    # Exclude the query itself and rows without enough future bars.
    max_future = 7
    enough_history = np.arange(len(df)) <= len(df) - 1 - max_future
    candidate_mask = valid_mask & enough_history
    candidate_mask[query_index] = False

    candidate_indices = np.where(candidate_mask)[0]
    if len(candidate_indices) == 0:
        return []

    train = raw_states[candidate_indices]
    query = raw_states[query_index]

    train_scaled, query_scaled = _scale_data(train, query, normalizer)

    if metric == "weighted_euclidean" and weights is None:
        weights = get_state_weights()
    train_scaled, query_scaled = _apply_weights(train_scaled, query_scaled, weights)

    n_neighbors = min(n_neighbors, len(candidate_indices))

    train_f32 = np.ascontiguousarray(train_scaled, dtype=np.float32)
    query_f32 = np.ascontiguousarray(query_scaled.reshape(1, -1), dtype=np.float32)

    distances: np.ndarray
    indices: np.ndarray

    if _FAISS_AVAILABLE:
        index = faiss.IndexFlatL2(train_f32.shape[1])
        index.add(train_f32)
        distances_sq, indices_arr = index.search(query_f32, n_neighbors)
        distances = np.sqrt(distances_sq[0])
        indices = indices_arr[0]
    elif _SKLEARN_AVAILABLE:
        nn = NearestNeighbors(n_neighbors=n_neighbors, metric="euclidean")
        nn.fit(train_f32)
        distances, indices = nn.kneighbors(query_f32)
        distances = distances[0]
        indices = indices[0]
    else:
        diff = train_f32 - query_f32
        all_distances = np.sqrt(np.sum(diff * diff, axis=1))
        order = np.argsort(all_distances)[:n_neighbors]
        distances = all_distances[order]
        indices = order

    results = []
    for local_idx, dist in zip(indices, distances):
        global_idx = int(candidate_indices[local_idx])
        results.append(_format_result(df, query_index, global_idx, dist, state_columns))
    return results
