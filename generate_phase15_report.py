"""生成 Phase 15 校准与基准综合报告。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.buy_and_hold import compute_buy_and_hold
from src.config import Settings
from src.data.cache import cache_file_path, load


DEFAULT_OUTPUT_DIR = Path("reports")
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "phase15_calibration_benchmark.json"


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


def build_phase15_report(
    df_by_sub_index: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """为每个子指数计算买入持有基准并汇总。"""
    if df_by_sub_index is None:
        settings = Settings()
        sub_indices = _discover_sub_indices(settings)
        df_by_sub_index = {}
        for sub_index in sub_indices:
            df = _load_daily_df(sub_index, settings)
            if df is not None:
                df_by_sub_index[sub_index] = df

    per_sub_index: dict[str, Any] = {}
    for sub_index, df in df_by_sub_index.items():
        per_sub_index[sub_index] = {
            "buy_and_hold": compute_buy_and_hold(df),
            "bar_count": len(df),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "per_sub_index": per_sub_index,
    }


def save_phase15_report(
    report: dict[str, Any],
    path: Path | str | None = None,
) -> Path:
    """将 Phase 15 报告持久化为 JSON。"""
    output_path = Path(path or DEFAULT_OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    return output_path


def main() -> None:
    """CLI entry point for generating the Phase 15 report."""
    report = build_phase15_report()
    save_phase15_report(report)
    print(f"Phase 15 report saved to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
