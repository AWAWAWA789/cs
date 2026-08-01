"""历史训练模块单元测试：case_store / labeling / trainer / case_retriever。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.scenario_engine.case_store import (
    save_case,
    save_cases_batch,
    load_cases,
    load_labeled_cases,
    update_labels,
    case_count,
)
from src.scenario_engine.labeling import (
    label_case,
    label_cases_with_horizon,
)
from src.scenario_engine.trainer import (
    train_rule_weights,
    load_rule_weights,
    build_case_index,
    load_case_index,
    FEATURE_KEYS,
)


# ── 测试夹具 ──────────────────────────────────────────────


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    """临时缓存目录。"""
    return tmp_path


def _make_ohlc_df(start_price: float = 100.0, days: int = 100, trend: float = 0.001) -> pd.DataFrame:
    """构造测试用 OHLC DataFrame。"""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    dates = [base + timedelta(days=i) for i in range(days)]
    prices = [start_price * ((1 + trend) ** i) for i in range(days)]
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "close": prices,
    })


def _make_case(case_id: str, good_id: str, ts: str, label: str | None = None) -> dict:
    """构造测试案例。"""
    return {
        "case_id": case_id,
        "good_id": good_id,
        "good_name": f"item_{good_id}",
        "category": "rifle",
        "timestamp": ts,
        "period": "1day",
        "features": {k: float(np.random.rand()) for k in FEATURE_KEYS},
        "kline_score": 0.65,
        "signals": {},
        "duration_bars": 30,
        "label": label,
    }


# ── case_store 测试 ───────────────────────────────────────


class TestCaseStore:
    def test_save_and_load_case(self, tmp_cache: Path):
        """单条保存与加载。"""
        case = _make_case("rifle_1_100", "1", "2024-03-01")
        save_case(case, tmp_cache, "rifle")
        loaded = load_cases(tmp_cache, "rifle")
        assert len(loaded) == 1
        assert loaded[0]["case_id"] == "rifle_1_100"

    def test_save_batch_append(self, tmp_cache: Path):
        """批量追加写。"""
        cases = [_make_case(f"rifle_1_{i}", "1", "2024-03-01") for i in range(5)]
        save_cases_batch(cases, tmp_cache, "rifle")
        save_cases_batch(cases, tmp_cache, "rifle")  # 再写一次
        loaded = load_cases(tmp_cache, "rifle")
        assert len(loaded) == 10

    def test_save_batch_overwrite(self, tmp_cache: Path):
        """覆盖写。"""
        cases = [_make_case("rifle_1_100", "1", "2024-03-01") for _ in range(3)]
        save_cases_batch(cases, tmp_cache, "rifle")
        save_cases_batch(cases[:1], tmp_cache, "rifle", overwrite=True)
        loaded = load_cases(tmp_cache, "rifle")
        assert len(loaded) == 1

    def test_load_labeled_only(self, tmp_cache: Path):
        """load_labeled_cases 仅返回已标注的。"""
        cases = [
            _make_case("c1", "1", "2024-03-01", label="positive"),
            _make_case("c2", "1", "2024-03-08", label=None),
            _make_case("c3", "1", "2024-03-15", label="negative"),
        ]
        save_cases_batch(cases, tmp_cache, "rifle")
        labeled = load_labeled_cases(tmp_cache, "rifle")
        assert len(labeled) == 2

    def test_case_count(self, tmp_cache: Path):
        """统计案例数。"""
        cases = [
            _make_case("c1", "1", "2024-03-01", label="positive"),
            _make_case("c2", "1", "2024-03-08", label=None),
        ]
        save_cases_batch(cases, tmp_cache, "rifle")
        counts = case_count(tmp_cache, "rifle")
        assert counts["total"] == 2
        assert counts["labeled"] == 1
        assert counts["unlabeled"] == 1

    def test_update_labels_preserves_unlabeled(self, tmp_cache: Path):
        """update_labels 保留未标注案例。"""
        cases = [
            _make_case("c1", "1", "2024-03-01", label=None),
            _make_case("c2", "1", "2024-03-08", label=None),
        ]
        save_cases_batch(cases, tmp_cache, "rifle")

        # 模拟标注
        labeled = [{**cases[0], "label": "positive", "future_return_30d": 0.2}]
        update_labels(labeled, tmp_cache, "rifle")

        loaded = load_cases(tmp_cache, "rifle")
        assert len(loaded) == 2
        labels = {c["case_id"]: c["label"] for c in loaded}
        assert labels["c1"] == "positive"
        assert labels["c2"] is None


# ── labeling 测试 ─────────────────────────────────────────


class TestLabeling:
    def test_positive_label_when_strong_rise(self):
        """30 天涨幅 > 15% → positive。"""
        df = _make_ohlc_df(start_price=100, days=60, trend=0.008)  # 涨幅约 60%
        case = _make_case("c1", "1", str(df.iloc[20]["timestamp"]))
        result = label_case(case, df, horizon=30, positive_threshold=0.15)
        assert result["label"] == "positive"
        assert result["future_return_30d"] > 0.15

    def test_negative_label_when_strong_drop(self):
        """30 天跌幅 > 10% → negative。"""
        df = _make_ohlc_df(start_price=100, days=60, trend=-0.006)  # 跌幅约 30%
        case = _make_case("c1", "1", str(df.iloc[20]["timestamp"]))
        result = label_case(case, df, horizon=30, negative_threshold=-0.10)
        assert result["label"] == "negative"

    def test_neutral_label_when_flat(self):
        """横盘 → neutral。"""
        df = _make_ohlc_df(start_price=100, days=60, trend=0.0)  # 不涨不跌
        case = _make_case("c1", "1", str(df.iloc[20]["timestamp"]))
        result = label_case(case, df, horizon=30)
        assert result["label"] == "neutral"

    def test_none_label_when_no_timestamp(self):
        """无时间戳 → label=None。"""
        case = _make_case("c1", "1", "")
        result = label_case(case, _make_ohlc_df())
        assert result["label"] is None

    def test_batch_labeling(self):
        """批量标注。"""
        df = _make_ohlc_df(start_price=100, days=100, trend=0.005)
        cases = [
            _make_case("c1", "1", str(df.iloc[20]["timestamp"])),
            _make_case("c2", "1", str(df.iloc[40]["timestamp"])),
            _make_case("c3", "999", str(df.iloc[20]["timestamp"])),  # 无 OHLC
        ]
        labeled = label_cases_with_horizon(cases, {"1": df}, horizon=30)
        assert labeled[0]["label"] in ("positive", "neutral")
        assert labeled[2]["label"] is None  # 无 OHLC


# ── trainer 测试 ──────────────────────────────────────────


class TestTrainer:
    def test_train_with_sufficient_data(self, tmp_cache: Path):
        """足够数据应训练成功。"""
        # 构造 30 个正样本 + 30 个负样本
        cases = []
        for i in range(30):
            # 正样本：特征值高
            c = _make_case(f"pos_{i}", str(i), "2024-03-01", label="positive")
            c["features"] = {k: 0.8 + np.random.rand() * 0.2 for k in FEATURE_KEYS}
            cases.append(c)
        for i in range(30):
            # 负样本：特征值低
            c = _make_case(f"neg_{i}", str(100 + i), "2024-03-01", label="negative")
            c["features"] = {k: np.random.rand() * 0.2 for k in FEATURE_KEYS}
            cases.append(c)

        result = train_rule_weights(cases, tmp_cache, "rifle")
        assert result["trained"] is True
        assert result["train_size"] == 60
        assert "weights" in result
        assert result["train_accuracy"] >= 0.5

    def test_train_insufficient_data(self, tmp_cache: Path):
        """数据不足应返回 trained=False。"""
        cases = [_make_case(f"c{i}", "1", "2024-03-01", label="positive") for i in range(5)]
        result = train_rule_weights(cases, tmp_cache, "rifle")
        assert result["trained"] is False
        assert result["reason"] == "insufficient_data"

    def test_load_rule_weights(self, tmp_cache: Path):
        """加载已训练权重。"""
        cases = []
        for i in range(30):
            c = _make_case(f"pos_{i}", str(i), "2024-03-01", label="positive")
            c["features"] = {k: 0.8 for k in FEATURE_KEYS}
            cases.append(c)
        for i in range(30):
            c = _make_case(f"neg_{i}", str(100 + i), "2024-03-01", label="negative")
            c["features"] = {k: 0.2 for k in FEATURE_KEYS}
            cases.append(c)

        train_rule_weights(cases, tmp_cache, "rifle")
        loaded = load_rule_weights(tmp_cache, "rifle")
        assert loaded is not None
        assert loaded["trained"] is True
        assert "weights" in loaded

    def test_build_case_index(self, tmp_cache: Path):
        """构建案例索引 Parquet。"""
        cases = []
        for i in range(10):
            c = _make_case(f"c{i}", str(i), "2024-03-01", label="positive")
            c["future_return_30d"] = 0.2
            cases.append(c)

        result = build_case_index(cases, tmp_cache, "rifle")
        assert result["built"] is True
        assert result["case_count"] == 10

        df = load_case_index(tmp_cache, "rifle")
        assert df is not None
        assert len(df) == 10

    def test_build_case_index_no_labeled(self, tmp_cache: Path):
        """无标注案例 → 不构建。"""
        cases = [_make_case("c1", "1", "2024-03-01", label=None)]
        result = build_case_index(cases, tmp_cache, "rifle")
        assert result["built"] is False


# ── llm_explainer 测试 ────────────────────────────────────


from src.scenario_engine.llm_explainer import (
    _build_prompt,
    _fallback_explanation,
    explain_fused,
    is_llm_available,
)


def _make_fused_data(pattern: str = "strong", fused_score: float = 0.75) -> dict:
    """构造双轨融合分析数据。"""
    return {
        "good_id": "12345",
        "period": "1day",
        "fused_score": fused_score,
        "kline_score": 0.7,
        "inventory_score": 0.8,
        "pattern": pattern,
        "phase": "accumulation",
        "duration_bars": 45,
        "inventory_stats": {
            "top3_concentration": 0.65,
            "total_hold": 12000,
            "net_inflow_7d": 1500,
            "active_holder_count": 8,
            "holder_total": 12,
            "team_confidence": 0.55,
        },
        "evidence": ["TOP3 集中度 65%", "近7日净流入 1500", "底部抬高"],
        "kline_signals": {
            "price_position": 0.6,
            "consolidation": 0.7,
        },
    }


class TestLlmExplainer:
    def test_is_llm_available_no_key(self, monkeypatch):
        """无 API key 时 is_llm_available 返回 False。"""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        assert is_llm_available() is False

    def test_build_prompt_contains_key_data(self):
        """prompt 包含核心字段。"""
        data = _make_fused_data()
        prompt = _build_prompt(data)
        assert "12345" in prompt  # good_id
        assert "strong" in prompt  # pattern
        assert "TOP3 集中度" in prompt
        assert "证据链" in prompt

    def test_build_prompt_with_similar_cases(self):
        """prompt 包含历史相似案例（F3: ≥3 才展示）。"""
        data = _make_fused_data()
        # F3 要求 ≥3 才喂 LLM
        cases = [
            {
                "good_name": "AK-47 | 红线",
                "timestamp": "2024-03-15",
                "kline_score": 0.68,
                "future_return_30d": 0.18,
                "max_drawdown_30d": -0.05,
                "label": "positive",
            },
            {
                "good_name": "M4A4 | 咆哮",
                "timestamp": "2024-04-20",
                "kline_score": 0.55,
                "future_return_30d": -0.12,
                "max_drawdown_30d": -0.18,
                "label": "negative",
            },
            {
                "good_name": "AWP | 巨龙传说",
                "timestamp": "2024-05-10",
                "kline_score": 0.62,
                "future_return_30d": 0.05,
                "max_drawdown_30d": -0.03,
                "label": "neutral",
            },
        ]
        prompt = _build_prompt(data, cases)
        assert "AK-47" in prompt
        assert "历史相似案例" in prompt
        # F3: 应包含回撤信息
        assert "回撤" in prompt

    def test_build_prompt_with_few_similar_cases_skipped(self):
        """F3: 相似案例 <3 不展示（避免噪声）。"""
        data = _make_fused_data()
        cases = [
            {
                "good_name": "AK-47 | 红线",
                "timestamp": "2024-03-15",
                "kline_score": 0.68,
                "future_return_30d": 0.18,
                "label": "positive",
            }
        ]
        prompt = _build_prompt(data, cases)
        # 单案例不应展示
        assert "历史相似案例" not in prompt

    def test_fallback_high_score(self):
        """高评分降级模板。"""
        data = _make_fused_data(fused_score=0.75)
        text = _fallback_explanation(data)
        assert "主力吸货信号明确" in text

    def test_fallback_low_score(self):
        """低评分降级模板。"""
        data = _make_fused_data(fused_score=0.2)
        text = _fallback_explanation(data)
        assert "主力出货信号明显" in text

    def test_fallback_no_evidence(self):
        """无证据链时降级模板。"""
        data = {"pattern": "none", "fused_score": 0.4, "evidence": []}
        text = _fallback_explanation(data)
        assert "none" in text

    def test_explain_fused_template_when_no_llm(self, monkeypatch):
        """无 LLM 配置时降级模板。"""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        result = explain_fused(_make_fused_data(), use_llm=True)
        assert result["source"] == "template"
        assert result["explanation"]
        assert result["model"] is None

    def test_explain_fused_forced_template(self):
        """use_llm=False 强制模板。"""
        result = explain_fused(_make_fused_data(), use_llm=False)
        assert result["source"] == "template"

    def test_explain_fused_caches_result(self, monkeypatch):
        """相同输入命中缓存。"""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        data = _make_fused_data()
        first = explain_fused(data, use_llm=False)
        second = explain_fused(data, use_llm=False)
        # 缓存命中：两次返回相同归因
        assert first["explanation"] == second["explanation"]

