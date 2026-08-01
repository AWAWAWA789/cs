"""训练-推理一致性测试。

验证：
1. 训练产物落盘后，detect_accumulation 能正确加载并使用 trained 权重
2. 权重热加载（mtime 变化）能刷新缓存
3. 删除训练产物后自动回退 empirical
4. feature_mode 字段在训练/推理两端一致
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.accumulation_detector import (
    detect_accumulation,
    rule_engine_score,
    _TRAINED_WEIGHTS_CACHE,
)
from src.scenario_engine.trainer import train_rule_weights


def _make_synthetic_ohlc(n: int = 120, seed: int = 42) -> pd.DataFrame:
    """生成合成 OHLC 数据用于测试。"""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
    high = close + rng.random(n) * 2
    low = close - rng.random(n) * 2
    open_ = close + rng.standard_normal(n) * 0.3
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        "open": open_, "high": high, "low": low, "close": close,
    })


def _make_labeled_cases(n: int = 30) -> list[dict]:
    """构造 n 个已标注案例用于训练。"""
    cases = []
    rng = np.random.default_rng(0)
    for i in range(n):
        df = _make_synthetic_ohlc(80, seed=i)
        result = detect_accumulation(df, sub_index=f"test#{i}", period="1day")
        label = "positive" if rng.random() > 0.5 else "negative"
        cases.append({
            "case_id": f"rifle_{i}_20240101",
            "good_id": str(i),
            "good_name": f"TestItem-{i}",
            "category": "rifle",
            "timestamp": "2024-01-01",
            "period": "1day",
            "features": result["features"],
            "kline_score": result["accumulation_score"],
            "label": label,
        })
    return cases


def test_train_then_inference_uses_trained_weights(tmp_path: Path) -> None:
    """训练后推理应使用 trained 权重。"""
    cases = _make_labeled_cases(30)
    cache_root = tmp_path / "cache"

    # 训练
    result = train_rule_weights(cases, cache_root, "rifle")
    assert result["trained"] is True
    assert result["feature_mode"] == "FULL"
    assert "trained_at" in result

    # 训练产物存在
    weights_path = cache_root / "trained" / "rifle_rule_weights.json"
    assert weights_path.exists()

    # 推理：detect_accumulation 应使用 trained 权重
    df = _make_synthetic_ohlc(120, seed=100)
    # 重置缓存避免测试间污染
    _TRAINED_WEIGHTS_CACHE.update(path=None, mtime=0.0, data=None)
    r = detect_accumulation(
        df, sub_index="consistency_test", period="1day",
        cache_root=cache_root, category="rifle",
    )
    assert r["weights_source"] == "trained"
    assert r["feature_mode"] == "FULL"


def test_no_training_falls_back_to_empirical(tmp_path: Path) -> None:
    """无训练产物时回退 empirical。"""
    cache_root = tmp_path / "empty_cache"
    df = _make_synthetic_ohlc(120, seed=42)
    _TRAINED_WEIGHTS_CACHE.update(path=None, mtime=0.0, data=None)
    r = detect_accumulation(
        df, sub_index="empirical_test", period="1day",
        cache_root=cache_root, category="rifle",
    )
    assert r["weights_source"] == "empirical"


def test_weights_hot_reload_on_mtime_change(tmp_path: Path) -> None:
    """训练产物 mtime 变化后，缓存应刷新。"""
    cases1 = _make_labeled_cases(30)
    cases2 = _make_labeled_cases(30)
    # 第二组用不同 seed 让权重不同
    for i, c in enumerate(cases2):
        c["label"] = "negative" if c["label"] == "positive" else "positive"

    cache_root = tmp_path / "hot_reload"
    train_rule_weights(cases1, cache_root, "rifle")
    weights_path = cache_root / "trained" / "rifle_rule_weights.json"
    mtime1 = weights_path.stat().st_mtime

    # 首次加载
    _TRAINED_WEIGHTS_CACHE.update(path=None, mtime=0.0, data=None)
    df = _make_synthetic_ohlc(120, seed=42)
    detect_accumulation(df, cache_root=cache_root, category="rifle")
    cached_path = _TRAINED_WEIGHTS_CACHE["path"]
    cached_mtime = _TRAINED_WEIGHTS_CACHE["mtime"]
    assert cached_path == str(weights_path)
    assert cached_mtime == mtime1

    # 等 0.01s 让 mtime 可区分，重训
    time.sleep(0.01)
    train_rule_weights(cases2, cache_root, "rifle")
    mtime2 = weights_path.stat().st_mtime
    assert mtime2 > mtime1

    # 再推理应触发重新加载
    detect_accumulation(df, cache_root=cache_root, category="rifle")
    assert _TRAINED_WEIGHTS_CACHE["mtime"] == mtime2


def test_close_only_mode_does_not_use_full_trained_weights(tmp_path: Path) -> None:
    """CLOSE_ONLY 模式不应错误使用 FULL 训练权重。"""
    cases = _make_labeled_cases(30)
    cache_root = tmp_path / "mode_mismatch"
    train_rule_weights(cases, cache_root, "rifle")

    # 构造 CLOSE_ONLY 数据（伪 OHLC）
    df_full = _make_synthetic_ohlc(120, seed=42)
    df_fake = df_full.copy()
    df_fake["open"] = df_fake["high"] = df_fake["low"] = df_fake["close"]

    _TRAINED_WEIGHTS_CACHE.update(path=None, mtime=0.0, data=None)
    r = detect_accumulation(
        df_fake, sub_index="close_only_test", period="1day",
        cache_root=cache_root, category="rifle",
    )
    assert r["feature_mode"] == "CLOSE_ONLY"
    # 训练产物是 FULL，不匹配 → 应回退 empirical
    assert r["weights_source"] == "empirical"


def test_untrained_product_falls_back(tmp_path: Path) -> None:
    """训练产物标记 trained=False 时回退 empirical。"""
    cache_root = tmp_path / "untrained"
    weights_dir = cache_root / "trained"
    weights_dir.mkdir(parents=True)
    (weights_dir / "rifle_rule_weights.json").write_text(json.dumps({
        "trained": False,
        "reason": "insufficient_data",
        "feature_mode": "FULL",
    }))

    df = _make_synthetic_ohlc(120, seed=42)
    _TRAINED_WEIGHTS_CACHE.update(path=None, mtime=0.0, data=None)
    r = detect_accumulation(
        df, sub_index="untrained_test", period="1day",
        cache_root=cache_root, category="rifle",
    )
    assert r["weights_source"] == "empirical"


def test_confidence_values() -> None:
    """置信度计算覆盖各模式与样本量。"""
    from src.scenario_engine.accumulation_detector import _compute_confidence
    # FULL + 大样本 → 高置信
    assert _compute_confidence("FULL", 500) == 0.95
    # FULL + 小样本 → 中置信
    assert _compute_confidence("FULL", 50) == 0.75
    # CLOSE_ONLY + 无样本 → 较低
    assert _compute_confidence("CLOSE_ONLY", None) == 0.55
    # DEGRADED → 最低
    assert _compute_confidence("DEGRADED", None) == 0.35
