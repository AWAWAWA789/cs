"""真实 Brier 分数跟踪器。

基于 walk-forward 方向胜率结果计算 Brier 分数，不再使用 proxy 标签：
actual_outcome 为未来 N 日实际方向是否与最高概率情景方向一致的二元标签。

Brier = mean((predicted_probability - actual_outcome)^2)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_DIRECTION_ACCURACY_PATH = Path("reports") / "phase14_direction_accuracy.json"
DEFAULT_OUTPUT_PATH = Path("reports") / "phase14_brier.json"


def _load_json(path: Path) -> dict[str, Any]:
    """加载 JSON 文件。"""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compute_brier(
    probabilities: list[float],
    outcomes: list[int],
) -> dict[str, Any]:
    """计算 Brier 分数与相关统计量。

    Args:
        probabilities: 模型输出的概率列表，取值范围 [0, 1]。
        outcomes: 实际结果列表，1 表示事件发生，0 表示未发生。

    Returns:
        包含 ``brier_score``、``n_samples``、``mean_probability`` 与
        ``mean_outcome`` 的字典。
    """
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same length")
    if not probabilities:
        return {
            "brier_score": 0.0,
            "n_samples": 0,
            "mean_probability": 0.0,
            "mean_outcome": 0.0,
        }

    probs = np.asarray(probabilities, dtype=float)
    outs = np.asarray(outcomes, dtype=int)
    return {
        "brier_score": round(float(np.mean((probs - outs) ** 2)), 6),
        "n_samples": len(probabilities),
        "mean_probability": round(float(np.mean(probs)), 6),
        "mean_outcome": round(float(np.mean(outs)), 6),
    }


def evaluate_direction_accuracy_report(
    report: dict[str, Any],
) -> dict[str, Any]:
    """从方向胜率报告中提取样本并计算各 horizon 的真实 Brier 分数。

    Args:
        report: ``phase14_direction_accuracy.json`` 解析后的字典。

    Returns:
        按子指数与 horizon 聚合的 Brier 结果字典。
    """
    horizons = report.get("horizons", [])
    per_sub_index: dict[str, Any] = {}

    for sub_index, info in report.get("per_sub_index", {}).items():
        samples = info.get("samples", [])
        sub_summary: dict[str, Any] = {}
        for horizon in horizons:
            probs: list[float] = []
            outcomes: list[int] = []
            for sample in samples:
                hit = sample.get(f"hit_{horizon}")
                if hit is None:
                    # 中性预测不参与 Brier 计算。
                    continue
                probs.append(float(sample.get("probability", 0.0)))
                outcomes.append(1 if hit else 0)
            sub_summary[f"horizon_{horizon}"] = compute_brier(probs, outcomes)
        per_sub_index[sub_index] = sub_summary

    aggregate: dict[str, Any] = {}
    for horizon in horizons:
        all_probs: list[float] = []
        all_outcomes: list[int] = []
        for info in report.get("per_sub_index", {}).values():
            for sample in info.get("samples", []):
                hit = sample.get(f"hit_{horizon}")
                if hit is None:
                    continue
                all_probs.append(float(sample.get("probability", 0.0)))
                all_outcomes.append(1 if hit else 0)
        aggregate[f"horizon_{horizon}"] = compute_brier(all_probs, all_outcomes)

    return {
        "sub_indices": report.get("sub_indices", []),
        "horizons": horizons,
        "walk_forward_params": report.get("walk_forward_params", {}),
        "aggregate": aggregate,
        "per_sub_index": per_sub_index,
    }


def generate_brier_report(
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """读取 walk-forward 方向胜率报告并输出 Brier 校准报告。

    Args:
        input_path: 方向胜率报告路径，默认为
            ``reports/phase14_direction_accuracy.json``。
        output_path: Brier 报告输出路径，默认为 ``reports/phase14_brier.json``。

    Returns:
        输出文件路径。
    """
    input_path = Path(input_path or DEFAULT_DIRECTION_ACCURACY_PATH)
    output_path = Path(output_path or DEFAULT_OUTPUT_PATH)

    accuracy_report = _load_json(input_path)
    brier_result = evaluate_direction_accuracy_report(accuracy_report)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(brier_result, f, indent=2, ensure_ascii=False, default=str)

    return output_path


def main() -> None:
    """CLI entry point for generating the Phase 14 Brier report."""
    output_path = generate_brier_report()
    print(f"Phase 14 Brier report saved to: {output_path}")


if __name__ == "__main__":
    main()
