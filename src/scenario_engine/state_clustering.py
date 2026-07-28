"""K-Means clustering of historical market-state vectors.

Clustering turns the continuous state space into a small set of reusable
historical regimes. Each cluster centre can be inspected and, where possible,
given an interpretable market-state name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.scenario_engine.normalization import min_max_scale, robust_scale, z_score
from src.scenario_engine.state_vector import get_state_columns

try:
    from sklearn.cluster import KMeans  # type: ignore[import]
    from sklearn.metrics import silhouette_score  # type: ignore[import]

    _SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    _SKLEARN_AVAILABLE = False


_NORMALIZERS = {
    "z_score": z_score,
    "min_max": min_max_scale,
    "robust": robust_scale,
}


def cluster_states(
    df: pd.DataFrame,
    state_columns: list[str] | None = None,
    n_clusters: int = 5,
    normalizer: str = "z_score",
    random_state: int = 42,
) -> dict[str, Any]:
    """Cluster historical state vectors using K-Means.

    Args:
        df: DataFrame containing state-vector columns.
        state_columns: Ordered list of state-vector columns. Defaults to the
            schema-defined fields.
        n_clusters: Number of clusters (regimes) to discover.
        normalizer: One of ``z_score``, ``min_max`` or ``robust``.
        random_state: Random seed for reproducibility.

    Returns:
        A dictionary with cluster labels, centres, sizes, inertia and silhouette
        score. The returned labels are aligned to the original ``df`` index.

    Raises:
        RuntimeError: If scikit-learn is not installed.
    """
    if not _SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn is required for state clustering")

    state_columns = state_columns or get_state_columns()
    raw_states = df[state_columns].to_numpy(dtype=float)
    valid_mask = ~np.isnan(raw_states).any(axis=1)
    valid_indices = np.where(valid_mask)[0]
    valid_states = raw_states[valid_mask]

    if len(valid_states) < n_clusters:
        raise ValueError(
            f"Not enough valid state vectors ({len(valid_states)}) for "
            f"n_clusters={n_clusters}"
        )

    func = _NORMALIZERS.get(normalizer)
    if func is None:
        raise ValueError(f"Unsupported normalizer: {normalizer}")

    scaled = func(valid_states)

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")
    labels = kmeans.fit_predict(scaled)

    full_labels = np.full(len(df), -1, dtype=int)
    full_labels[valid_indices] = labels

    counts = {int(c): int((labels == c).sum()) for c in range(n_clusters)}

    silhouette: float | None = None
    if n_clusters > 1 and len(set(labels)) > 1:
        silhouette = float(silhouette_score(scaled, labels))

    return {
        "n_clusters": int(n_clusters),
        "labels": full_labels.tolist(),
        "valid_indices": valid_indices.tolist(),
        "centers": kmeans.cluster_centers_.tolist(),
        "cluster_sizes": counts,
        "inertia": float(kmeans.inertia_),
        "silhouette_score": silhouette,
        "feature_names": state_columns,
    }


def save_cluster_report(
    result: dict[str, Any],
    output_path: str | Path,
    sub_index_name: str | None = None,
    period: str | None = None,
) -> Path:
    """Persist a clustering result to JSON.

    Args:
        result: Output from ``cluster_states``.
        output_path: Destination file path.
        sub_index_name: Optional sub-index name for metadata.
        period: Optional K-line period for metadata.

    Returns:
        The written ``Path``.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "sub_index_name": sub_index_name,
        "period": period,
        **result,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    return output_path
