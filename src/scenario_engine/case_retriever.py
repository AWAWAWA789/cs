"""在线推理：检索历史相似案例。

F2 升级：支持双轨特征向量（K线 + 库存）。
- 若案例库的 case 含 inventory_features，检索向量扩展为双轨
- 命中率改为"预测准确率"（标注正确率），而非 positive 占比

加载已训练的案例索引，计算当前饰品的特征向量，用 KNN 检索 top-K 相似案例，
返回它们的标签与事后走势，供人工判断当前是否在吸货。

复用 sklearn NearestNeighbors + z-score 标准化。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from src.api.logging import get_logger
from src.scenario_engine.trainer import (
    FEATURE_KEYS,
    load_case_index,
    load_rule_weights,
)

LOGGER = get_logger("csqaq.case_retriever")


# F2: 库存特征 keys（与 inventory_snapshot computed_signals 对齐）
INVENTORY_FEATURE_KEYS = [
    "top3_concentration",
    "net_inflow_7d",
    "active_holder_count",
    "holder_total",
    "concentration",
    "net_inflow",
    "holder_activity",
]


def _build_feature_vector(features: dict[str, Any]) -> np.ndarray:
    """从特征字典构建 K 线向量（与 trainer.FEATURE_KEYS 对齐）。"""
    vec = []
    for key in FEATURE_KEYS:
        val = features.get(key)
        try:
            vec.append(float(val) if val is not None else 0.0)
        except (TypeError, ValueError):
            vec.append(0.0)
    return np.array(vec, dtype=float).reshape(1, -1)


def _build_dual_track_vector(
    kline_features: dict[str, Any],
    inventory_features: dict[str, Any] | None,
) -> np.ndarray:
    """F2: 构建双轨特征向量（K线 + 库存）。

    若 inventory_features 为空，库存部分填 0。
    """
    kline_vec = _build_feature_vector(kline_features).flatten()
    inv_vec = []
    for key in INVENTORY_FEATURE_KEYS:
        val = (inventory_features or {}).get(key)
        try:
            inv_vec.append(float(val) if val is not None else 0.0)
        except (TypeError, ValueError):
            inv_vec.append(0.0)
    return np.concatenate([kline_vec, np.array(inv_vec)]).reshape(1, -1)


def retrieve_similar(
    good_id: str,
    category: str,
    period: str,
    cache_root: str | Path,
    top_k: int = 5,
) -> dict[str, Any]:
    """检索历史相似案例。

    Args:
        good_id: 查询饰品 good_id
        category: 品类
        period: 周期
        cache_root: 缓存根目录
        top_k: 返回的相似案例数

    Returns:
        {
            "query_good_id": str,
            "query_features": {...},
            "similar_cases": [{...}],
            "hit_rate": float | None,
            "trained": bool,
        }
    """
    # 加载案例索引
    index_df = load_case_index(cache_root, category)
    if index_df is None or len(index_df) == 0:
        return {
            "query_good_id": good_id,
            "query_features": {},
            "similar_cases": [],
            "hit_rate": None,
            "trained": False,
            "reason": "case_index_not_built",
        }

    # 加载当前饰品最新特征
    from src.data.item_cache import load_item_ohlc
    from src.scenario_engine.accumulation_detector import detect_accumulation

    df = load_item_ohlc(good_id, period, cache_root, category)
    if df is None or len(df) < 60:
        return {
            "query_good_id": good_id,
            "query_features": {},
            "similar_cases": [],
            "hit_rate": None,
            "trained": True,
            "reason": "query_ohlc_unavailable",
        }

    result = detect_accumulation(
        df, sub_index=f"{category}#{good_id}", period=period,
        cache_root=cache_root, category=category,
    )
    query_features = result.get("features", {})

    # F2: 检测案例库是否含库存特征列
    inv_feat_cols = [f"inv_{k}" for k in INVENTORY_FEATURE_KEYS]
    has_inventory = all(c in index_df.columns for c in inv_feat_cols)

    if has_inventory:
        # 双轨检索：尝试加载当前品的库存快照
        from src.data.inventory_snapshot import load_snapshot_for_date
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        snap = load_snapshot_for_date(good_id, today, cache_root)
        query_inv = snap or {}
        query_vec = _build_dual_track_vector(query_features, query_inv)
        # 构建双轨索引矩阵
        kline_cols = [f"feat_{k}" for k in FEATURE_KEYS]
        X = index_df[kline_cols + inv_feat_cols].values
    else:
        # 旧版 K 线单轨检索
        query_vec = _build_feature_vector(query_features)
        feat_cols = [f"feat_{k}" for k in FEATURE_KEYS]
        X = index_df[feat_cols].values if all(c in index_df.columns for c in feat_cols) else None

    if X is None or len(X) == 0:
        return {
            "query_good_id": good_id,
            "query_features": query_features,
            "similar_cases": [],
            "hit_rate": None,
            "trained": True,
            "reason": "index_matrix_empty",
            "dual_track": has_inventory,
        }

    # z-score 标准化（用索引集的均值/方差）
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0  # 防除零
    X_scaled = (X - mean) / std
    query_scaled = (query_vec - mean) / std

    # KNN 检索
    k = min(top_k, len(X))
    nn = NearestNeighbors(n_neighbors=k, metric="euclidean", algorithm="auto")
    nn.fit(X_scaled)
    distances, indices = nn.kneighbors(query_scaled)

    # 组装结果
    similar_cases = []
    for dist, idx in zip(distances[0], indices[0]):
        row = index_df.iloc[idx]
        similar_cases.append({
            "case_id": str(row.get("case_id", "")),
            "good_id": str(row.get("good_id", "")),
            "good_name": str(row.get("good_name", "")),
            "timestamp": str(row.get("timestamp", "")),
            "kline_score": float(row.get("kline_score", 0)),
            "inventory_score": float(row.get("inventory_score", 0)) if "inventory_score" in row else 0.0,
            "fused_score": float(row.get("fused_score", 0)) if "fused_score" in row else 0.0,
            "label": str(row.get("label", "")),
            "future_return_30d": float(row["future_return_30d"]) if pd.notna(row.get("future_return_30d")) else None,
            "max_drawdown_30d": float(row["max_drawdown_30d"]) if pd.notna(row.get("max_drawdown_30d")) else None,
            "distance": round(float(dist), 4),
        })

    # F2: 命中率改为"预测准确率"
    # 当前 query 的预测 = fused_score ≥ 0.5 视为 positive 预测
    # 准确率 = 预测 positive 且实际 positive + 预测 negative 且实际 negative
    query_pred_positive = float(result.get("accumulation_score", 0)) >= 0.5
    correct = 0
    total_labeled = 0
    for c in similar_cases:
        if c["label"] not in ("positive", "negative"):
            continue
        total_labeled += 1
        case_pred_positive = c.get("fused_score", c.get("kline_score", 0)) >= 0.5
        if case_pred_positive == (c["label"] == "positive"):
            correct += 1
    accuracy = (correct / total_labeled) if total_labeled > 0 else None

    # 兼容字段：positive 占比（旧 hit_rate 含义，保留）
    pos_count = sum(1 for c in similar_cases if c["label"] == "positive")
    positive_ratio = (pos_count / total_labeled) if total_labeled > 0 else None

    # 加载训练权重（如果有）
    weights = load_rule_weights(cache_root, category)
    trained = weights is not None and weights.get("trained", False)

    return {
        "query_good_id": good_id,
        "query_features": query_features,
        "query_kline_score": float(result.get("accumulation_score", 0)),
        "similar_cases": similar_cases,
        # F2: hit_rate 现在是预测准确率
        "hit_rate": round(accuracy, 4) if accuracy is not None else None,
        "positive_ratio": round(positive_ratio, 4) if positive_ratio is not None else None,
        "trained": trained,
        "case_count": len(index_df),
        "dual_track": has_inventory,
    }
