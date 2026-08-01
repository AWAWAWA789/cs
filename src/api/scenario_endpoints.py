"""Scenario API endpoints for Phase 13.

This module exposes the algorithmic scenario pipeline over HTTP. It is
sub-index agnostic: callers provide ``sub_index`` (Chinese name) and
``period`` and the backend loads cached OHLC data or falls back to a
deterministic synthetic dataset when no API token is available.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.cache import SCENARIO_CACHE, TTLCache
from src.api.client import CSQAQClient
from src.api.endpoints import get_current_data_init, get_sub_kline
from src.api.logging import get_logger, log_request
from src.api.monitoring import record_request
from src.config import Settings
from src.data.cache import (
    cache_file_path,
    invalidate_mem_cache,
    load_cached as load_cache,
    save as save_cache,
)
from src.data.pipeline import filter_from_2024, normalize_kline
from src.scenario_engine.scenario_generator import generate_scenarios
from src.scenario_engine.similarity_search import find_similar_states
from src.scenario_engine.template_matcher import match_templates


LOGGER = get_logger("csqaq.scenario_api")


router = APIRouter(prefix="/scenario", tags=["scenario"])

# Response-level caches for /history, /templates, /meta. These endpoints do
# not mutate state and their inputs are bounded, so we can cache the entire
# serialisable response for a short TTL. ``/scenario/generate`` already has
# its own dedicated ScenarioCache; the caches below mirror that pattern.
HISTORY_CACHE: TTLCache = TTLCache(ttl_seconds=120.0)
TEMPLATES_CACHE: TTLCache = TTLCache(ttl_seconds=120.0)
META_CACHE: TTLCache = TTLCache(ttl_seconds=60.0)

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
    for the same inputs return identical data — including across process
    restarts. The data ends at the current date so the UI always shows
    up-to-date timestamps.
    """
    # Use a stable hash (sha256) so the seed does not depend on Python's
    # randomized PYTHONHASHSEED, which would otherwise make the synthetic
    # series change after every server restart.
    digest = hashlib.sha256(f"{sub_index}:{period}".encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2**31)
    rng = np.random.default_rng(seed)
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


def _load_ohlc(
    sub_index: str, period: str, *, force_refresh: bool = False
) -> tuple[pd.DataFrame, str]:
    """Load OHLC data from cache, API, or synthetic fallback.

    Args:
        sub_index: Sub-index Chinese name, used for cache file naming.
        period: Internal period name (e.g. ``1day``).
        force_refresh: Ignore the local cache and attempt a fresh fetch.

    Returns:
        ``(df, data_source)`` where ``df`` has columns ``timestamp``,
        ``open``, ``high``, ``low``, ``close`` and ``data_source`` is one of
        ``"real"`` (fresh from API or fresh cache), ``"stale_cache"`` (cached
        data older than the freshness window, used as fallback) or
        ``"synthetic"`` (deterministic demo data — never persisted as real
        cache, so downstream endpoints can flag it to the UI).
    """
    settings = Settings()
    cache_path = cache_file_path(sub_index, period, settings.cache_path)

    # Drop any in-memory parquet entry when the caller explicitly asked for
    # a refresh — otherwise the TTL layer would mask the freshly fetched data.
    if force_refresh:
        invalidate_mem_cache(cache_path)

    # Load existing cache (may be stale but still usable as fallback).
    cached_df: pd.DataFrame | None = None
    if not force_refresh:
        cached_df = load_cache(cache_path)
        if cached_df is not None:
            # Check if cached data is fresh (last bar within 3 days).
            last_ts = pd.to_datetime(cached_df["timestamp"].iloc[-1])
            if hasattr(last_ts, "tzinfo") and last_ts.tzinfo is None:
                last_ts = last_ts.tz_localize("UTC")
            age = pd.Timestamp.now(tz="UTC") - last_ts
            if age <= pd.Timedelta(days=3):
                return filter_from_2024(cached_df), "real"
            LOGGER.info("Cache stale for %s/%s (last bar %s old), refreshing", sub_index, period, age)

    # Attempt a real fetch only when an API token is configured.
    if settings.api_token:
        try:
            client = CSQAQClient(settings)
            sub_index_id = settings.sub_index_id or _resolve_sub_index_id(client, sub_index)
            raw = get_sub_kline(client, sub_index_id, period, skip_rate_limit=True)
            df = normalize_kline(raw)
            save_cache(df, cache_path)  # also invalidates the in-memory entry
            return filter_from_2024(df), "real"
        except Exception as exc:
            LOGGER.warning("API fetch failed for %s/%s: %s", sub_index, period, exc)
            # If we have stale cached data, return it instead of synthetic data.
            if cached_df is not None:
                LOGGER.info("Falling back to stale cache for %s/%s", sub_index, period)
                return filter_from_2024(cached_df), "stale_cache"

    # Only use synthetic data when no cached data exists at all. Synthetic
    # data is NOT persisted to the real cache path — otherwise the freshness
    # check above would treat it as fresh real data on the next call.
    df = _synthetic_ohlc(sub_index, period)
    return df, "synthetic"


def _run_generate(sub_index: str, period: str) -> dict[str, Any]:
    """Execute the scenario generator and wrap the result with metadata."""
    df, data_source = _load_ohlc(sub_index, period)
    if len(df) < _MIN_BARS:
        df = _synthetic_ohlc(sub_index, period)
        data_source = "synthetic"

    start = time.perf_counter()
    result = generate_scenarios({period: df})
    elapsed = time.perf_counter() - start

    return {
        "sub_index": sub_index,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_time_ms": round(elapsed * 1000, 3),
        "data_source": data_source,
        "scenarios": result["scenarios"],
        "per_period": result.get("per_period", {}),
    }


def _history_cache_key(sub_index: str, period: str, method: str, n_neighbors: int) -> str:
    """Build a stable cache key for the ``/history`` response cache."""
    return f"history|{sub_index}|{period}|{method}|{n_neighbors}"


def _templates_cache_key(sub_index: str, period: str, min_confidence: float) -> str:
    """Build a stable cache key for the ``/templates`` response cache."""
    # Round to 2 decimals so 0.5 and 0.5001 collapse to the same entry — the
    # caller-visible result is identical for any finer granularity.
    return f"templates|{sub_index}|{period}|{round(min_confidence, 2)}"


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
        # Refresh must also drop the derived response caches so callers see
        # the freshly regenerated similarity / template matches. These have
        # short TTLs anyway, but refresh is rare so a full clear is cheap.
        HISTORY_CACHE.invalidate_all()
        TEMPLATES_CACHE.invalidate_all()

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
        df, data_source = _load_ohlc(sub_index, period)
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

    # Vectorised serialisation — ``df.iterrows()`` was the slow path here:
    # each row materialised a Series and was boxed back into Python floats.
    # Pulling the columns as numpy arrays and converting the timestamp
    # column via ``tolist()`` (which returns Timestamp objects directly,
    # without per-row Series boxing) avoids the per-row overhead for the
    # typical 300-1000 bar payloads.
    #
    # Timestamps keep the canonical ``isoformat()`` output (e.g.
    # ``2024-01-01T00:00:00+00:00``) so downstream consumers — including the
    # frontend — see the exact same string format as before.
    timestamps = [
        t.isoformat() if hasattr(t, "isoformat") else str(t)
        for t in df["timestamp"].tolist()
    ]

    opens = np.round(df["open"].to_numpy(dtype=float), 6)
    highs = np.round(df["high"].to_numpy(dtype=float), 6)
    lows = np.round(df["low"].to_numpy(dtype=float), 6)
    closes = np.round(df["close"].to_numpy(dtype=float), 6)
    # 成交量列可能不存在（synthetic 数据无 v 字段）
    volumes = df["volume"].to_numpy(dtype=float) if "volume" in df.columns else None

    records = []
    for i, ts in enumerate(timestamps):
        rec = {
            "timestamp": ts,
            "open": float(opens[i]),
            "high": float(highs[i]),
            "low": float(lows[i]),
            "close": float(closes[i]),
        }
        if volumes is not None:
            rec["volume"] = float(volumes[i])
        records.append(rec)

    return {
        "sub_index": sub_index,
        "period": period,
        "count": len(records),
        "data_source": data_source,
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
    cache_key = _history_cache_key(sub_index, period, method, n_neighbors)
    cached = HISTORY_CACHE.get(cache_key)
    if cached is not None:
        log_request(
            LOGGER,
            endpoint="/scenario/history",
            sub_index=sub_index,
            period=period,
            cached=True,
            extra={"method": method},
        )
        return {**cached, "cached": True}

    df, data_source = _load_ohlc(sub_index, period)

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
    payload = {
        "sub_index": sub_index,
        "period": period,
        "method": method,
        "data_source": data_source,
        "matches": matches,
    }
    HISTORY_CACHE.set(cache_key, payload)
    return {**payload, "cached": False}


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
    cache_key = _templates_cache_key(sub_index, period, min_confidence)
    cached = TEMPLATES_CACHE.get(cache_key)
    if cached is not None:
        log_request(
            LOGGER,
            endpoint="/scenario/templates",
            sub_index=sub_index,
            period=period,
            cached=True,
            extra={"min_confidence": min_confidence},
        )
        return {**cached, "cached": True}

    df, data_source = _load_ohlc(sub_index, period)

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
    payload = {
        "sub_index": sub_index,
        "period": period,
        "min_confidence": min_confidence,
        "data_source": data_source,
        "matches": matches,
    }
    TEMPLATES_CACHE.set(cache_key, payload)
    return {**payload, "cached": False}


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

    Cached for 60s: the sub-index list rarely changes and a cold ``meta``
    call may hit the API or scan the cache directory, both of which add
    latency that the UI does not need to pay on every page load.
    """
    cached = META_CACHE.get("meta")
    if cached is not None:
        record_request("/scenario/meta", 0.0, error=False)
        return cached

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
    payload = {
        "available_sub_indices": sorted(discovered),
        "supported_periods": sorted(SUPPORTED_PERIODS),
        "default_period": "1day",
    }
    META_CACHE.set("meta", payload)
    return payload
