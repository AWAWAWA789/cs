"""Generate the Phase 14 walk-forward direction accuracy report.

Rolls through historical daily bars for each discovered sub-index, generates
scenarios at fixed intervals, takes the highest-probability scenario direction,
and compares it with the realised 5- and 7-bar direction. Outputs a JSON report
with per-sub-index and aggregate accuracy.
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
from src.scenario_engine.scenario_generator import generate_scenarios


# Walk-forward parameters.
MIN_BARS = 200
STEP_BARS = 20
HORIZONS = (5, 7)


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


def _load_daily_df(sub_index: str, settings: Settings) -> pd.DataFrame | None:
    """Load cached daily OHLC data for a sub-index."""
    path = cache_file_path(sub_index, "1day", settings.cache_path)
    df = load(path)
    if df is None or df.empty:
        return None
    return df.reset_index(drop=True)


def _realised_direction(close_series: pd.Series, idx: int, horizon: int) -> int:
    """Return +1/-1/0 for the future ``horizon`` bar price change from ``idx``."""
    if idx + horizon >= len(close_series):
        return 0
    change = float(close_series.iloc[idx + horizon]) - float(close_series.iloc[idx])
    if change > 0:
        return 1
    if change < 0:
        return -1
    return 0


def _evaluate_sub_index(sub_index: str, settings: Settings) -> dict[str, Any]:
    """Run the walk-forward direction accuracy evaluation for one sub-index."""
    df = _load_daily_df(sub_index, settings)
    if df is None:
        raise RuntimeError(f"No daily cache found for {sub_index}")

    close = df["close"]
    max_horizon = max(HORIZONS)
    end_idx = len(df) - max_horizon
    if end_idx <= MIN_BARS:
        raise RuntimeError(f"Insufficient bars for {sub_index}: {len(df)}")

    records: list[dict[str, Any]] = []
    start_time = time.perf_counter()

    for idx in range(MIN_BARS, end_idx, STEP_BARS):
        sliced = df.iloc[: idx + 1].copy().reset_index(drop=True)
        result = generate_scenarios({"1day": sliced})
        scenarios = result.get("scenarios", [])
        if not scenarios:
            continue

        top = max(scenarios, key=lambda s: s.get("probability", 0.0))
        predicted_dir = int(top.get("direction", 0))
        probability = float(top.get("probability", 0.0))

        row: dict[str, Any] = {
            "index": idx,
            "timestamp": str(sliced["timestamp"].iloc[-1]) if "timestamp" in sliced.columns else None,
            "current_close": round(float(sliced["close"].iloc[-1]), 6),
            "predicted_direction": predicted_dir,
            "predicted_scenario": top.get("scenario_key", "unknown"),
            "probability": round(probability, 6),
        }

        for horizon in HORIZONS:
            actual_dir = _realised_direction(close, idx, horizon)
            row[f"actual_direction_{horizon}"] = actual_dir
            # Neutral predictions are excluded from hit/miss counts.
            if predicted_dir == 0:
                row[f"hit_{horizon}"] = None
            else:
                row[f"hit_{horizon}"] = predicted_dir == actual_dir

        records.append(row)

    elapsed = round(time.perf_counter() - start_time, 4)

    summary: dict[str, Any] = {
        "total_samples": len(records),
        "evaluation_time_seconds": elapsed,
    }
    for horizon in HORIZONS:
        hits = sum(1 for r in records if r[f"hit_{horizon}"] is True)
        valid = sum(1 for r in records if r[f"hit_{horizon}"] is not None)
        accuracy = round(hits / valid, 6) if valid > 0 else 0.0
        summary[f"horizon_{horizon}"] = {
            "hits": hits,
            "valid_predictions": valid,
            "accuracy": accuracy,
        }

    return {
        "summary": summary,
        "samples": records,
    }


def main() -> None:
    """Run walk-forward direction accuracy across all discovered sub-indices."""
    os.environ.setdefault("CSQAQ_API_TOKEN", "dummy")
    settings = Settings()

    sub_indices = _discover_sub_indices(settings)
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    per_sub_index: dict[str, dict[str, Any]] = {}
    for sub_index in sub_indices:
        print(f"Evaluating direction accuracy for {sub_index} ...")
        per_sub_index[sub_index] = _evaluate_sub_index(sub_index, settings)

    aggregate: dict[str, Any] = {}
    for horizon in HORIZONS:
        total_hits = sum(
            info["summary"][f"horizon_{horizon}"]["hits"]
            for info in per_sub_index.values()
        )
        total_valid = sum(
            info["summary"][f"horizon_{horizon}"]["valid_predictions"]
            for info in per_sub_index.values()
        )
        aggregate[f"horizon_{horizon}"] = {
            "total_hits": total_hits,
            "total_valid_predictions": total_valid,
            "mean_accuracy": round(total_hits / total_valid, 6) if total_valid > 0 else 0.0,
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_indices": sub_indices,
        "horizons": list(HORIZONS),
        "walk_forward_params": {
            "min_bars": MIN_BARS,
            "step_bars": STEP_BARS,
        },
        "aggregate": aggregate,
        "per_sub_index": per_sub_index,
    }

    output_path = report_dir / "phase14_direction_accuracy.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"Phase 14 direction accuracy report saved to: {output_path}")


if __name__ == "__main__":
    main()
