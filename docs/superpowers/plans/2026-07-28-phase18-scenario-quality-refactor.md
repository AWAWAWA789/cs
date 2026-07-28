# Phase 18 情景质量重构与概率门槛体系

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正情景生成器输出“数量多但概率低”的问题，建立 2–4 条高概率情景输出规范，用动态概率门槛替代固定阈值，并生成 Phase 18 质量验证报告。

**Architecture:** 在 `scenario_generator.py` 中新增 `_select_high_probability_scenarios` 与 `_normalize_probabilities` 两个纯函数，把原 `_ensure_diversity` 的“补齐 4–6 条”逻辑替换为“按动态门槛筛选 → 兜底 2 条 → 截断 4 条 → 重归一化”流程；同步更新 `generate_scenarios` 默认参数与测试断言；新增 `generate_phase18_report.py` 遍历子指数输出 `reports/phase18_scenario_quality_validation.json`。

**Tech Stack:** Python 3.10, pandas, numpy, pytest, FastAPI.

---

## File Structure

| 文件 | 类型 | 职责 |
|------|------|------|
| `src/scenario_engine/scenario_generator.py` | 修改 | 实现动态概率门槛、情景数量约束、概率重归一化 |
| `tests/scenario_engine/test_scenario_generator.py` | 修改 | 更新数量/概率断言，新增分布健康度测试 |
| `generate_phase18_report.py` | 新建 | 遍历子指数缓存，生成情景质量验证报告 |
| `tests/test_phase18_report.py` | 新建 | 验证报告生成器字段与分布健康度计算 |
| `reports/phase18_scenario_quality_validation.json` | 新建 | Phase 18 验证结果 |

---

## Task 1: 实现动态概率门槛与情景数量约束

**Files:**
- Modify: `src/scenario_engine/scenario_generator.py`
- Test: `tests/scenario_engine/test_scenario_generator.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/scenario_engine/test_scenario_generator.py
import pytest

from src.scenario_engine.scenario_generator import (
    _compute_probability_threshold,
    _select_high_probability_scenarios,
)


def test_compute_probability_threshold_dynamic_floor():
    probs = [0.5, 0.3, 0.15, 0.05]
    threshold = _compute_probability_threshold(probs)
    # relative floor = max(1/4, 0.10) = 0.25
    # dynamic floor = 0.15 * 0.5 = 0.075
    # absolute floor = 0.05
    assert threshold == pytest.approx(0.25, abs=1e-6)


def test_select_high_probability_scenarios_enforces_min_and_max():
    scenarios = [
        {"scenario_key": "bullish_continuation", "probability": 0.5, "direction": 1},
        {"scenario_key": "bearish_reversal", "probability": 0.3, "direction": -1},
        {"scenario_key": "dip_then_rise", "probability": 0.15, "direction": 1},
        {"scenario_key": "range_bound", "probability": 0.05, "direction": 0},
    ]
    selected = _select_high_probability_scenarios(scenarios)
    assert 2 <= len(selected) <= 4
    total = sum(s["probability"] for s in selected)
    assert abs(total - 1.0) < 1e-6
```

Run: `pytest tests/scenario_engine/test_scenario_generator.py::test_compute_probability_threshold_dynamic_floor tests/scenario_engine/test_scenario_generator.py::test_select_high_probability_scenarios_enforces_min_and_max -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 2: 实现概率门槛函数**

在 `src/scenario_engine/scenario_generator.py` 中 `_ensure_diversity` 之前新增：

```python
def _compute_probability_threshold(probabilities: list[float]) -> float:
    """计算动态概率入选门槛。

    规则：
    - 相对下界 = max(1 / n, 0.10)，n 为候选情景数；
    - 动态下界 = 第 3 大概率（若存在）的 50%；
    - 绝对硬底 = 0.05；
    - 最终门槛 = 三者最大值。
    """
    n = len(probabilities)
    if n == 0:
        return 0.0

    sorted_probs = sorted(probabilities, reverse=True)
    relative_floor = max(1.0 / n, 0.10)
    dynamic_floor = sorted_probs[2] * 0.5 if n >= 3 else 0.0
    absolute_floor = 0.05

    return float(max(relative_floor, dynamic_floor, absolute_floor))


def _normalize_probabilities(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对情景概率做重归一化，使总和为 1。"""
    total = sum(s["probability"] for s in scenarios)
    if total <= 0:
        equal = round(1.0 / len(scenarios), 6) if scenarios else 0.0
        for s in scenarios:
            s["probability"] = equal
        return scenarios

    for s in scenarios:
        s["probability"] = round(s["probability"] / total, 6)

    # 修正浮点误差：将余量加到最后一个元素。
    remainder = 1.0 - sum(s["probability"] for s in scenarios)
    if scenarios:
        scenarios[-1]["probability"] = round(scenarios[-1]["probability"] + remainder, 6)
    return scenarios


def _select_high_probability_scenarios(
    scenarios: list[dict[str, Any]],
    min_scenarios: int = 2,
    max_scenarios: int = 4,
) -> list[dict[str, Any]]:
    """按动态概率门槛筛选情景，确保数量在 [min, max] 之间，并做概率重归一化。"""
    if not scenarios:
        return []

    # 按概率降序排列，便于后续截取。
    sorted_scenarios = sorted(
        scenarios, key=lambda x: x["probability"], reverse=True
    )
    probabilities = [s["probability"] for s in sorted_scenarios]
    threshold = _compute_probability_threshold(probabilities)

    # 先按门槛筛选。
    selected = [s for s in sorted_scenarios if s["probability"] >= threshold]

    # 兜底：不足 min_scenarios 时按概率排名补足。
    if len(selected) < min_scenarios:
        selected = sorted_scenarios[:min_scenarios]

    # 截断：超过 max_scenarios 时只保留前 max_scenarios。
    if len(selected) > max_scenarios:
        selected = selected[:max_scenarios]

    return _normalize_probabilities(selected)


def _count_unique_directions(scenarios: list[dict[str, Any]]) -> int:
    """统计不同方向的数量。"""
    return len({s["direction"] for s in scenarios})
```

- [ ] **Step 3: 替换 `_ensure_diversity` 调用**

将 `src/scenario_engine/scenario_generator.py` 中：

```python
scenarios = _ensure_diversity(scenarios, base_df, min_scenarios=min_scenarios, max_scenarios=max_scenarios)
```

改为：

```python
scenarios = _select_high_probability_scenarios(scenarios, min_scenarios=min_scenarios, max_scenarios=max_scenarios)
```

- [ ] **Step 4: 更新 `generate_scenarios` 默认参数**

将 `generate_scenarios` 函数签名中的：

```python
    max_scenarios: int = 6,
    min_scenarios: int = 4,
```

改为：

```python
    max_scenarios: int = 4,
    min_scenarios: int = 2,
```

同时更新 docstring 中对应描述。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/scenario_engine/test_scenario_generator.py -v`
Expected: 新测试通过；既有测试可能因数量断言失败，进入 Step 6。

- [ ] **Step 6: 更新既有测试断言**

将 `tests/scenario_engine/test_scenario_generator.py` 中所有 `4 <= len(...) <= 6` 改为 `2 <= len(...) <= 4`，并删除 `test_standard_scenario_names_present`（原要求必须同时包含 4 个名称，与新数量约束冲突）：

```python
def test_generate_scenarios_returns_two_to_four():
    df = _make_ohlc(250)
    result = generate_scenarios({"1day": df})
    scenarios = result["scenarios"]
    assert 2 <= len(scenarios) <= 4
```

- [ ] **Step 7: 运行测试**

Run: `pytest tests/scenario_engine/test_scenario_generator.py -v`
Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add src/scenario_engine/scenario_generator.py tests/scenario_engine/test_scenario_generator.py
git commit -m "feat(scenario): enforce 2-4 high-probability scenarios with dynamic threshold"
```

---

## Task 2: 新增 Phase 18 质量验证报告生成器

**Files:**
- Create: `generate_phase18_report.py`
- Create: `tests/test_phase18_report.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_phase18_report.py
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate_phase18_report import (
    _evaluate_scenario_quality,
    build_phase18_report,
)


def test_evaluate_scenario_quality_flags_oligopoly():
    scenarios = [
        {"probability": 0.97, "direction": 1},
        {"probability": 0.01, "direction": -1},
        {"probability": 0.01, "direction": 0},
        {"probability": 0.01, "direction": 1},
    ]
    quality = _evaluate_scenario_quality(scenarios)
    assert quality["count"] == 4
    assert quality["min_probability"] == pytest.approx(0.01, abs=1e-6)
    assert quality["max_probability"] == pytest.approx(0.97, abs=1e-6)
    assert quality["has_oligopoly"] is True
    assert quality["unique_directions"] == 3


def test_report_contains_quality_fields():
    rng = np.random.default_rng(31)
    n = 200
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
    report = build_phase18_report({"test_index": df})
    assert "generated_at" in report
    assert "per_sub_index" in report
    assert "summary" in report
    assert "test_index" in report["per_sub_index"]
    entry = report["per_sub_index"]["test_index"]
    assert "quality" in entry
    assert "scenarios" in entry
```

Run: `pytest tests/test_phase18_report.py -v`
Expected: FAIL with `ModuleNotFoundError`。

- [ ] **Step 2: 实现报告生成器**

```python
# generate_phase18_report.py
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
            and quality["unique_directions"] >= 2
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
```

Run: `pytest tests/test_phase18_report.py -v`
Expected: PASS。

- [ ] **Step 3: 提交**

```bash
git add generate_phase18_report.py tests/test_phase18_report.py
git commit -m "feat(reports): add Phase 18 scenario quality validation report generator"
```

---

## Task 3: 运行 Phase 18 报告并提交结果

**Files:**
- Create: `reports/phase18_scenario_quality_validation.json`

- [ ] **Step 1: 运行生成器**

Run: `python generate_phase18_report.py`
Expected: 输出各子指数情景质量结果，并保存到 `reports/phase18_scenario_quality_validation.json`。

- [ ] **Step 2: 提交报告**

```bash
git add reports/phase18_scenario_quality_validation.json
git commit -m "reports: add Phase 18 scenario quality validation results"
```

---

## Task 4: 全量回归测试

- [ ] **Step 1: 运行全量测试**

Run: `pytest -q`
Expected: 全部通过。

---

## Self-Review

1. **Spec coverage:**
   - 2–4 条情景、通常 3 条 -> `_select_high_probability_scenarios` 默认参数。
   - 动态概率门槛 -> `_compute_probability_threshold`。
   - 5% 硬底 -> `absolute_floor = 0.05`。
   - 重归一化 -> `_normalize_probabilities`。
   - 分布健康度检查 -> `_evaluate_scenario_quality` 与 `has_oligopoly`。
   - 无遗漏。

2. **Placeholder scan:**
   - 无 TBD/TODO。
   - 所有代码块完整。

3. **Type consistency:**
   - `_select_high_probability_scenarios` 与 `generate_scenarios` 的参数名一致。
   - 报告字段与测试断言一致。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-28-phase18-scenario-quality-refactor.md`.**

**Execution approach:** Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.
