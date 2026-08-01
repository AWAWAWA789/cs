"""MVP signal generation logic.

The long signal combines three price-action concepts:
1. Uptrend confirmed by higher swing highs and higher swing lows.
2. Price pulling back to a key Fibonacci retracement zone (0.5 or 0.618).
3. A bullish reversal candlestick pattern (Pin Bar or Engulfing).

No volume data is used.
"""

from __future__ import annotations

import pandas as pd

from src.features.candlestick import identify_candlestick_patterns
from src.features.fibonacci import is_near_level, retracement_levels
from src.features.market_regime import add_market_regime_feature
from src.features.signal_quality import add_signal_quality_features, structure_resonance
from src.features.smart_money import add_smart_money_features
from src.features.structure import add_structure_features
from src.features.trend_following import add_trend_following_features


class SignalParams:
    """Parameters controlling signal detection."""

    def __init__(
        self,
        swing_order: int = 2,
        fib_tolerance: float = 0.03,
        target_levels: tuple[str, ...] = ("0.5", "0.618"),
        confirmations: int = 1,
        use_smart_money: bool = True,
        liquidity_grab_buffer: float = 0.005,
        use_trend_following: bool = False,
        trend_strength_threshold: float | None = None,
        adx_period: int = 14,
        use_market_regime_filter: bool = False,
        market_regime_confirmations: int = 4,
        require_structure_resonance: bool = False,
        structure_resonance_buffer: float = 0.03,
        use_signal_quality: bool = False,
        min_signal_quality: float = 0.0,
        quality_trend_weight: float = 0.4,
        quality_structure_weight: float = 0.4,
        quality_confluence_weight: float = 0.2,
    ) -> None:
        self.swing_order = swing_order
        self.fib_tolerance = fib_tolerance
        self.target_levels = target_levels
        self.confirmations = confirmations
        self.use_smart_money = use_smart_money
        self.liquidity_grab_buffer = liquidity_grab_buffer
        self.use_trend_following = use_trend_following
        self.trend_strength_threshold = trend_strength_threshold
        self.adx_period = adx_period
        self.use_market_regime_filter = use_market_regime_filter
        self.market_regime_confirmations = market_regime_confirmations
        self.require_structure_resonance = require_structure_resonance
        self.structure_resonance_buffer = structure_resonance_buffer
        self.use_signal_quality = use_signal_quality
        self.min_signal_quality = min_signal_quality
        self.quality_trend_weight = quality_trend_weight
        self.quality_structure_weight = quality_structure_weight
        self.quality_confluence_weight = quality_confluence_weight


def _last_swing_price(
    series: pd.Series, mask: pd.Series, index: int
) -> float | None:
    """Return the most recent price at or before ``index`` where ``mask`` is True."""
    subset = series.where(mask).iloc[: index + 1]
    if subset.dropna().empty:
        return None
    return float(subset.dropna().iloc[-1])


def _last_swing_index(mask: pd.Series, index: int) -> int | None:
    """Return the index of the most recent True value at or before ``index``."""
    positions = mask.iloc[: index + 1]
    true_positions = positions[positions].index
    if len(true_positions) == 0:
        return None
    return int(true_positions[-1])


def generate_signals(
    df: pd.DataFrame,
    params: SignalParams | None = None,
    *,
    trend_col: str = "trend",
) -> pd.DataFrame:
    """Add long-signal columns to ``df``.

    Adds:
    - ``signal_long``: boolean flag for a long entry signal.
    - ``signal_reason``: human-readable reason when a signal fires.
    - ``swing_low_price``, ``swing_high_price``: anchors used for the signal.

    Args:
        df: OHLC DataFrame. Trend labels are computed with
            ``add_structure_features`` unless ``trend_col`` already exists.
        params: Signal parameters.
        trend_col: Column name to use for trend filtering. Defaults to ``trend``.
            Useful for multi-timeframe analysis where the column may be named
            ``higher_trend``.
    """
    params = params or SignalParams()

    # Always compute swing points on the input timeframe; they are needed by
    # candlestick, Smart Money and risk calculations regardless of whether the
    # trend label comes from a higher timeframe.
    result = add_structure_features(
        df, swing_order=params.swing_order, confirmations=params.confirmations
    )
    # If a higher timeframe trend column is provided, keep it alongside the
    # locally computed swing points.
    if trend_col in df.columns and trend_col != "trend":
        result[trend_col] = df[trend_col].values
    result = identify_candlestick_patterns(result)
    if params.use_smart_money:
        result = add_smart_money_features(
            result, liquidity_grab_buffer=params.liquidity_grab_buffer
        )
    if params.use_trend_following:
        result = add_trend_following_features(
            result,
            trend_strength_threshold=params.trend_strength_threshold,
            adx_period=params.adx_period,
        )
    if params.use_market_regime_filter:
        result = add_market_regime_feature(
            result,
            swing_order=params.swing_order + 1,
            confirmations=params.market_regime_confirmations,
        )

    # Pre-compute diagnostics used by the signal-quality scorer.
    near_fib = pd.Series(False, index=result.index)
    fib_level_name = pd.Series("", index=result.index, dtype=object)
    has_bullish_pattern = pd.Series(False, index=result.index)

    signal_long = pd.Series(False, index=result.index)
    signal_reason = pd.Series("", index=result.index, dtype=object)
    swing_low_prices = pd.Series(dtype=float, index=result.index)
    swing_high_prices = pd.Series(dtype=float, index=result.index)

    for i in range(len(result)):
        if result[trend_col].iloc[i] != 1:
            continue

        if params.use_market_regime_filter:
            regime = result["market_regime"].iloc[i]
            if pd.isna(regime) or regime != "uptrend":
                continue

        low_price = _last_swing_price(result["low"], result["swing_low"], i)
        high_price = _last_swing_price(result["high"], result["swing_high"], i)

        if low_price is None or high_price is None:
            continue

        levels = retracement_levels(low_price, high_price)
        close = result["close"].iloc[i]

        near, level_name, _ = is_near_level(
            close,
            levels,
            tolerance=params.fib_tolerance,
            target_levels=params.target_levels,
        )
        near_fib.iloc[i] = near
        fib_level_name.iloc[i] = level_name

        has_pattern = (
            result["pin_bar_bull"].iloc[i] or result["engulfing_bull"].iloc[i]
        )
        has_bullish_pattern.iloc[i] = has_pattern

        smart_money = False
        smart_money_reason = ""
        if params.use_smart_money:
            if result["liquidity_grab"].iloc[i]:
                smart_money = True
                smart_money_reason = "smart_money_liquidity_grab"
            elif result["order_block"].iloc[i]:
                smart_money = True
                smart_money_reason = "smart_money_order_block"
            elif result["fair_value_gap"].iloc[i]:
                smart_money = True
                smart_money_reason = "smart_money_fvg"

            if smart_money and params.require_structure_resonance:
                resonance = abs(close - low_price) / low_price <= params.structure_resonance_buffer
                if not resonance:
                    smart_money = False
                    smart_money_reason = ""

        trend_following = False
        trend_following_reason = ""
        if params.use_trend_following:
            if result["higher_high_breakout"].iloc[i]:
                trend_following = True
                trend_following_reason = "trend_following_higher_high"
            elif result["breakout_follow_through"].iloc[i]:
                trend_following = True
                trend_following_reason = "trend_following_breakout"

        if (near and has_pattern) or smart_money or trend_following:
            signal_long.iloc[i] = True
            swing_low_prices.iloc[i] = low_price
            swing_high_prices.iloc[i] = high_price

            if near and has_pattern:
                if result["pin_bar_bull"].iloc[i]:
                    pattern_name = "pin_bar"
                else:
                    pattern_name = "engulfing"
                signal_reason.iloc[i] = (
                    f"uptrend_pullback_fib_{level_name}_{pattern_name}"
                )
            elif smart_money:
                signal_reason.iloc[i] = smart_money_reason
            elif trend_following:
                signal_reason.iloc[i] = trend_following_reason

    result["near_fib"] = near_fib
    result["fib_level_name"] = fib_level_name
    result["has_bullish_pattern"] = has_bullish_pattern
    result["signal_long"] = signal_long
    result["signal_reason"] = signal_reason
    result["signal_swing_low"] = swing_low_prices
    result["signal_swing_high"] = swing_high_prices

    if params.use_signal_quality:
        result = add_signal_quality_features(
            result,
            trend_weight=params.quality_trend_weight,
            structure_weight=params.quality_structure_weight,
            confluence_weight=params.quality_confluence_weight,
        )
        if params.min_signal_quality > 0.0:
            quality_mask = result["signal_quality"] >= params.min_signal_quality
            result["signal_long"] = result["signal_long"] & quality_mask
            result["signal_reason"] = result["signal_reason"].where(
                result["signal_long"], ""
            )
            result["signal_swing_low"] = result["signal_swing_low"].where(
                result["signal_long"]
            )
            result["signal_swing_high"] = result["signal_swing_high"].where(
                result["signal_long"]
            )

    return result
