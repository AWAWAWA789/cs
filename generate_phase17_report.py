"""生成 Phase 17 跨子指数策略绩效与超额收益报告。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.performance import compare_strategy_vs_benchmark
from src.config import Settings
from src.data.cache import cache_file_path, load


DEFAULT_OUTPUT_DIR = Path("reports")
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "phase17_strategy_performance.json"


def _discover_sub_indices(settings: Settings) -> list[str]:
    """从日线缓存目录发现子指数名称。"""
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
    """加载缓存的日线 OHLC 数据。"""
    path = cache_file_path(sub_index, "1day", settings.cache_path)
    df = load(path)
    if df is None or df.empty:
        return None
    return df.reset_index(drop=True)


def build_phase17_report(
    df_by_sub_index: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """为每个子指数计算策略绩效、买入持有基准与超额收益。"""
    if df_by_sub_index is None:
        settings = Settings()
        sub_indices = _discover_sub_indices(settings)
        df_by_sub_index = {}
        for sub_index in sub_indices:
            df = _load_daily_df(sub_index, settings)
            if df is not None:
                df_by_sub_index[sub_index] = df

    per_sub_index: dict[str, Any] = {}
    beat_count = 0
    total_excess = 0.0

    for sub_index, df in df_by_sub_index.items():
        comparison = compare_strategy_vs_benchmark(df)
        per_sub_index[sub_index] = {
            "sub_index": sub_index,
            "bar_count": len(df),
            **comparison,
        }
        if comparison["beat_buy_and_hold"]:
            beat_count += 1
        total_excess += comparison["excess_return"]

    summary = {
        "sub_index_count": len(per_sub_index),
        "beat_buy_and_hold_count": beat_count,
        "beat_buy_and_hold_ratio": round(beat_count / len(per_sub_index), 4)
        if per_sub_index
        else 0.0,
        "average_excess_return": round(total_excess / len(per_sub_index), 6)
        if per_sub_index
        else 0.0,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "per_sub_index": per_sub_index,
        "summary": summary,
    }


def save_phase17_report(
    report: dict[str, Any],
    path: Path | str | None = None,
) -> Path:
    """将 Phase 17 报告持久化为 JSON。"""
    output_path = Path(path or DEFAULT_OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    return output_path


def main() -> None:
    """CLI entry point for generating the Phase 17 report."""
    report = build_phase17_report()
    save_phase17_report(report)
    print(f"Phase 17 report saved to {DEFAULT_OUTPUT_PATH}")
    summary = report["summary"]
    print(
        f"Beat buy-and-hold: {summary['beat_buy_and_hold_count']}/{summary['sub_index_count']} "
        f"({summary['beat_buy_and_hold_ratio']*100:.2f}%)"
    )


if __name__ == "__main__":
    main()
