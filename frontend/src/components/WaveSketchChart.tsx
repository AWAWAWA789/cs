import { memo, useMemo } from "react";
import { EChart } from "./EChart";
import type { WavePoint } from "../types/api";
import { formatPrice } from "../lib/format";

interface WaveSketchChartProps {
  /** 波段数据点列表。 */
  data: WavePoint[];
  /** 情景名称，用于图表标题。 */
  title?: string;
  /** 情景方向标签，用于颜色。 */
  direction?: "bullish" | "bearish" | "neutral";
  /** 当前价格（可选），在图中标注为虚线。 */
  currentPrice?: number | null;
  /** 图表高度，默认 200。 */
  height?: number;
}

/** 方向到颜色的映射。 */
const DIRECTION_COLORS: Record<string, string> = {
  bullish: "#16a34a",
  bearish: "#dc2626",
  neutral: "#f59e0b",
};

/**
 * 波段概览波形图组件。
 *
 * 将 scenario.wave_sketch 数据渲染为折线波形图，
 * 支持标注当前价格位置。
 *
 * 使用 ``memo`` + ``useMemo`` 避免父组件无关重渲染导致 ECharts 全量
 * ``setOption`` 重绘——情景卡片在父组件每次刷新 isStale 时都会重渲染，
 * 若 option 每次重建会触发肉眼可见的图表闪烁。
 */
export const WaveSketchChart = memo(function WaveSketchChart({
  data,
  title,
  direction = "neutral",
  currentPrice,
  height = 200,
}: WaveSketchChartProps) {
  const option = useMemo(() => {
    if (!data || data.length === 0) return null;

    const labels = data.map((d) => d.label);
    const prices = data.map((d) => d.price);
    const color = DIRECTION_COLORS[direction] ?? DIRECTION_COLORS.neutral;

    const markLines: unknown[] = [];
    if (currentPrice !== null && currentPrice !== undefined) {
      markLines.push({
        yAxis: currentPrice,
        lineStyle: { type: "dashed", color: "#6366f1", width: 1.5 },
        label: {
          formatter: `当前 ${formatPrice(currentPrice)}`,
          position: "insideEndTop",
          fontSize: 10,
          color: "#6366f1",
        },
      });
    }

    return {
      title: title
        ? {
            text: title,
            left: "center",
            textStyle: { fontSize: 12, fontWeight: 500, color: "#64748b" },
          }
        : undefined,
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: number) => formatPrice(v),
      },
      grid: { left: 60, right: 20, top: title ? 36 : 16, bottom: 28 },
      xAxis: {
        type: "category",
        data: labels,
        boundaryGap: false,
        axisLabel: { fontSize: 10 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { fontSize: 10 },
        splitLine: { show: true, lineStyle: { type: "dashed" } },
      },
      series: [
        {
          type: "line",
          data: prices,
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { width: 2, color },
          itemStyle: { color },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: `${color}40` },
                { offset: 1, color: `${color}00` },
              ],
            },
          },
          markLine:
            markLines.length > 0 ? { silent: true, data: markLines } : undefined,
        },
      ],
    };
  }, [data, title, direction, currentPrice]);

  if (!option) return null;

  return (
    <EChart option={option} style={{ height, width: "100%" }} notMerge={false} lazyUpdate />
  );
});
