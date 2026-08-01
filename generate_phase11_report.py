"""Generate the Phase 11 predefined-template backtest report.

Runs every scenario template on the four configured sub-indices using cached
1-day OHLC data, computes forward-return statistics, and writes a JSON report.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.api.client import CSQAQClient
from src.config import Settings
from src.data.pipeline import load_or_fetch
from src.scenario_engine.template_matcher import load_templates, match_templates


SUB_INDICES = ["手套", "匕首", "百元主战", "贴纸"]
PERIOD = "1day"
HORIZONS = [5, 10, 20]
MIN_CONFIDENCE = 0.5


def _compute_forward_returns(
    df,
    match: dict,
    horizons: list[int],
) -> dict[str, float]:
    """Compute signed forward returns for a single match."""
    idx = match["matched_index"]
    entry_close = float(df["close"].iloc[idx])
    direction = match.get("direction", "bullish")
    signed_returns: dict[str, float] = {}
    for h in horizons:
        future_idx = min(idx + h, len(df) - 1)
        future_close = float(df["close"].iloc[future_idx])
        raw_return = (future_close - entry_close) / entry_close
        signed_return = -raw_return if direction == "bearish" else raw_return
        signed_returns[f"return_{h}"] = signed_return
    return signed_returns


def _aggregate_template_stats(
    matches: list[dict],
    returns: list[dict],
    horizons: list[int],
) -> dict[str, Any]:
    """Aggregate per-template statistics."""
    n = len(matches)
    if n == 0:
        return {
            "matches": 0,
            "avg_confidence": 0.0,
            **{f"win_rate_{h}": None for h in horizons},
            **{f"avg_signed_return_{h}": None for h in horizons},
            **{f"wins_{h}": 0 for h in horizons},
        }

    avg_confidence = sum(m["confidence"] for m in matches) / n
    stats: dict[str, Any] = {
        "matches": n,
        "avg_confidence": round(avg_confidence, 4),
    }

    for h in horizons:
        rets = [r[f"return_{h}"] for r in returns]
        wins = sum(1 for ret in rets if ret > 0)
        stats[f"wins_{h}"] = wins
        stats[f"win_rate_{h}"] = round(wins / n, 4)
        stats[f"avg_signed_return_{h}"] = round(sum(rets) / n, 6)

    return stats


def main() -> None:
    os.environ.setdefault("CSQAQ_API_TOKEN", "dummy")
    settings = Settings()
    client = CSQAQClient(settings)

    templates = load_templates()
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    per_subindex: dict[str, dict[str, dict[str, Any]]] = {}
    summary_counters: dict[str, dict[str, Any]] = {
        t["name"]: {
            "matches": 0,
            "wins": {h: 0 for h in HORIZONS},
            "signed_returns": {h: [] for h in HORIZONS},
            "confidence_sum": 0.0,
        }
        for t in templates
    }

    for sub_index_name in SUB_INDICES:
        print(f"Processing {sub_index_name} ...")
        df = load_or_fetch(
            settings,
            client,
            sub_index_name=sub_index_name,
            sub_index_id="dummy",
            period=PERIOD,
        )
        per_subindex[sub_index_name] = {}

        for template in templates:
            template_name = template["name"]
            matches = match_templates(
                df,
                templates=[template],
                min_confidence=MIN_CONFIDENCE,
            )
            returns = [_compute_forward_returns(df, m, HORIZONS) for m in matches]
            stats = _aggregate_template_stats(matches, returns, HORIZONS)
            per_subindex[sub_index_name][template_name] = stats

            counter = summary_counters[template_name]
            counter["matches"] += stats["matches"]
            counter["confidence_sum"] += stats["matches"] * stats["avg_confidence"]
            for h in HORIZONS:
                counter["wins"][h] += stats[f"wins_{h}"]
                counter["signed_returns"][h].extend(
                    [r[f"return_{h}"] for r in returns]
                )

    summary: dict[str, dict[str, Any]] = {}
    for template_name, counter in summary_counters.items():
        n = counter["matches"]
        if n == 0:
            summary[template_name] = {"matches": 0}
            for h in HORIZONS:
                summary[template_name][f"win_rate_{h}"] = None
                summary[template_name][f"avg_signed_return_{h}"] = None
            summary[template_name]["avg_confidence"] = 0.0
            continue

        summary[template_name] = {
            "matches": n,
            "avg_confidence": round(counter["confidence_sum"] / n, 4),
        }
        for h in HORIZONS:
            rets = counter["signed_returns"][h]
            summary[template_name][f"win_rate_{h}"] = round(counter["wins"][h] / n, 4)
            summary[template_name][f"avg_signed_return_{h}"] = (
                round(sum(rets) / n, 6) if rets else None
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": PERIOD,
        "start_date": "2024-01-01",
        "sub_indices": SUB_INDICES,
        "horizons": HORIZONS,
        "min_confidence": MIN_CONFIDENCE,
        "per_sub_index": per_subindex,
        "summary": summary,
    }

    output_path = report_dir / "phase11_template_backtest.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"Phase 11 backtest report saved to: {output_path}")


if __name__ == "__main__":
    main()
