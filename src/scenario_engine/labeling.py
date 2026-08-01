"""案例标注模块（事后回看生成标签）。

对每个案例，从其分析时点起，回看 horizon 天的价格走势：
- 涨幅 > positive_threshold → positive（吸货确认）
- 跌幅 > negative_threshold → negative（误判）
- 否则 → neutral

标签规则可调，默认：30 天涨幅 > 15% = positive，跌幅 > 10% = negative。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from src.api.logging import get_logger

LOGGER = get_logger("csqaq.labeling")

DEFAULT_HORIZON = 30
DEFAULT_POSITIVE = 0.15  # 30 天涨幅 > 15%
DEFAULT_NEGATIVE = -0.10  # 跌幅 > 10%


def _parse_timestamp(ts: Any) -> datetime | None:
    """解析案例时间戳（兼容 ISO 字符串/Unix 秒/毫秒）。"""
    if ts is None or ts == "":
        return None
    if isinstance(ts, datetime):
        return ts
    # Unix 时间戳
    try:
        v = float(ts)
        if v > 1e12:
            v = v / 1000.0
        return datetime.fromtimestamp(v, tz=datetime.now().astimezone().tzinfo)
    except (TypeError, ValueError):
        pass
    # ISO 字符串
    try:
        s = str(ts).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _find_closest_row(df: pd.DataFrame, target_ts: datetime) -> int:
    """在 df 中找到最接近 target_ts 的行索引。"""
    if "timestamp" not in df.columns or len(df) == 0:
        return -1
    ts_series = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if ts_series.isna().all():
        return -1
    target = pd.Timestamp(target_ts)
    if target.tzinfo is None:
        target = target.tz_localize("UTC")
    diffs = (ts_series - target).abs()
    return int(diffs.idxmin())


def label_case(
    case: dict[str, Any],
    ohlc_df: pd.DataFrame,
    horizon: int = DEFAULT_HORIZON,
    positive_threshold: float = DEFAULT_POSITIVE,
    negative_threshold: float = DEFAULT_NEGATIVE,
) -> dict[str, Any]:
    """为单个案例生成标签。

    Args:
        case: 案例字典，需含 timestamp 与 good_id
        ohlc_df: 该单品的完整 OHLC DataFrame
        horizon: 回看窗口（天）
        positive_threshold: 正样本涨幅阈值
        negative_threshold: 负样本跌幅阈值（负数）

    Returns:
        更新后的案例字典，增加 label / future_return_{horizon}d / max_drawdown 字段
    """
    ts = _parse_timestamp(case.get("timestamp"))
    if ts is None or ohlc_df is None or len(ohlc_df) == 0:
        case["label"] = None
        case["future_return_30d"] = None
        case["max_drawdown_30d"] = None
        return case

    entry_idx = _find_closest_row(ohlc_df, ts)
    if entry_idx < 0 or entry_idx >= len(ohlc_df) - 1:
        case["label"] = None
        return case

    entry_close = float(ohlc_df.iloc[entry_idx]["close"])
    if entry_close <= 0:
        case["label"] = None
        return case

    # 取 horizon 天后的窗口
    end_idx = min(entry_idx + horizon, len(ohlc_df) - 1)
    if end_idx <= entry_idx:
        case["label"] = None
        return case

    future_window = ohlc_df.iloc[entry_idx + 1:end_idx + 1]
    if len(future_window) == 0:
        case["label"] = None
        return case

    future_close = float(future_window.iloc[-1]["close"])
    future_return = (future_close - entry_close) / entry_close

    # 最大回撤
    cummax = future_window["close"].cummax()
    drawdown = (future_window["close"] - cummax) / cummax
    max_drawdown = float(drawdown.min()) if len(drawdown) > 0 else 0.0

    # 标注
    if future_return >= positive_threshold:
        label = "positive"
    elif future_return <= negative_threshold:
        label = "negative"
    else:
        label = "neutral"

    case["label"] = label
    case[f"future_return_{horizon}d"] = round(future_return, 4)
    case[f"max_drawdown_{horizon}d"] = round(max_drawdown, 4)
    case["labeled_at"] = datetime.now(datetime.now().astimezone().tzinfo).isoformat()

    return case


def label_cases_with_horizon(
    cases: list[dict[str, Any]],
    ohlc_cache: dict[str, pd.DataFrame],
    horizon: int = DEFAULT_HORIZON,
    positive_threshold: float = DEFAULT_POSITIVE,
    negative_threshold: float = DEFAULT_NEGATIVE,
) -> list[dict[str, Any]]:
    """批量标注案例。

    Args:
        cases: 案例列表
        ohlc_cache: {good_id: OHLC DataFrame} 缓存
        horizon: 回看窗口
        positive_threshold / negative_threshold: 标签阈值

    Returns:
        标注后的案例列表
    """
    labeled: list[dict[str, Any]] = []
    skipped = 0
    for case in cases:
        good_id = case.get("good_id")
        df = ohlc_cache.get(good_id) if good_id else None
        if df is None:
            case["label"] = None
            skipped += 1
            labeled.append(case)
            continue
        labeled_case = label_case(
            case, df, horizon, positive_threshold, negative_threshold,
        )
        labeled.append(labeled_case)

    LOGGER.info(
        "labeled %d cases (horizon=%d): %d skipped (no OHLC)",
        len(labeled), horizon, skipped,
    )
    return labeled
