"""Unified entry point for historical similarity search.

This module wires together the state-vector builder, KNN search, DTW shape
search and K-Means clustering behind a single function so that downstream
components do not need to know which algorithm is being used.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.scenario_engine.dtw_search import dtw_search
from src.scenario_engine.knn_search import knn_search
from src.scenario_engine.state_clustering import cluster_states
from src.scenario_engine.state_vector import compute_state_vector, get_state_columns


_SUPPORTED_METHODS = {"knn", "dtw", "cluster"}


def find_similar_states(
    df: pd.DataFrame,
    method: str = "knn",
    n_neighbors: int = 10,
    state_columns: list[str] | None = None,
    state_df: pd.DataFrame | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Find historically similar states or clusters for ``df``.

    Args:
        df: OHLC DataFrame. For ``knn`` and ``cluster`` it is enriched with the
            full state vector before searching. For ``dtw`` only the ``close``
            series is used.
        method: ``knn`` for state-vector nearest neighbours, ``dtw`` for
            shape-aligned price series search, or ``cluster`` for K-Means
            regime clustering.
        n_neighbors: Number of neighbours (``knn`` / ``dtw``) or default
            clusters when ``method == 'cluster'`` and ``n_clusters`` is not
            provided.
        state_columns: Optional ordered list of state-vector columns.
        state_df: 可选的预计算状态向量 DataFrame。若提供，则直接使用，避免
            在冷生成路径中重复计算状态向量。
        **kwargs: Extra arguments forwarded to the underlying search function.

    Returns:
        - ``knn`` / ``dtw``: a list of result dictionaries sorted by distance.
        - ``cluster``: a dictionary with labels, cluster centres and sizes.

    Raises:
        ValueError: If ``method`` is not supported.
    """
    method = method.lower()
    if method not in _SUPPORTED_METHODS:
        raise ValueError(f"method must be one of {_SUPPORTED_METHODS}, got {method}")

    state_columns = state_columns or get_state_columns()

    if method == "knn":
        if state_df is None:
            state_df = compute_state_vector(df, state_columns=state_columns)
        return knn_search(
            state_df,
            state_columns=state_columns,
            n_neighbors=n_neighbors,
            **kwargs,
        )

    if method == "dtw":
        return dtw_search(df, n_neighbors=n_neighbors, **kwargs)

    # method == "cluster"
    if state_df is None:
        state_df = compute_state_vector(df, state_columns=state_columns)
    cluster_kwargs = {k: v for k, v in kwargs.items() if k != "n_clusters"}
    n_clusters = kwargs.get("n_clusters", n_neighbors)
    return cluster_states(
        state_df,
        state_columns=state_columns,
        n_clusters=int(n_clusters),
        **cluster_kwargs,
    )
