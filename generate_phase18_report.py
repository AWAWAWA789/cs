"""生成 Phase 18 情景质量验证报告。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import Settings
from src.data.cache import cache_file_path, load
from src.scenario_engine.scenario_generator import generate_scenarios


DEFAULT_OUTPUT_PATH = Path("reports/phase18_scenario_quality_validation.json")


def _evaluate_scenario_quality(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """评估一次生成结果的概率质量与分布健康度。"""
    if not scenarios:
        return {
            "count": 0,
            "min_probability": 0.0,
            "max_probability": 0.0,
            "unique_directions": 0,
            "has_oligopoly": False,
            "passes_hard_floor": False,
        }

    probabilities = [s["probability"] for s in scenarios]
    directions = {s["direction"] for s in scenarios}
    max_prob = max(probabilities)
    min_prob = min(probabilities)

    return {
        "count": len(scenarios),
        "min_probability": round(min_prob, 6),
        "max_probability": round(max_prob, 6),
        "unique_directions": len(directions),
        "has_oligopoly": max_prob > 0.95,
        "passes_hard_floor": min_prob >= 0.05,
    }


def _discover_sub_indices(settings: Settings) -> list[str]:
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
    path = cache_file_path(sub_index, "1day", settings.cache_path)
    df = load(path)
    if df is None or df.empty:
        return None
    return df.reset_index(drop=True)


def build_phase18_report(
    df_by_sub_index: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """为每个子指数生成情景并评估质量。"""
    if df_by_sub_index is None:
        settings = Settings()
        sub_indices = _discover_sub_indices(settings)
        df_by_sub_index = {}
        for sub_index in sub_indices:
            df = _load_daily_df(sub_index, settings)
            if df is not None:
                df_by_sub_index[sub_index] = df

    per_sub_index: dict[str, Any] = {}
    total_count = 0
    oligopoly_count = 0
    pass_count = 0

    for sub_index, df in df_by_sub_index.items():
        result = generate_scenarios({"1day": df})
        scenarios = result["scenarios"]
        quality = _evaluate_scenario_quality(scenarios)
        per_sub_index[sub_index] = {
            "sub_index": sub_index,
            "bar_count": len(df),
            "scenarios": scenarios,
            "quality": quality,
        }
        total_count += 1
        if quality["has_oligopoly"]:
            oligopoly_count += 1
        if (
            2 <= quality["count"] <= 4
            and quality["passes_hard_floor"]
            and not quality["has_oligopoly"]
        ):
            pass_count += 1

    summary = {
        "sub_index_count": len(per_sub_index),
        "average_scenario_count": round(
            sum(
                entry["quality"]["count"]
                for entry in per_sub_index.values()
            )
            / len(per_sub_index),
            2,
        )
        if per_sub_index
        else 0.0,
        "oligopoly_count": oligopoly_count,
        "quality_pass_count": pass_count,
        "quality_pass_ratio": round(pass_count / total_count, 4) if total_count else 0.0,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "per_sub_index": per_sub_index,
        "summary": summary,
    }


def save_phase18_report(
    report: dict[str, Any],
    path: Path | str | None = None,
) -> Path:
    output_path = Path(path or DEFAULT_OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    return output_path


def main() -> None:
    report = build_phase18_report()
    save_phase18_report(report)
    print(f"Phase 18 report saved to {DEFAULT_OUTPUT_PATH}")
    summary = report["summary"]
    print(
        f"Quality pass: {summary['quality_pass_count']}/{summary['sub_index_count']} "
        f"({summary['quality_pass_ratio']*100:.2f}%)"
    )


if __name__ == "__main__":
    main()
