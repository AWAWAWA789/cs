"""训练模块：规则权重拟合 + 案例索引构建。

两部分：
1. **规则权重拟合**：用已标注案例库 fit LogisticRegression，得到数据驱动的
   特征权重，替代 accumulation_detector.RULE_WEIGHTS 的经验值。
2. **案例索引构建**：复用 index_builder 构建 KNN 索引，供在线推理检索。

训练产物落盘：
- ``data/trained/{category}_rule_weights.json``
- ``data/trained/{category}_case_index.parquet``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.api.logging import get_logger

LOGGER = get_logger("csqaq.trainer")

# 特征列顺序（与 detect_accumulation 输出对齐）
FEATURE_KEYS = [
    "price_position",
    "volume_price_divergence",
    "consolidation_score",
    "bottom_rising",
    "volatility_regime",
    "atr_percent",
    "volume_ratio",
    "volume_trend",
    "consolidation_bars",
    "distance_to_low",
]

# 训练产物路径
def _weights_path(cache_root: str | Path, category: str) -> Path:
    return Path(cache_root) / "trained" / f"{category}_rule_weights.json"


def _index_path(cache_root: str | Path, category: str) -> Path:
    return Path(cache_root) / "trained" / f"{category}_case_index.parquet"


def _build_feature_matrix(cases: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """从案例库构建特征矩阵 X 和标签 y。

    Returns:
        (X, y, feature_names)
    """
    rows = []
    labels = []
    for case in cases:
        features = case.get("features", {})
        if not isinstance(features, dict):
            continue
        row = []
        for key in FEATURE_KEYS:
            val = features.get(key)
            try:
                row.append(float(val) if val is not None else 0.0)
            except (TypeError, ValueError):
                row.append(0.0)
        rows.append(row)
        label = case.get("label")
        # positive=1, negative=0, neutral 跳过
        if label == "positive":
            labels.append(1)
        elif label == "negative":
            labels.append(0)
        else:
            labels.append(-1)  # neutral 暂存，下面过滤

    X = np.array(rows, dtype=float) if rows else np.zeros((0, len(FEATURE_KEYS)))
    y = np.array(labels, dtype=int) if labels else np.zeros(0, dtype=int)

    # 仅保留 positive/negative 样本
    mask = y >= 0
    return X[mask], y[mask], FEATURE_KEYS


def train_rule_weights(
    cases: list[dict[str, Any]],
    cache_root: str | Path,
    category: str = "rifle",
) -> dict[str, Any]:
    """用已标注案例拟合规则权重。

    Args:
        cases: 已标注案例列表
        cache_root: 缓存根目录
        category: 品类

    Returns:
        训练结果字典：weights / intercept / train_size / accuracy
    """
    X, y, feature_names = _build_feature_matrix(cases)

    if len(X) < 20 or len(np.unique(y)) < 2:
        LOGGER.warning(
            "insufficient labeled data: %d samples, %d classes (need ≥20 + 2 classes)",
            len(X), len(np.unique(y)),
        )
        return {
            "trained": False,
            "reason": "insufficient_data",
            "train_size": int(len(X)),
            "positive_count": int((y == 1).sum()),
            "negative_count": int((y == 0).sum()),
        }

    # 标准化 + 逻辑回归
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clf = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
    )
    clf.fit(X_scaled, y)

    # 训练集准确率（无验证集，仅作参考）
    train_acc = float(clf.score(X_scaled, y))

    # 提取权重并归一化到 [0, 1]（绝对值归一化，保持方向）
    raw_weights = clf.coef_[0]
    abs_sum = np.abs(raw_weights).sum()
    if abs_sum > 0:
        normalized_weights = (np.abs(raw_weights) / abs_sum).tolist()
    else:
        normalized_weights = [1.0 / len(feature_names) for _ in feature_names]

    # 权重符号：positive 应对应正权重
    weights_dict = {
        name: {
            "weight": float(raw_weights[i]),
            "direction": "positive" if raw_weights[i] >= 0 else "negative",
            "normalized": float(normalized_weights[i]),
        }
        for i, name in enumerate(feature_names)
    }

    result = {
        "trained": True,
        "weights": weights_dict,
        "intercept": float(clf.intercept_[0]),
        "train_accuracy": round(train_acc, 4),
        "train_size": int(len(X)),
        "positive_count": int((y == 1).sum()),
        "negative_count": int((y == 0).sum()),
        "feature_names": feature_names,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }

    # 落盘
    path = _weights_path(cache_root, category)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    LOGGER.info("trained rule weights → %s (acc=%.3f, n=%d)", path, train_acc, len(X))

    return result


def load_rule_weights(cache_root: str | Path, category: str = "rifle") -> dict[str, Any] | None:
    """加载已训练的规则权重。"""
    path = _weights_path(cache_root, category)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def build_case_index(
    cases: list[dict[str, Any]],
    cache_root: str | Path,
    category: str = "rifle",
) -> dict[str, Any]:
    """构建 KNN 案例索引（复用 index_builder 思路，但按 good_id 维度）。

    落盘为 Parquet，包含：特征向量 + 标签 + 事后走势 + good_id + 时间戳。
    在线推理时直接 pd.read_parquet + sklearn NearestNeighbors 查询。
    """
    labeled = [c for c in cases if c.get("label") is not None]
    if not labeled:
        return {"built": False, "reason": "no_labeled_cases"}

    # 展平为 DataFrame
    rows = []
    for case in labeled:
        features = case.get("features", {})
        if not isinstance(features, dict):
            continue
        row = {
            "case_id": case.get("case_id", ""),
            "good_id": case.get("good_id", ""),
            "good_name": case.get("good_name", ""),
            "timestamp": case.get("timestamp", ""),
            "kline_score": float(case.get("kline_score", 0)),
            "label": case.get("label"),
            "future_return_30d": case.get("future_return_30d"),
            "max_drawdown_30d": case.get("max_drawdown_30d"),
        }
        for key in FEATURE_KEYS:
            val = features.get(key)
            try:
                row[f"feat_{key}"] = float(val) if val is not None else 0.0
            except (TypeError, ValueError):
                row[f"feat_{key}"] = 0.0
        rows.append(row)

    df = pd.DataFrame(rows)
    path = _index_path(cache_root, category)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

    LOGGER.info("built case index → %s (%d cases)", path, len(df))
    return {
        "built": True,
        "index_path": str(path),
        "case_count": len(df),
        "feature_count": len(FEATURE_KEYS),
    }


def load_case_index(cache_root: str | Path, category: str = "rifle") -> pd.DataFrame | None:
    """加载已构建的案例索引。"""
    path = _index_path(cache_root, category)
    if not path.exists():
        return None
    return pd.read_parquet(path)
