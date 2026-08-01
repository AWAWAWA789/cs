/**
 * Tree-shaken ECharts wrapper component.
 *
 * Drop-in replacement for ``echarts-for-react``'s default export that binds
 * the pre-configured, tree-shaken ECharts instance from ``lib/echarts``.
 * Callers use ``<EChart option={...} />`` exactly as they would
 * ``<ReactECharts option={...} />``, but the resulting bundle only includes
 * the chart types and components registered in ``lib/echarts`` instead of
 * the full ECharts runtime.
 */
import EChartsReactCore from "echarts-for-react/lib/core";
import type { CSSProperties } from "react";

import { echarts } from "../lib/echarts";

interface EChartProps {
  /** ECharts option object. */
  option: unknown;
  /** Inline style for the chart container (width/height). */
  style?: CSSProperties;
  /** ECharts ``notMerge`` flag. Default ``false``. */
  notMerge?: boolean;
  /** ECharts ``lazyUpdate`` flag. Default ``false``. */
  lazyUpdate?: boolean;
  /** ECharts ``showLoading`` flag. */
  showLoading?: boolean;
  /** Theme name or theme object. */
  theme?: string | Record<string, unknown>;
  /** ``opts`` passed to ``echarts.init``. */
  opts?: Record<string, unknown>;
  /** Callback fired with the echarts instance after init. */
  onChartReady?: (instance: unknown) => void;
  /** Event handlers keyed by event name. */
  onEvents?: Record<string, (...args: unknown[]) => void>;
  /** Class name applied to the container div. */
  className?: string;
}

export function EChart({
  option,
  style,
  notMerge = false,
  lazyUpdate = false,
  showLoading = false,
  theme,
  opts,
  onChartReady,
  onEvents,
  className,
}: EChartProps) {
  return (
    <EChartsReactCore
      echarts={echarts}
      option={option as never}
      notMerge={notMerge}
      lazyUpdate={lazyUpdate}
      showLoading={showLoading}
      theme={theme}
      opts={opts}
      onChartReady={onChartReady as never}
      onEvents={onEvents as never}
      style={style}
      className={className}
    />
  );
}
