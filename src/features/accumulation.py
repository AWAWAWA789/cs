"""库存吸货特征工程。

基于价格行为（OHLCV）和库存监控数据，计算用于识别主力资金隐蔽建仓行为的
特征向量。核心思路：

1. 量价背离：放量但价格不动（主力压价吸筹）
2. 底部位置：价格处于近期低点附近
3. 波动率收缩：低波动率横盘（蓄势特征）
4. 成交量趋势：成交量温和递增
5. 价格形态：底部抬高（higher lows）

这些特征不依赖成交量时退化为纯价格行为分析；当库存监控数据可用时，
可叠加库存斜率、筹码集中度等维度增强识别。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_divide(a: float | int, b: float | int) -> float:
    """安全除法，分母为零时返回 0。"""
    if b == 0:
        return 0.0
    return float(a) / float(b)


def add_price_position_features(df: pd.DataFrame, lookback: int = 60) -> pd.DataFrame:
    """计算价格位置特征。

    Args:
        df: 含 open/high/low/close 列的 DataFrame。
        lookback: 回看窗口（默认 60 根 K 线）。

    Returns:
        原 df 增加 price_position（0=最低, 1=最高）、distance_to_low 列。
    """
    result = df.copy()
    close = result["close"]

    rolling_low = close.rolling(window=lookback, min_periods=1).min()
    rolling_high = close.rolling(window=lookback, min_periods=1).max()
    rolling_range = (rolling_high - rolling_low).replace(0.0, np.nan)

    # 价格位置：0 = 处于窗口最低点，1 = 处于最高点
    result["price_position"] = np.nan_to_num(
        (close - rolling_low) / rolling_range, nan=0.5
    ).clip(0.0, 1.0)

    # 距低点比例：越小越接近底部
    result["distance_to_low"] = np.nan_to_num(
        (close - rolling_low) / rolling_low, nan=0.0
    ).clip(0.0, 5.0)

    return result


def add_volatility_features(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """计算波动率特征。

    Args:
        df: 含 close 列的 DataFrame。
        window: 波动率计算窗口。

    Returns:
        原 df 增加 atr_percent（ATR 占价格百分比）、volatility_regime 列。
    """
    result = df.copy()
    close = result["close"]

    # True Range
    if all(col in result.columns for col in ("high", "low")):
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                result["high"] - result["low"],
                (result["high"] - prev_close).abs(),
                (result["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
    else:
        tr = close.diff().abs()

    atr = tr.rolling(window=window, min_periods=1).mean()
    result["atr_percent"] = np.nan_to_num(
        atr / close * 100.0, nan=0.0, posinf=0.0, neginf=0.0
    )

    # 波动率体制：低（atr_percent < 1.5）、中（1.5-3.0）、高（>3.0）
    result["volatility_regime"] = pd.cut(
        result["atr_percent"],
        bins=[0, 1.5, 3.0, float("inf")],
        labels=[0, 1, 2],
        include_lowest=True,
    ).astype(float).fillna(1.0)

    return result


def add_volume_features(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """计算成交量特征。

    当成交量数据不可用时（synthetic 数据无 volume 列），跳过并返回原 df。

    Args:
        df: 含 close 列、可选 volume 列的 DataFrame。
        window: 均量计算窗口。

    Returns:
        原 df 增加 volume_ma、volume_ratio、volume_trend 列（如有 volume）。
    """
    if "volume" not in df.columns:
        return df

    result = df.copy()
    vol = result["volume"]

    # 成交量均线
    result["volume_ma"] = vol.rolling(window=window, min_periods=1).mean()

    # 量比：当前成交量 / 均量
    result["volume_ratio"] = np.nan_to_num(
        vol / result["volume_ma"].replace(0.0, np.nan), nan=1.0
    ).clip(0.0, 10.0)

    # 成交量趋势：近 window/2 根 vs 前 window/2 根的均量比
    half = max(1, window // 2)
    recent_vol = vol.rolling(window=half, min_periods=1).mean()
    older_vol = vol.shift(half).rolling(window=half, min_periods=1).mean()
    result["volume_trend"] = np.nan_to_num(
        recent_vol / older_vol.replace(0.0, np.nan), nan=1.0
    ).clip(0.0, 10.0)

    return result


def add_price_divergence_features(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """计算量价背离特征。

    量价背离 = 成交量上升 + 价格波动率下降（主力压价吸筹的典型信号）。
    当无成交量数据时，退化为波动率收缩指标。

    Args:
        df: 含 close 列、可选 volume 列的 DataFrame。
        window: 计算窗口。

    Returns:
        原 df 增加 volume_price_divergence 列。
    """
    result = df.copy()

    # 价格波动率变化率
    returns = result["close"].pct_change()
    vol_now = returns.rolling(window=max(1, window // 2), min_periods=1).std()
    vol_prev = returns.shift(max(1, window // 2)).rolling(
        window=max(1, window // 2), min_periods=1
    ).std()
    vol_change = np.nan_to_num(
        (vol_now - vol_prev) / vol_prev.replace(0.0, np.nan), nan=0.0
    ).clip(-5.0, 5.0)

    if "volume" in result.columns:
        # 成交量变化率
        vol_ma_now = result["volume"].rolling(
            window=max(1, window // 2), min_periods=1
        ).mean()
        vol_ma_prev = result["volume"].shift(max(1, window // 2)).rolling(
            window=max(1, window // 2), min_periods=1
        ).mean()
        vol_change_rate = np.nan_to_num(
            (vol_ma_now - vol_ma_prev) / vol_ma_prev.replace(0.0, np.nan), nan=0.0
        ).clip(-5.0, 5.0)

        # 量价背离 = 成交量上升 + 波动率下降
        # 正值表示量价背离（放量+波动缩小 = 吸货信号）
        result["volume_price_divergence"] = (
            vol_change_rate * (-vol_change)
        ).clip(-5.0, 5.0)
    else:
        # 无成交量时退化为波动率收缩指标
        result["volume_price_divergence"] = (-vol_change).clip(-5.0, 5.0)

    return result


def add_swing_trend_features(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """计算波段趋势特征（底部抬高检测）。

    检测近期 swing low 是否呈递增趋势（底部抬高 = 吸货特征）。

    Args:
        df: 含 high/low/close 列的 DataFrame。
        lookback: 取多少个 swing 点。

    Returns:
        原 df 增加 bottom_rising 列（0-1，越高表示底部抬高越明显）。
    """
    result = df.copy()
    lows = result["low"]
    highs = result["high"]

    # 简化 swing 检测：局部极值
    swing_lows = []
    swing_highs = []
    for i in range(lookback, len(result) - lookback):
        window_low = lows.iloc[i - lookback : i + lookback + 1]
        window_high = highs.iloc[i - lookback : i + lookback + 1]
        if lows.iloc[i] == window_low.min():
            swing_lows.append((i, lows.iloc[i]))
        if highs.iloc[i] == window_high.max():
            swing_highs.append((i, highs.iloc[i]))

    # 底部抬高评分：最近几个 swing low 是否递增
    result["bottom_rising"] = 0.0
    if len(swing_lows) >= 2:
        recent_lows = swing_lows[-3:]  # 取最近 3 个 swing low
        if len(recent_lows) >= 2:
            prices = [p for _, p in recent_lows]
            # 线性回归斜率 > 0 表示底部抬高
            x = np.arange(len(prices), dtype=float)
            y = np.array(prices, dtype=float)
            if len(x) > 1:
                slope = np.polyfit(x, y, 1)[0] if not np.any(np.isnan(y)) else 0.0
                # 归一化到 0-1
                result.loc[result.index[-1], "bottom_rising"] = float(
                    max(0.0, min(1.0, slope * 100))
                )

    # 顶部降低评分（看跌信号，用于对比）
    result["top_lowering"] = 0.0
    if len(swing_highs) >= 2:
        recent_highs = swing_highs[-3:]
        if len(recent_highs) >= 2:
            prices = [p for _, p in recent_highs]
            x = np.arange(len(prices), dtype=float)
            y = np.array(prices, dtype=float)
            if len(x) > 1:
                slope = np.polyfit(x, y, 1)[0] if not np.any(np.isnan(y)) else 0.0
                result.loc[result.index[-1], "top_lowering"] = float(
                    max(0.0, min(1.0, -slope * 100))
                )

    return result


def add_consolidation_features(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """计算横盘整理特征。

    检测价格是否在窄幅区间内震荡（横盘蓄势）。

    Args:
        df: 含 close 列的 DataFrame。
        window: 计算窗口。

    Returns:
        原 df 增加 consolidation_score 列（0-1，越高越横盘）。
    """
    result = df.copy()
    close = result["close"]

    # 振幅 = (最高-最低)/均价
    rolling_high = close.rolling(window=window, min_periods=1).max()
    rolling_low = close.rolling(window=window, min_periods=1).min()
    rolling_mean = close.rolling(window=window, min_periods=1).mean()

    amplitude = np.nan_to_num(
        (rolling_high - rolling_low) / rolling_mean.replace(0.0, np.nan), nan=0.0
    ).clip(0.0, 5.0)

    # 振幅越小，横盘评分越高
    result["consolidation_score"] = (1.0 - amplitude).clip(0.0, 1.0)

    # 横盘持续天数：连续低振幅的 K 线数
    low_amplitude = amplitude < 0.05  # 5% 以下算低振幅
    # 用累计计数
    groups = (~low_amplitude).cumsum()
    result["consolidation_bars"] = low_amplitude.groupby(groups).cumsum()

    return result


def compute_accumulation_features(df: pd.DataFrame) -> pd.DataFrame:
    """计算全部吸货特征。

    输入 DataFrame 需含 open/high/low/close 列，可选 volume 列。
    返回增加所有吸货特征列的 DataFrame。

    特征列表：
    - price_position: 价格在窗口中的位置（0=最低, 1=最高）
    - distance_to_low: 距低点比例
    - atr_percent: ATR 占价格百分比
    - volatility_regime: 波动率体制（0=低, 1=中, 2=高）
    - volume_ma / volume_ratio / volume_trend: 成交量特征（如有 volume）
    - volume_price_divergence: 量价背离指数
    - bottom_rising: 底部抬高评分
    - consolidation_score: 横盘评分
    - consolidation_bars: 横盘持续 K 线数
    """
    result = df.copy()
    result = add_price_position_features(result)
    result = add_volatility_features(result)
    result = add_volume_features(result)
    result = add_price_divergence_features(result)
    result = add_swing_trend_features(result)
    result = add_consolidation_features(result)
    return result


def get_latest_features(df: pd.DataFrame) -> dict[str, float]:
    """获取最新一根 K 线的吸货特征值。

    Args:
        df: 经 compute_accumulation_features 处理后的 DataFrame。

    Returns:
        特征名到值的字典。
    """
    feature_cols = [
        "price_position",
        "distance_to_low",
        "atr_percent",
        "volatility_regime",
        "volume_ratio",
        "volume_trend",
        "volume_price_divergence",
        "bottom_rising",
        "consolidation_score",
        "consolidation_bars",
    ]
    result = {}
    last_row = df.iloc[-1]
    for col in feature_cols:
        if col in df.columns:
            val = last_row[col]
            result[col] = float(val) if not np.isnan(float(val)) else 0.0
    return result
