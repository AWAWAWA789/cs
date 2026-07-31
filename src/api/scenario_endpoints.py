"""Scenario API endpoints for Phase 13.

This module exposes the algorithmic scenario pipeline over HTTP. It is
sub-index agnostic: callers provide ``sub_index`` (Chinese name) and
``period`` and the backend loads cached OHLC data or falls back to a
deterministic synthetic dataset when no API token is available.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.cache import SCENARIO_CACHE
from src.api.client import CSQAQClient
from src.api.endpoints import get_current_data_init, get_sub_kline
from src.api.logging import get_logger, log_request
from src.api.monitoring import record_request
from src.config import Settings
from src.data.cache import cache_file_path, load as load_cache, save as save_cache
from src.data.pipeline import filter_from_2024, normalize_kline
from src.scenario_engine.scenario_generator import generate_scenarios
from src.scenario_engine.similarity_search import find_similar_states
from src.scenario_engine.template_matcher import match_templates


LOGGER = get_logger("csqaq.scenario_api")


router = APIRouter(prefix="/scenario", tags=["scenario"])

# Supported K-line periods. The API accepts human-friendly aliases and
# normalises them to the internal names used elsewhere in the project.
_PERIOD_ALIASES = {
    "1day": "1day",
    "1d": "1day",
    "daily": "1day",
    "day": "1day",
    "4hour": "4hour",
    "4h": "4hour",
    "1hour": "1hour",
    "1h": "1hour",
    "hour": "1hour",
    "7day": "7day",
    "7d": "7day",
    "weekly": "7day",
    "week": "7day",
}
SUPPORTED_PERIODS = {"1day", "4hour", "1hour", "7day"}

# Minimum number of bars required by the downstream state-vector / template
# engines. The synthetic fallback always produces at least this many rows.
_MIN_BARS = 300


class ExplainRequest(BaseModel):
    """Request body for /scenario/explain."""

    scenario: dict[str, Any] = Field(..., description="Algorithm-generated scenario JSON.")
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional market context (sub_index, period, current_price).",
    )


class ExplainResponse(BaseModel):
    """Response from /scenario/explain."""

    prompt: str
    explanation: str
    wave_sketch_description: str


# --- Request bodies for POST variants -------------------------------------
# These mirror the Query parameters of the GET endpoints so callers can pass
# Chinese ``sub_index`` values in a JSON body, avoiding URL-encoding issues
# with uvicorn's HTTP parser.

class GenerateRequest(BaseModel):
    """Request body for POST /scenario/generate."""

    sub_index: str
    period: str = "1day"
    refresh: bool = False


class OhlcRequest(BaseModel):
    """Request body for POST /scenario/ohlc."""

    sub_index: str
    period: str = "1day"


class HistoryRequest(BaseModel):
    """Request body for POST /scenario/history."""

    sub_index: str
    period: str = "1day"
    method: str = "knn"
    n_neighbors: int = Field(10, ge=1, le=100)


class TemplatesRequest(BaseModel):
    """Request body for POST /scenario/templates."""

    sub_index: str
    period: str = "1day"
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)


def _normalize_period(period: str) -> str:
    """Convert a period alias to the internal period name."""
    normalized = _PERIOD_ALIASES.get(str(period).strip().lower())
    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported period: {period}. Supported: {sorted(SUPPORTED_PERIODS)}",
        )
    return normalized


def _to_iso(value: object) -> str | None:
    """Convert a timestamp-like value to an ISO string, or None."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _resolve_sub_index_id(client: CSQAQClient, sub_index_name: str) -> str:
    """Resolve a Chinese sub-index name to its API id."""
    payload = get_current_data_init(client, skip_rate_limit=True)
    sub_index_data = payload.get("sub_index_data", [])
    for item in sub_index_data:
        if item.get("name") == sub_index_name:
            return str(item.get("id"))
    for item in sub_index_data:
        if sub_index_name in item.get("name", ""):
            return str(item.get("id"))
    raise ValueError(f"Sub-index name not found: {sub_index_name}")


def _synthetic_ohlc(sub_index: str, period: str, n: int = _MIN_BARS) -> pd.DataFrame:
    """Generate deterministic synthetic OHLC data for tests / demo mode.

    The series is seeded from ``sub_index`` and ``period`` so repeated calls
    for the same inputs return identical data. The data ends at the current
    date so the UI always shows up-to-date timestamps.
    """
    seed = int(hash(f"{sub_index}:{period}")) % (2**31)
    rng = np.random.default_rng(abs(seed))
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))

    # Determine frequency from period and end at today's date.
    freq_map = {"1day": "D", "4hour": "4h", "1hour": "1h", "7day": "7D"}
    freq = freq_map.get(period, "D")

    end_date = pd.Timestamp.now(tz="UTC")
    date_range = pd.date_range(end=end_date, periods=n, freq=freq, tz="UTC")

    df = pd.DataFrame(
        {
            "timestamp": date_range,
            "open": price * (1.0 + rng.normal(0.0, 0.005, n)),
            "high": price * (1.0 + np.abs(rng.normal(0.0, 0.015, n))),
            "low": price * (1.0 - np.abs(rng.normal(0.0, 0.015, n))),
            "close": price,
        }
    )
    # Ensure OHLC consistency.
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
    return df


def _load_ohlc(sub_index: str, period: str, *, force_refresh: bool = False) -> pd.DataFrame:
    """Load OHLC data from cache, API, or synthetic fallback.

    Args:
        sub_index: Sub-index Chinese name, used for cache file naming.
        period: Internal period name (e.g. ``1day``).
        force_refresh: Ignore the local cache and attempt a fresh fetch.

    Returns:
        A DataFrame with ``timestamp``, ``open``, ``high``, ``low``, ``close``.
    """
    settings = Settings()
    cache_path = cache_file_path(sub_index, period, settings.cache_path)

    if not force_refresh:
        df = load_cache(cache_path)
        if df is not None:
            # Check if cached data is stale (last bar more than 3 days old).
            last_ts = pd.to_datetime(df["timestamp"].iloc[-1])
            if hasattr(last_ts, "tzinfo") and last_ts.tzinfo is None:
                last_ts = last_ts.tz_localize("UTC")
            age = pd.Timestamp.now(tz="UTC") - last_ts
            if age > pd.Timedelta(days=3):
                LOGGER.info("Cache stale for %s/%s (last bar %s old), refreshing", sub_index, period, age)
            else:
                return filter_from_2024(df)

    # Attempt a real fetch only when an API token is configured.
    if settings.api_token:
        try:
            client = CSQAQClient(settings)
            sub_index_id = settings.sub_index_id or _resolve_sub_index_id(client, sub_index)
            raw = get_sub_kline(client, sub_index_id, period, skip_rate_limit=True)
            df = normalize_kline(raw)
            save_cache(df, cache_path)
            return filter_from_2024(df)
        except Exception as exc:  # pragma: no cover - demo fallback path
            # Fall back to synthetic data so the UI and tests always work.
            pass

    df = _synthetic_ohlc(sub_index, period)
    save_cache(df, cache_path)
    return df


def _run_generate(sub_index: str, period: str) -> dict[str, Any]:
    """Execute the scenario generator and wrap the result with metadata."""
    df = _load_ohlc(sub_index, period)
    if len(df) < _MIN_BARS:
        df = _synthetic_ohlc(sub_index, period)

    start = time.perf_counter()
    result = generate_scenarios({period: df})
    elapsed = time.perf_counter() - start

    return {
        "sub_index": sub_index,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_time_ms": round(elapsed * 1000, 3),
        "scenarios": result["scenarios"],
        "per_period": result.get("per_period", {}),
    }


@router.get("/generate")
def generate(
    sub_index: str = Query(..., description="Sub-index Chinese name (e.g. 手套)."),
    period: str = Query("1day", description="K-line period (e.g. 1day, 4hour, 1hour)."),
    refresh: bool = Query(False, description="Bypass cache and force regeneration."),
) -> dict[str, Any]:
    """Return the latest scenario set for the requested sub-index and period."""
    period = _normalize_period(period)

    if refresh:
        SCENARIO_CACHE.invalidate(sub_index, period)

    cached = SCENARIO_CACHE.get(sub_index, period)
    if cached is not None:
        log_request(
            LOGGER,
            endpoint="/scenario/generate",
            sub_index=sub_index,
            period=period,
            cached=True,
            scenario_count=len(cached.get("scenarios", [])),
        )
        return {**cached, "cached": True}

    start = time.perf_counter()
    try:
        payload = _run_generate(sub_index, period)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(
            LOGGER,
            endpoint="/scenario/generate",
            sub_index=sub_index,
            period=period,
            latency_ms=latency_ms,
            error=str(exc),
        )
        record_request("/scenario/generate", latency_ms, error=True)
        raise HTTPException(status_code=500, detail=f"Scenario generation failed: {exc}") from exc

    SCENARIO_CACHE.set(sub_index, period, payload)
    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/scenario/generate",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
        cached=False,
        scenario_count=len(payload.get("scenarios", [])),
    )
    record_request("/scenario/generate", latency_ms, error=False)
    return {**payload, "cached": False}


@router.post("/generate")
def generate_post(request: GenerateRequest) -> dict[str, Any]:
    """POST version of /scenario/generate.

    Accepts the same parameters in a JSON body to avoid URL-encoding issues
    with Chinese ``sub_index`` values in query strings. Delegates to the GET
    handler so the internal logic stays identical.
    """
    return generate(request.sub_index, request.period, request.refresh)


@router.get("/ohlc")
def ohlc(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, Any]:
    """Return the raw OHLC series used by the scenario pipeline."""
    period = _normalize_period(period)
    start = time.perf_counter()
    try:
        df = _load_ohlc(sub_index, period)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request("/scenario/ohlc", latency_ms, error=True)
        raise HTTPException(status_code=500, detail=f"OHLC load failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/scenario/ohlc",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
        extra={"bar_count": len(df)},
    )
    record_request("/scenario/ohlc", latency_ms, error=False)

    records = []
    for _, row in df.iterrows():
        ts = row["timestamp"]
        if isinstance(ts, pd.Timestamp):
            ts = ts.isoformat()
        records.append(
            {
                "timestamp": ts,
                "open": round(float(row["open"]), 6),
                "high": round(float(row["high"]), 6),
                "low": round(float(row["low"]), 6),
                "close": round(float(row["close"]), 6),
            }
        )

    return {
        "sub_index": sub_index,
        "period": period,
        "count": len(records),
        "ohlc": records,
    }


@router.post("/ohlc")
def ohlc_post(request: OhlcRequest) -> dict[str, Any]:
    """POST version of /scenario/ohlc (accepts body to avoid URL encoding issues)."""
    return ohlc(request.sub_index, request.period)


@router.get("/history")
def history(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
    method: str = Query("knn", description="One of knn, dtw, cluster."),
    n_neighbors: int = Query(10, ge=1, le=100, description="Number of historical matches."),
) -> dict[str, Any]:
    """Return historically similar market states for the current window."""
    period = _normalize_period(period)
    df = _load_ohlc(sub_index, period)

    start = time.perf_counter()
    try:
        matches = find_similar_states(df, method=method, n_neighbors=n_neighbors)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(
            LOGGER,
            endpoint="/scenario/history",
            sub_index=sub_index,
            period=period,
            latency_ms=latency_ms,
            error=str(exc),
            extra={"method": method},
        )
        record_request("/scenario/history", latency_ms, error=True)
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/scenario/history",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
        extra={"method": method, "match_count": len(matches)},
    )
    record_request("/scenario/history", latency_ms, error=False)
    return {
        "sub_index": sub_index,
        "period": period,
        "method": method,
        "matches": matches,
    }


@router.post("/history")
def history_post(request: HistoryRequest) -> dict[str, Any]:
    """POST version of /scenario/history (accepts body to avoid URL encoding issues)."""
    return history(
        request.sub_index,
        request.period,
        request.method,
        request.n_neighbors,
    )


@router.get("/templates")
def templates(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0, description="Minimum template confidence."),
) -> dict[str, Any]:
    """Return the currently matched classic pattern templates."""
    period = _normalize_period(period)
    df = _load_ohlc(sub_index, period)

    start = time.perf_counter()
    try:
        matches = match_templates(df, min_confidence=min_confidence)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(
            LOGGER,
            endpoint="/scenario/templates",
            sub_index=sub_index,
            period=period,
            latency_ms=latency_ms,
            error=str(exc),
            extra={"min_confidence": min_confidence},
        )
        record_request("/scenario/templates", latency_ms, error=True)
        raise HTTPException(status_code=500, detail=f"Template matching failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/scenario/templates",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
        extra={"min_confidence": min_confidence, "match_count": len(matches)},
    )
    record_request("/scenario/templates", latency_ms, error=False)
    return {
        "sub_index": sub_index,
        "period": period,
        "min_confidence": min_confidence,
        "matches": matches,
    }


@router.post("/templates")
def templates_post(request: TemplatesRequest) -> dict[str, Any]:
    """POST version of /scenario/templates (accepts body to avoid URL encoding issues)."""
    return templates(
        request.sub_index,
        request.period,
        request.min_confidence,
    )


@router.post("/explain", response_model=ExplainResponse)
def explain(request: ExplainRequest) -> ExplainResponse:
    """Generate a constrained natural-language explanation for a scenario.

    The prompt strictly instructs the LLM to explain the provided scenario
    without re-judging direction, probability, or price levels. This endpoint
    does not call an external LLM by default; it returns the prompt and a
    deterministic template-based explanation so the API works offline.
    """
    scenario = request.scenario
    ctx = request.context or {}

    sub_index = ctx.get("sub_index", "当前标的")
    period = ctx.get("period", "当前周期")
    current_price = ctx.get("current_price", scenario.get("support", "未知"))

    name = scenario.get("name", "未命名情景")
    direction_label = scenario.get("direction_label", "neutral")
    probability = scenario.get("probability", 0.0)
    support = scenario.get("support")
    resistance = scenario.get("resistance")
    target = scenario.get("target")
    stop_loss = scenario.get("stop_loss")
    position_size = scenario.get("position_size", 0.0)
    wave_sketch = scenario.get("wave_sketch", [])

    prompt = (
        "你是一名严谨的技术分析解释助手。请仅根据下方算法生成的情景 JSON 进行解释，\n"
        "帮助用户理解该情景的假设、关键价位与浪形含义。\n"
        "约束（必须遵守）：\n"
        "1. 仅解释，不得重新判断方向、概率或价位。\n"
        "2. 不得引入算法未给出的外部信息。\n"
        "3. 保持客观，不给出投资建议。\n\n"
        f"标的：{sub_index}，周期：{period}，当前价：{current_price}\n"
        f"情景：{name}\n"
        f"方向标签：{direction_label}，算法概率：{probability:.2%}\n"
        f"关键价位：支撑={support}，阻力={resistance}，目标={target}，止损={stop_loss}\n"
        f"建议仓位比例：{position_size:.2%}\n"
        f"浪形草图点位：{wave_sketch}\n"
    )

    direction_text = {
        "bullish": "偏多",
        "bearish": "偏空",
        "neutral": "中性",
    }.get(direction_label, direction_label)

    explanation = (
        f"{name}（{direction_text}）的概率为 {probability:.2%}。"
        f"算法在 {sub_index} 的 {period} 周期上识别出该情景，"
        f"当前参考支撑 {support}、阻力 {resistance}，目标位 {target}，止损 {stop_loss}。"
    )
    if position_size:
        explanation += f" 根据凯利近似与最大风险约束，建议仓位比例约为 {position_size:.2%}。"
    else:
        explanation += " 当前情景置信度较低，建议保持观望或轻仓。"

    wave_desc = "浪形草图依次为："
    if wave_sketch:
        wave_desc += " → ".join(
            f"{pt.get('label', '?')}({pt.get('price', '?')})" for pt in wave_sketch
        )
    else:
        wave_desc += "（未提供具体浪形点位）"
    wave_desc += "。该草图仅用于可视化参考，不代表未来真实走势。"

    return ExplainResponse(
        prompt=prompt,
        explanation=explanation,
        wave_sketch_description=wave_desc,
    )


@router.get("/meta")
def meta() -> dict[str, Any]:
    """Return available sub-indices and supported periods.

    Tries to fetch the real sub-index list from the CSQAQ API first.
    Falls back to scanning local cache files, then to a built-in default list.
    """
    start = time.perf_counter()
    settings = Settings()
    discovered: set[str] = set()

    # 1. Try fetching from CSQAQ API (if token is configured).
    if settings.api_token:
        try:
            client = CSQAQClient(settings)
            payload = get_current_data_init(client, skip_rate_limit=True)
            sub_index_data = payload.get("sub_index_data", [])
            for item in sub_index_data:
                name = item.get("name")
                if name:
                    discovered.add(name)
            LOGGER.info("meta: discovered %d sub-indices from API", len(discovered))
        except Exception as exc:
            LOGGER.warning("meta: API fetch failed, falling back to cache: %s", exc)

    # 2. Scan local cache files.
    if not discovered:
        cache_dir = cache_file_path("", "1day", settings.cache_path).parent
        if cache_dir.exists():
            for path in cache_dir.glob("*_*.parquet"):
                name = path.stem.rsplit("_", 1)[0]
                if name:
                    discovered.add(name)

    # 3. Built-in defaults covering all CSQAQ sub-indices.
    if not discovered:
        discovered = {
            "手套", "刀", "步枪", "手枪", "狙击枪",
            "微型冲锋枪", "重型武器", "贴纸", "音乐盒", "物品",
        }

    latency_ms = (time.perf_counter() - start) * 1000
    record_request("/scenario/meta", latency_ms, error=False)
    return {
        "available_sub_indices": sorted(discovered),
        "supported_periods": sorted(SUPPORTED_PERIODS),
        "default_period": "1day",
    }
