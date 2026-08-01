"""案例库存储（JSONL + Parquet 双格式）。

案例库是历史训练的核心资产——每次吸货分析的特征向量 + 评分 + 时间戳
都会落盘，事后回看标注，最终用于训练。

存储格式：
- JSONL（append-only）：全量案例，含未标注的
- Parquet：已标注案例，训练用

落盘路径：
- ``data/cases/{category}_cases.jsonl``
- ``data/cases/{category}_cases_labeled.parquet``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.api.logging import get_logger

LOGGER = get_logger("csqaq.case_store")


def cases_path(cache_root: str | Path, category: str) -> Path:
    """JSONL 案例库路径。"""
    return Path(cache_root) / "cases" / f"{category}_cases.jsonl"


def labeled_path(cache_root: str | Path, category: str) -> Path:
    """已标注案例 Parquet 路径。"""
    return Path(cache_root) / "cases" / f"{category}_cases_labeled.parquet"


def save_case(case: dict[str, Any], cache_root: str | Path, category: str) -> None:
    """追加单条案例到 JSONL。"""
    path = cases_path(cache_root, category)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(case, ensure_ascii=False, default=str) + "\n")


def save_cases_batch(
    cases: list[dict[str, Any]],
    cache_root: str | Path,
    category: str,
    overwrite: bool = False,
) -> None:
    """批量写案例。

    Args:
        cases: 案例列表
        cache_root: 缓存根目录
        category: 品类
        overwrite: True=覆盖写，False=追加写
    """
    path = cases_path(cache_root, category)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "a"
    with path.open(mode, encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False, default=str) + "\n")
    LOGGER.info("saved %d cases to %s (mode=%s)", len(cases), path, mode)


def load_cases(cache_root: str | Path, category: str) -> list[dict[str, Any]]:
    """加载全量案例（含未标注）。"""
    path = cases_path(cache_root, category)
    if not path.exists():
        return []
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return cases


def load_labeled_cases(cache_root: str | Path, category: str) -> list[dict[str, Any]]:
    """加载已标注案例（仅 label 非 None 的）。"""
    all_cases = load_cases(cache_root, category)
    return [c for c in all_cases if c.get("label") is not None]


def save_labeled_parquet(
    cases: list[dict[str, Any]],
    cache_root: str | Path,
    category: str,
) -> Path:
    """将已标注案例保存为 Parquet（训练用）。

    signals/features 等嵌套字典展平为前缀列，避免 Parquet 无法写空 struct。
    """
    path = labeled_path(cache_root, category)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cases:
        pd.DataFrame().to_parquet(path, index=False)
        return path

    rows = []
    for c in cases:
        row = {}
        for k, v in c.items():
            if isinstance(v, dict):
                # 展平字典
                for sub_k, sub_v in v.items():
                    row[f"{k}_{sub_k}"] = sub_v
            else:
                row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_parquet(path, index=False)
    return path


def update_labels(
    labeled_cases: list[dict[str, Any]],
    cache_root: str | Path,
    category: str,
) -> None:
    """用已标注案例重写全量案例库（保留未标注案例的 label=None）。"""
    all_cases = load_cases(cache_root, category)
    labeled_map = {c["case_id"]: c for c in labeled_cases}

    # 合并：保留原案例，更新已标注的
    merged = []
    for c in all_cases:
        cid = c.get("case_id")
        if cid and cid in labeled_map:
            merged.append(labeled_map[cid])
        else:
            merged.append(c)

    # 覆盖写 JSONL
    save_cases_batch(merged, cache_root, category, overwrite=True)

    # 同步写 Parquet
    labeled = [c for c in merged if c.get("label") is not None]
    save_labeled_parquet(labeled, cache_root, category)


def case_count(cache_root: str | Path, category: str) -> dict[str, int]:
    """统计案例数。"""
    all_cases = load_cases(cache_root, category)
    labeled = [c for c in all_cases if c.get("label") is not None]
    return {
        "total": len(all_cases),
        "labeled": len(labeled),
        "unlabeled": len(all_cases) - len(labeled),
    }
