"""Generate the Phase 14 cold-generation performance report.

Benchmarks ``generate_scenarios`` under two configurations by spawning fresh
Python processes for each measurement, so module-level caches (schema, templates)
start cold and the reported latency reflects the true cold-generation path.

* ``baseline``: sequential multi-period processing without precomputed state
  vectors.
* ``optimized``: parallel multi-period processing with a single precomputed
  state vector per period and shared template feature computation.

The report is written to ``reports/phase14_performance.json``.
"""

from __future__ import annotations

import json
import pickle
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import Settings
from src.data.cache import cache_file_path, load


# Benchmark parameters.
TIMED_RUNS = 3
MIN_BARS = 200


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


def _synthetic_ohlc(n: int = 300) -> pd.DataFrame:
    """Generate deterministic synthetic OHLC data for fallback benchmarking."""
    rng = np.random.default_rng(42)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
    return df


def _multi_timeframe_input(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build a representative multi-timeframe input from a daily DataFrame.

    The cold-generation path is typically invoked with at least daily, 4-hour
    and 1-hour bars, so the benchmark uses the same shape to measure the
    benefit of parallel period processing and shared state-vector computation.
    """
    df = df.iloc[-MIN_BARS:].copy().reset_index(drop=True)
    df_4h = df.iloc[::4].copy().reset_index(drop=True)
    df_1h = df.copy().reset_index(drop=True)
    return {"1day": df, "4hour": df_4h, "1hour": df_1h}


def _run_subprocess(data_path: str, enable_parallel: bool, precompute_state: bool) -> float:
    """Spawn a fresh process, run one generation, and return elapsed seconds.

    A fresh interpreter guarantees cold module-level caches, which is what
    production cold generation looks like after a service restart.
    """
    script = f"""
import pickle
import time
import pandas as pd
from src.scenario_engine.scenario_generator import generate_scenarios

with open({data_path!r}, "rb") as f:
    df_by_period = pickle.load(f)

start = time.perf_counter()
generate_scenarios(
    df_by_period,
    enable_parallel={enable_parallel!r},
    precompute_state={precompute_state!r},
)
elapsed = time.perf_counter() - start
print(f"{{elapsed:.6f}}")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip().splitlines()[-1])


def _benchmark_configuration(
    df_by_period: dict[str, pd.DataFrame],
    *,
    enable_parallel: bool,
    precompute_state: bool,
    timed_runs: int,
) -> dict[str, Any]:
    """Run timed generation in fresh processes and return latency statistics."""
    work_dir = Path(__file__).parent / ".perf_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    data_path = work_dir / "df_by_period.pkl"
    with data_path.open("wb") as f:
        pickle_protocol = min(5, pickle.HIGHEST_PROTOCOL)
        pickle.dump(df_by_period, f, protocol=pickle_protocol)

    latencies: list[float] = []
    for _ in range(timed_runs):
        latencies.append(
            _run_subprocess(
                str(data_path),
                enable_parallel=enable_parallel,
                precompute_state=precompute_state,
            )
        )

    return {
        "mean_seconds": round(float(np.mean(latencies)), 6),
        "std_seconds": round(float(np.std(latencies)), 6),
        "min_seconds": round(float(np.min(latencies)), 6),
        "max_seconds": round(float(np.max(latencies)), 6),
        "runs": timed_runs,
        "enable_parallel": enable_parallel,
        "precompute_state": precompute_state,
    }


def _evaluate_sub_index(sub_index: str, settings: Settings) -> dict[str, Any]:
    """Benchmark a single sub-index under baseline and optimized configs."""
    df = _load_daily_df(sub_index, settings)
    if df is None:
        df = _synthetic_ohlc()
    if len(df) < MIN_BARS:
        df = _synthetic_ohlc(MIN_BARS)

    df_by_period = _multi_timeframe_input(df)
    bars = sum(len(d) for d in df_by_period.values())

    baseline = _benchmark_configuration(
        df_by_period,
        enable_parallel=False,
        precompute_state=False,
        timed_runs=TIMED_RUNS,
    )
    optimized = _benchmark_configuration(
        df_by_period,
        enable_parallel=True,
        precompute_state=True,
        timed_runs=TIMED_RUNS,
    )

    improvement = 0.0
    if baseline["mean_seconds"] > 0:
        improvement = round(
            (baseline["mean_seconds"] - optimized["mean_seconds"])
            / baseline["mean_seconds"]
            * 100,
            2,
        )

    return {
        "sub_index": sub_index,
        "total_bars": bars,
        "baseline": baseline,
        "optimized": optimized,
        "improvement_percent": improvement,
    }


def main() -> None:
    """Run the Phase 14 performance benchmark and write the JSON report."""
    settings = Settings()
    sub_indices = _discover_sub_indices(settings)

    per_sub_index: dict[str, dict[str, Any]] = {}
    for sub_index in sub_indices:
        per_sub_index[sub_index] = _evaluate_sub_index(sub_index, settings)

    baseline_mean = np.mean(
        [r["baseline"]["mean_seconds"] for r in per_sub_index.values()]
    )
    optimized_mean = np.mean(
        [r["optimized"]["mean_seconds"] for r in per_sub_index.values()]
    )
    improvement = 0.0
    if baseline_mean > 0:
        improvement = float((baseline_mean - optimized_mean) / baseline_mean * 100)

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sub_indices": sub_indices,
        "benchmark_params": {
            "timed_runs": TIMED_RUNS,
            "min_bars": MIN_BARS,
            "note": "Each measurement runs in a fresh Python process to capture cold-generation latency.",
        },
        "aggregate": {
            "baseline_mean_seconds": round(baseline_mean, 6),
            "optimized_mean_seconds": round(optimized_mean, 6),
            "improvement_percent": round(improvement, 2),
        },
        "per_sub_index": per_sub_index,
    }

    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / "phase14_performance.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Phase 14 performance report written to {output_path}")
    print(
        f"Aggregate: baseline={report['aggregate']['baseline_mean_seconds']:.3f}s, "
        f"optimized={report['aggregate']['optimized_mean_seconds']:.3f}s, "
        f"improvement={report['aggregate']['improvement_percent']:.1f}%"
    )


if __name__ == "__main__":
    main()
