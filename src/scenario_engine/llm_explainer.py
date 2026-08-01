"""LLM 归因解释模块。

把双轨特征 + 历史相似案例 + 库存证据喂给大模型，输出人话归因：
"该品近7天 TOP3 主力合计加仓 1,200 件，K线呈现缩量横盘+底部抬高。
与 2024-03 的 AK-47 红线吸货模式相似度 87%，那次后续 30 天涨了 18%。
判断：主力隐蔽吸货，置信度 0.78。"

设计：
1. **provider 无关**：支持 OpenAI 兼容 API（含 DeepSeek/通义/Kimi 等），可扩展
2. **纯函数 + 容错**：LLM 不可用时降级为模板拼接（复用现有 _generate_description）
3. **token 控制**：prompt 严格约束输出格式与长度
4. **缓存**：相同输入 5 分钟缓存
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.api.cache import TTLCache
from src.api.logging import get_logger

LOGGER = get_logger("csqaq.llm_explainer")

# LLM 归因结果缓存（10 分钟）
_LLM_CACHE = TTLCache(ttl_seconds=600.0)


def _get_llm_config() -> dict[str, str]:
    """从环境变量读取 LLM 配置。

    支持的变量：
    - LLM_API_KEY: API key（必需）
    - LLM_BASE_URL: OpenAI 兼容 API base URL（默认 https://api.deepseek.com/v1）
    - LLM_MODEL: 模型名（默认 deepseek-chat）
    """
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
    }


def is_llm_available() -> bool:
    """检查 LLM 是否可用（配置了 API key）。"""
    return bool(_get_llm_config()["api_key"])


def _build_prompt(
    fused_data: dict[str, Any],
    similar_cases: list[dict[str, Any]] | None = None,
) -> str:
    """构建 LLM prompt（F3 增强：双轨对比 + 校准要求）。

    F3 升级：
    - 相似案例 ≥3 才喂 LLM（避免噪声，由 explain_fused 控制）
    - prompt 增加双轨对比结构化模板
    - 要求 LLM 输出置信度时基于历史命中率校准
    """
    parts = [
        "你是 CS:GO 饰品市场的主力资金分析师。基于以下双轨吸货分析数据，给出简洁归因。",
        "",
        "## 当前饰品分析",
        f"- good_id: {fused_data.get('good_id', '')}",
        f"- 周期: {fused_data.get('period', '')}",
        f"- 融合评分: {fused_data.get('fused_score', 0)}",
        f"- K线评分: {fused_data.get('kline_score', 0)}",
        f"- 库存评分: {fused_data.get('inventory_score', 0)}",
        f"- 融合模式: {fused_data.get('pattern', '')}",
        f"- 阶段: {fused_data.get('phase', '')}",
        f"- 持续K线数: {fused_data.get('duration_bars', 0)}",
    ]

    # F3: 数据源透明化
    feature_mode = fused_data.get("feature_mode", "")
    weights_source = fused_data.get("weights_source", "")
    confidence = fused_data.get("confidence", "")
    if feature_mode or weights_source:
        parts.append("")
        parts.append("## 数据源与置信度")
        if feature_mode:
            mode_desc = {"FULL": "完整OHLC（6项规则）", "CLOSE_ONLY": "仅收盘价（4项规则降级）",
                         "DEGRADED": "数据不足"}.get(feature_mode, feature_mode)
            parts.append(f"- K线数据模式: {feature_mode} ({mode_desc})")
        if weights_source:
            parts.append(f"- 权重来源: {weights_source} ({'训练产物' if weights_source == 'trained' else '经验值'})")
        if confidence != "":
            parts.append(f"- 系统置信度: {confidence}")

    # 库存统计
    inv_stats = fused_data.get("inventory_stats", {})
    if inv_stats:
        parts.extend([
            "",
            "## 库存行为数据",
            f"- TOP3 集中度: {inv_stats.get('top3_concentration', 0)}",
            f"- 总持仓量: {inv_stats.get('total_hold', 0)}",
            f"- 近7日净流入: {inv_stats.get('net_inflow_7d', 0)}",
            f"- 活跃主力: {inv_stats.get('active_holder_count', 0)}/{inv_stats.get('holder_total', 0)}",
        ])
        tc = inv_stats.get("team_confidence")
        if tc is not None:
            parts.append(f"- 团队置信度: {tc}")

    # 证据链
    evidence = fused_data.get("evidence", [])
    if evidence:
        parts.extend(["", "## 证据链"])
        for e in evidence:
            parts.append(f"- {e}")

    # F3: 历史相似案例（≥3 才展示，避免单案例噪声）
    if similar_cases and len(similar_cases) >= 3:
        parts.extend(["", "## 历史相似案例（top-3）"])
        for i, c in enumerate(similar_cases[:3], 1):
            ret = c.get("future_return_30d")
            ret_str = f"{ret*100:.1f}%" if ret is not None else "未知"
            dd = c.get("max_drawdown_30d")
            dd_str = f"{dd*100:.1f}%" if dd is not None else "未知"
            inv_s = c.get("inventory_score", 0)
            fused_s = c.get("fused_score", c.get("kline_score", 0))
            parts.append(
                f"{i}. {c.get('good_name', '')} ({c.get('timestamp', '')[:10]}) "
                f"融合 {fused_s:.2f}/K线 {c.get('kline_score', 0):.2f}/库存 {inv_s:.2f} "
                f"→ 后30天 {ret_str} (回撤 {dd_str}) [{c.get('label', '')}]"
            )

    # K线子分
    kline_signals = fused_data.get("kline_signals", {})
    if kline_signals:
        parts.extend(["", "## K线子分明细"])
        for k, v in kline_signals.items():
            try:
                parts.append(f"- {k}: {float(v):.3f}")
            except (TypeError, ValueError):
                parts.append(f"- {k}: {v}")

    parts.extend([
        "",
        "## 任务",
        "用一段话（不超过 150 字）给出归因：",
        "1. 主力在做什么（吸货/出货/观望）",
        "2. K线与库存是否相互印证（双轨一致性）",
        "3. 如有相似案例，参考历史走势给出预期",
        "4. 给出置信度判断（高/中/低），并说明依据：",
        "   - 高：双轨一致 + 相似案例命中率 ≥60%",
        "   - 中：单轨明显或相似案例命中 40-60%",
        "   - 低：双轨矛盾或无相似案例",
        "",
        "直接输出归因文本，不要加标题或分点。",
    ])

    return "\n".join(parts)


def _call_llm(prompt: str, config: dict[str, str]) -> str | None:
    """调用 OpenAI 兼容 API。

    使用 httpx 同步调用（端点内 asyncio.to_thread 包裹）。
    失败时返回 None，由调用方降级。
    """
    try:
        import httpx
    except ImportError:
        LOGGER.warning("httpx not available, LLM call skipped")
        return None

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "你是饰品市场主力资金分析专家，输出简洁专业。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 300,
        "temperature": 0.3,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{config['base_url']}/chat/completions",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() if content else None
    except Exception as exc:
        LOGGER.warning("LLM call failed: %s", exc)
        return None


def _fallback_explanation(fused_data: dict[str, Any]) -> str:
    """LLM 不可用时的模板降级（复用证据链拼接）。"""
    evidence = fused_data.get("evidence", [])
    if not evidence:
        pattern = fused_data.get("pattern", "none")
        return f"双轨融合模式: {pattern}，融合评分 {fused_data.get('fused_score', 0):.2f}。"

    # 取前 3 条证据拼接
    parts = evidence[:3]
    score = fused_data.get("fused_score", 0)
    if score >= 0.6:
        parts.append("综合判断: 主力吸货信号明确。")
    elif score <= 0.3:
        parts.append("综合判断: 主力出货信号明显。")
    else:
        parts.append("综合判断: 信号中性，需持续观察。")
    return "。".join(parts) + "。"


def explain_fused(
    fused_data: dict[str, Any],
    similar_cases: list[dict[str, Any]] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """对双轨融合分析结果生成 LLM 归因。

    Args:
        fused_data: /accumulation/analyze-fused 的返回数据
        similar_cases: 历史相似案例（可选，来自 case_retriever）
        use_llm: 是否调用 LLM（False 时强制降级模板）

    Returns:
        {
            "explanation": str,        # 归因文本
            "source": "llm" | "template",  # 来源
            "model": str | None,      # LLM 模型名（llm 时）
            "prompt": str,            # 完整 prompt（调试用）
        }
    """
    good_id = fused_data.get("good_id", "")
    cache_key = f"explain:{good_id}:{fused_data.get('fused_score', 0)}:{fused_data.get('pattern', '')}"
    cached = _LLM_CACHE.get(cache_key)
    if cached is not None:
        return {**cached, "source": cached["source"]}

    prompt = _build_prompt(fused_data, similar_cases)

    # 尝试 LLM
    if use_llm and is_llm_available():
        config = _get_llm_config()
        explanation = _call_llm(prompt, config)
        if explanation:
            result = {
                "explanation": explanation,
                "source": "llm",
                "model": config["model"],
                "prompt": prompt,
            }
            _LLM_CACHE.set(cache_key, result)
            return result
        LOGGER.info("LLM call failed, falling back to template")

    # 降级模板
    explanation = _fallback_explanation(fused_data)
    result = {
        "explanation": explanation,
        "source": "template",
        "model": None,
        "prompt": prompt,
    }
    _LLM_CACHE.set(cache_key, result)
    return result
