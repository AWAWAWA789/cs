"""Generate the Phase 10 historical-similarity validation report.

Runs KNN, DTW and K-Means on each configured sub-index using cached OHLC data
and writes a JSON report plus per-sub-index clustering reports.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.api.client import CSQAQClient
from src.config import Settings
from src.data.pipeline import load_or_fetch
from src.scenario_engine.similarity_search import find_similar_states
from src.scenario_engine.state_clustering import save_cluster_report


SUB_INDICES = ["手套", "匕首", "百元主战", "贴纸"]
PERIOD = "1day"
N_NEIGHBORS = 10
N_CLUSTERS = 5


def _load_data(settings: Settings, client: CSQAQClient, sub_index_name: str) -> dict:
    """Load cached OHLC data for a sub-index and return a metadata dict."""
    df = load_or_fetch(
        settings,
        client,
        sub_index_name=sub_index_name,
        sub_index_id="dummy",
        period=PERIOD,
    )
    return {
        "df": df,
        "bars": int(len(df)),
        "start": str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else None,
        "end": str(df["timestamp"].iloc[-1]) if "timestamp" in df.columns else None,
    }


def main() -> None:
    os.environ.setdefault("CSQAQ_API_TOKEN", "dummy")
    settings = Settings()
    client = CSQAQClient(settings)

    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    per_subindex: dict[str, dict] = {}

    for sub_index_name in SUB_INDICES:
        print(f"Processing {sub_index_name} ...")
        meta = _load_data(settings, client, sub_index_name)
        df = meta["df"]

        knn_results = find_similar_states(df, method="knn", n_neighbors=N_NEIGHBORS)
        dtw_results = find_similar_states(
            df, method="dtw", n_neighbors=N_NEIGHBORS, window=20, radius=3
        )
        cluster_result = find_similar_states(
            df, method="cluster", n_neighbors=N_CLUSTERS
        )

        cluster_report_path = report_dir / f"phase10_clustering_{sub_index_name}_1d.json"
        save_cluster_report(
            cluster_result,
            cluster_report_path,
            sub_index_name=sub_index_name,
            period=PERIOD,
        )

        per_subindex[sub_index_name] = {
            "bars": meta["bars"],
            "start": meta["start"],
            "end": meta["end"],
            "knn": {
                "query_index": knn_results[0]["query_index"] if knn_results else None,
                "query_timestamp": knn_results[0].get("query_timestamp") if knn_results else None,
                "neighbors": knn_results,
            },
            "dtw": {
                "query_index": dtw_results[0]["query_index"] if dtw_results else None,
                "query_timestamp": dtw_results[0].get("query_timestamp") if dtw_results else None,
                "matches": dtw_results,
            },
            "cluster": {
                "n_clusters": cluster_result["n_clusters"],
                "cluster_sizes": cluster_result["cluster_sizes"],
                "inertia": cluster_result["inertia"],
                "silhouette_score": cluster_result["silhouette_score"],
                "feature_names": cluster_result["feature_names"],
                "centers": cluster_result["centers"],
                "report_path": str(cluster_report_path),
            },
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": PERIOD,
        "n_neighbors": N_NEIGHBORS,
        "n_clusters": N_CLUSTERS,
        "sub_indices": SUB_INDICES,
        "results": per_subindex,
    }

    output_path = report_dir / "phase10_similarity_search_validation.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"Validation report saved to: {output_path}")


if __name__ == "__main__":
    main()
