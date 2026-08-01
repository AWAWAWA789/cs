import { memo, useMemo } from "react";
import { EChart } from "./EChart";
import type { OhlcBar, Scenario, WavePoint } from "../types/api";
import { formatPrice, formatDateShort } from "../lib/format";

interface ForecastChartProps {
  /** 历史 K 线数据。 */
  ohlc: OhlcBar[];
  /** 情景列表（2-4 条），每条含 wave_sketch 用于生成模拟走势。 */
  scenarios: Scenario[];
  /** 图表高度，默认 420。 */
  height?: number;
}

/** 情景颜色调色板。 */
const SCENARIO_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#f59e0b"];

/** 情景透明度映射（概率越高越不透明）。 */
function scenarioOpacity(probability: number): number {
  // 概率 0.05 → 0.25，概率 0.95 → 0.75
  return Math.max(0.25, Math.min(0.75, 0.25 + probability * 0.5));
}

/** 确定性伪随机生成器（mulberry32）。

 * 用种子代替 ``Math.random()``，使得同一情景在每次重渲染时生成完全相同的
 * 模拟 K 线，避免预测线在屏幕上肉眼可见地抖动（旧实现每次 render 都
 * 重新随机，演示时像数据闪烁/出错）。
 */
function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return function () {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 字符串 → 32 位 hash，用于从情景名生成稳定种子。 */
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (Math.imul(hash, 31) + str.charCodeAt(i)) | 0;
  }
  return hash >>> 0;
}

/**
 * 将 wave_sketch 数据点转换为模拟 K 线数据。
 * 每个点生成一根模拟 K 线：以 price 为中心，用确定性伪随机添加波动模拟 OHLC。
 */
function waveToSimulatedBars(
  wave: WavePoint[],
  lastClose: number,
  seed: number,
): [number, number, number, number][] {
  if (wave.length === 0) return [];

  const rng = mulberry32(seed);
  const bars: [number, number, number, number][] = [];
  let prevPrice = lastClose;

  for (const point of wave) {
    const price = point.price;
    // 模拟波动幅度：基于前一根价格和当前价格的差异
    const volatility = Math.abs(price - prevPrice) * 0.3 + prevPrice * 0.002;
    const open = prevPrice;
    const close = price;
    const high = Math.max(open, close) + volatility * rng();
    const low = Math.min(open, close) - volatility * rng();
    bars.push([open, close, low, high]);
    prevPrice = price;
  }

  return bars;
}

/**
 * 未来走势模拟 K 线组件。
 *
 * 在历史 K 线右侧延伸 2-4 条情景模拟走势，
 * 用不同颜色区分，概率以透明度表示。
 * 当前价位处标注价格数值和点位。
 *
 * 使用 ``memo`` + ``useMemo`` 避免父组件无关重渲染导致 ECharts 全量
 * ``setOption`` 重绘。
 */
export const ForecastChart = memo(function ForecastChart({
  ohlc,
  scenarios,
  height = 420,
}: ForecastChartProps) {
  const option = useMemo(() => {
    if (!ohlc || ohlc.length === 0) return null;

    // 历史数据
    const histDates = ohlc.map((d) => formatDateShort(d.timestamp));
    const histData = ohlc.map((d) => [d.open, d.close, d.low, d.high]);
    const lastClose = ohlc[ohlc.length - 1].close;

    // 为每条情景生成模拟走势数据。种子取自情景名，保证跨渲染稳定。
    const forecastScenarios = scenarios
      .filter((s) => s.wave_sketch.length > 0)
      .map((s, idx) => {
        const color = SCENARIO_COLORS[idx % SCENARIO_COLORS.length];
        const opacity = scenarioOpacity(s.probability);
        const seed = hashString(`${s.name}|${idx}`);
        const simBars = waveToSimulatedBars(s.wave_sketch, lastClose, seed);

        // 生成未来日期标签（沿用历史最后日期 + 序号）
        const futureDates = s.wave_sketch.map((_, i) => `预测${i + 1}`);

        return { scenario: s, color, opacity, simBars, futureDates };
      });

    // 合并日期轴：历史 + 最长的预测序列
    const maxForecastLen = Math.max(0, ...forecastScenarios.map((f) => f.simBars.length));
    const allDates = [
      ...histDates,
      ...Array.from({ length: maxForecastLen }, (_, i) => `预测${i + 1}`),
    ];

    // 分界点（历史数据结束位置）
    const boundaryIdx = histDates.length;

    // 构建 markPoint：当前价位
    const markPoints: unknown[] = [
      {
        coord: [boundaryIdx - 1, lastClose],
        value: `当前\n${formatPrice(lastClose)}`,
        itemStyle: { color: "#6366f1" },
        label: { fontSize: 10, color: "#6366f1", position: "top" },
        symbol: "pin",
        symbolSize: 40,
      },
    ];

    // 为每条情景添加目标价位 markLine
    const markLines: unknown[] = [];
    forecastScenarios.forEach((f) => {
      if (f.scenario.target !== null && f.scenario.target !== undefined) {
        markLines.push({
          yAxis: f.scenario.target,
          lineStyle: { type: "dashed", color: f.color, width: 1, opacity: f.opacity },
          label: {
            formatter: `${f.scenario.name}目标`,
            position: "insideEndTop",
            fontSize: 9,
            color: f.color,
          },
        });
      }
    });

    // 构建 series
    const series: unknown[] = [
      {
        name: "历史K线",
        type: "candlestick",
        data: [...histData, ...Array(maxForecastLen).fill(null)],
        itemStyle: {
          color: "#dc2626",
          color0: "#16a34a",
          borderColor: "#dc2626",
          borderColor0: "#16a34a",
        },
        markPoint: { data: markPoints },
        markLine: {
          silent: true,
          symbol: "none",
          data: [
            // 分界竖线
            {
              xAxis: boundaryIdx - 0.5,
              lineStyle: { type: "dashed", color: "#94a3b8", width: 1.5 },
              label: { formatter: "← 历史 | 预测 →", fontSize: 9, color: "#94a3b8" },
            },
            ...markLines,
          ],
        },
      },
    ];

    // 为每条情景添加模拟走势线
    forecastScenarios.forEach((f) => {
      // 用折线展示模拟走势的收盘价
      const lineData = Array(boundaryIdx).fill(null).concat(
        f.simBars.map((bar) => bar[1]), // 收盘价
      );

      series.push({
        name: `${f.scenario.name} (${(f.scenario.probability * 100).toFixed(0)}%)`,
        type: "line",
        data: lineData,
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { width: 2, color: f.color, opacity: f.opacity },
        itemStyle: { color: f.color, opacity: f.opacity },
        connectNulls: false,
      });
    });

    // 默认展示最近 120 根K线 + 预测
    const visibleBars = 120 + maxForecastLen;
    const totalCount = allDates.length;
    const start =
      totalCount > visibleBars ? Math.round(((totalCount - visibleBars) / totalCount) * 100) : 0;

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
      },
      legend: {
        data: forecastScenarios.map(
          (f) => `${f.scenario.name} (${(f.scenario.probability * 100).toFixed(0)}%)`,
        ),
        bottom: 0,
        textStyle: { fontSize: 10 },
      },
      grid: { left: 60, right: 20, top: 20, bottom: 56 },
      xAxis: {
        type: "category",
        data: allDates,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        axisLabel: { fontSize: 10 },
      },
      yAxis: {
        type: "value",
        scale: true,
        splitLine: { show: true, lineStyle: { type: "dashed" } },
      },
      dataZoom: [
        { type: "inside", start, end: 100 },
        { type: "slider", start, end: 100, height: 18, bottom: 28 },
      ],
      series,
    };
  }, [ohlc, scenarios]);

  if (!option) return null;

  return <EChart option={option} style={{ height, width: "100%" }} notMerge={false} lazyUpdate />;
});
