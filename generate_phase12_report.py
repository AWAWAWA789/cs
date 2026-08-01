"""Generate the Phase 12 fusion and calibration validation report.

Runs the full dual-track fusion + Bayesian calibration + multi-timeframe fusion
pipeline on the four configured sub-indices and writes a JSON report.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import Settings
from src.data.cache import cache_file_path, load
from src.scenario_engine.bayesian_calibration import evaluate_calibration
from src.scenario_engine.index_builder import build_or_update_index, query_similar_states
from src.scenario_engine.scenario_generator import generate_scenarios
from src.scenario_engine.state_vector import get_state_columns
from src.scenario_engine.template_matcher import match_templates


PERIODS = ["1day", "4hour", "1hour"]


def _discover_sub_indices(settings: Settings) -> list[str]:
    """Discover sub-index names from the 1-day cache directory.

    Falls back to the four canonical indices if no cache files are found.
    """
    cache_dir = Path(settings.cache_path)
    discovered: set[str] = set()
    if cache_dir.exists():
        for path in cache_dir.glob("*_1d.parquet"):
            name = path.stem.rsplit("_", 1)[0]
            if name:
                discovered.add(name)
    if discovered:
        return sorted(discovered)
    return ["手套", "匕首", "百元主战", "贴纸"]


def _load_period_df(
    sub_index_name: str,
    period: str,
    settings: Settings,
) -> pd.DataFrame | None:
    """Load cached OHLC data for a sub-index / period pair."""
    path = cache_file_path(sub_index_name, period, settings.cache_path)
    df = load(path)
    if df is not None and not df.empty:
        return df
    return None


def _resample_from_daily(
    daily_df: pd.DataFrame,
    period: str,
) -> pd.DataFrame:
    """Fall back to resampling daily data when a shorter period is missing."""
    freq = {"1hour": "h", "4hour": "4h", "1day": "D"}.get(period, "D")
    daily_df = daily_df.copy()
    daily_df["timestamp"] = pd.to_datetime(daily_df["timestamp"], utc=True)
    daily_df = daily_df.set_index("timestamp")
    resampled = daily_df.resample(freq).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }
    ).dropna()
    resampled = resampled.reset_index()
    return resampled[["timestamp", "open", "high", "low", "close"]]


def _build_df_by_period(
    sub_index_name: str,
    settings: Settings,
) -> dict[str, pd.DataFrame]:
    """Build a period -> DataFrame mapping, falling back to resampling."""
    daily_df = _load_period_df(sub_index_name, "1day", settings)
    if daily_df is None:
        raise RuntimeError(f"No daily cache found for {sub_index_name}")

    result: dict[str, pd.DataFrame] = {}
    for period in PERIODS:
        df = _load_period_df(sub_index_name, period, settings)
        if df is None:
            df = _resample_from_daily(daily_df, period)
        result[period] = df
    return result


def _compute_brier_for_period(
    per_period: dict[str, Any],
    similarity_results: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute Brier score per period from calibrated candidates."""
    brier_by_period: dict[str, float] = {}
    for period, info in per_period.items():
        candidates = info.get("candidates", [])
        metrics = evaluate_calibration(candidates, similarity_results)
        brier_by_period[period] = metrics["brier_score"]
    return brier_by_period


def _run_sub_index(
    sub_index_name: str,
    settings: Settings,
) -> dict[str, Any]:
    """Run the full Phase 12 pipeline for one sub-index."""
    print(f"Processing {sub_index_name} ...")
    df_by_period = _build_df_by_period(sub_index_name, settings)

    # Build or update pre-computed state index for each period.
    index_paths: dict[str, str] = {}
    for period, df in df_by_period.items():
        path = build_or_update_index(
            df,
            sub_index_name,
            period,
            base_dir="data/scenario_index",
        )
        index_paths[period] = str(path)

    # Pre-fetch similarity results from the pre-computed index.
    state_columns = get_state_columns()
    similarity_results_by_period: dict[str, list[dict[str, Any]]] = {}
    template_results_by_period: dict[str, list[dict[str, Any]]] = {}
    for period, df in df_by_period.items():
        query_state = {
            c: float(df[c].iloc[-1])
            for c in state_columns
            if c in df.columns
        }
        similarity_results_by_period[period] = query_similar_states(
            index_paths[period],
            query_state,
            state_columns=state_columns,
            n_neighbors=10,
        )
        template_results_by_period[period] = match_templates(df, min_confidence=0.5)

    # Measure inference latency using pre-computed similarity/template results.
    start = time.perf_counter()
    result = generate_scenarios(
        df_by_period,
        similarity_results_by_period=similarity_results_by_period,
        template_results_by_period=template_results_by_period,
    )
    inference_latency = round(time.perf_counter() - start, 4)

    scenarios = result["scenarios"]
    per_period = result["per_period"]

    # Approximate Brier using the daily similarity results.
    daily_similarity_count = per_period["1day"]["similarity_count"]
    brier_by_period = _compute_brier_for_period(
        per_period,
        similarity_results_by_period["1day"],
    )

    return {
        "bars": {p: len(df) for p, df in df_by_period.items()},
        "index_paths": index_paths,
        "inference_latency_seconds": inference_latency,
        "scenarios": scenarios,
        "brier_by_period": brier_by_period,
        "mean_brier": round(sum(brier_by_period.values()) / len(brier_by_period), 6),
        "multi_timeframe_candidate_count": len(result["multi_timeframe_candidates"]),
        "daily_similarity_count": daily_similarity_count,
    }


def main() -> None:
    os.environ.setdefault("CSQAQ_API_TOKEN", "dummy")
    settings = Settings()

    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    sub_indices = _discover_sub_indices(settings)
    per_subindex: dict[str, dict[str, Any]] = {}
    for sub_index_name in sub_indices:
        per_subindex[sub_index_name] = _run_sub_index(sub_index_name, settings)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_indices": sub_indices,
        "periods": PERIODS,
        "per_sub_index": per_subindex,
    }

    output_path = report_dir / "phase12_fusion_validation.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"Phase 12 fusion validation report saved to: {output_path}")


if __name__ == "__main__":
    main()
