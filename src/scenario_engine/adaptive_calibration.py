"""子指数级自适应温度校准。

为每个子指数搜索最优 softmax 温度，使 walk-forward Brier 分数最小。
温度持久化到 data/calibration/，推理时优先读取。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.scenario_engine.bayesian_calibration import compute_brier_score


DEFAULT_CALIBRATION_DIR = Path("data") / "calibration"
DEFAULT_TEMPERATURE_GRID = [0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 5.0]
DEFAULT_TEMPERATURE = 1.0


def _temperature_scale(probs: np.ndarray, temperature: float) -> np.ndarray:
    """对概率分布进行温度缩放。"""
    if temperature <= 0:
        temperature = 1e-6
    log_probs = np.log(np.asarray(probs, dtype=float) + 1e-12)
    scaled = log_probs / temperature
    max_val = np.max(scaled)
    exps = np.exp(scaled - max_val)
    return exps / (np.sum(exps) + 1e-12)


def find_best_temperature(
    probabilities: list[float],
    outcomes: list[int],
    temperatures: list[float] | None = None,
) -> float:
    """在温度网格上搜索使 Brier 分数最小的温度。

    Args:
        probabilities: 单一方向的预测概率列表。
        outcomes: 对应的二元真实结果。
        temperatures: 候选温度列表。

    Returns:
        最优温度。若输入为空则返回默认温度。
    """
    if not probabilities:
        return DEFAULT_TEMPERATURE

    probs = np.asarray(probabilities, dtype=float)
    outs = np.asarray(outcomes, dtype=int)
    temps = temperatures or DEFAULT_TEMPERATURE_GRID

    best_temp = DEFAULT_TEMPERATURE
    best_brier = float("inf")
    for temp in temps:
        scaled = _temperature_scale(probs, temp)
        brier = float(np.mean((scaled - outs) ** 2))
        if brier < best_brier:
            best_brier = brier
            best_temp = temp

    return float(best_temp)


def save_temperature(
    sub_index: str,
    temperature: float,
    base_dir: Path | str | None = None,
) -> Path:
    """持久化子指数最优温度。"""
    base = Path(base_dir) if base_dir else DEFAULT_CALIBRATION_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{sub_index}_temperature.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            {"sub_index": sub_index, "temperature": float(temperature)},
            f,
            ensure_ascii=False,
            indent=2,
        )
    return path


def load_temperature(
    sub_index: str,
    base_dir: Path | str | None = None,
) -> float:
    """加载子指数最优温度，未命中返回默认值。"""
    base = Path(base_dir) if base_dir else DEFAULT_CALIBRATION_DIR
    path = base / f"{sub_index}_temperature.json"
    if not path.exists():
        return DEFAULT_TEMPERATURE
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return float(data.get("temperature", DEFAULT_TEMPERATURE))
