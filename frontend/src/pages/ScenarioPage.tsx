import { useRef, useState } from "react";
import { Card } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { SubIndexSelector } from "../components/Selector";
import { WaveSketchChart } from "../components/WaveSketchChart";
import { ForecastChart } from "../components/ForecastChart";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import {
  formatPercent,
  formatPrice,
  formatDate,
  formatDuration,
  formatDateShort,
  directionColor,
  directionLabel,
} from "../lib/format";
import type { Scenario, OhlcBar } from "../types/api";
import { useGlobalStore } from "../store/globalStore";
import ReactECharts from "echarts-for-react";

/** 方向标签到 Badge 颜色变体的映射。 */
const DIRECTION_BADGE: Record<Scenario["direction_label"], "bull" | "bear" | "neutral"> = {
  bullish: "bull",
  bearish: "bear",
  neutral: "neutral",
};

/** 价位标注颜色。 */
const LEVEL_COLORS = {
  support: "#16a34a",
  resistance: "#dc2626",
  target: "#2563eb",
  stop_loss: "#f59e0b",
};

/**
 * 构建增强版 ECharts K 线配置项（T2.1 + T2.2）。
 * - 支持成交量副图（如果数据包含 volume）
 * - 叠加支撑/阻力/目标/止损价位 markLine
 * - 标注当前位置 markPoint
 */
function buildEnhancedOhlcOption(ohlc: OhlcBar[], scenarios: Scenario[]) {
  if (!ohlc || ohlc.length === 0) {
    return { series: [] };
  }
  const dates = ohlc.map((d) => formatDateShort(d.timestamp));
  const candleData = ohlc.map((d) => [d.open, d.close, d.low, d.high]);
  const hasVolume = ohlc.some((d) => d.volume !== undefined && d.volume !== null);
  const volumeData = hasVolume
    ? ohlc.map((d) => ({
        value: d.volume ?? 0,
        itemStyle: { color: d.close >= d.open ? "#16a34a80" : "#dc262680" },
      }))
    : [];

  const visibleBars = 120;
  const count = ohlc.length;
  const start = count > visibleBars ? Math.round(((count - visibleBars) / count) * 100) : 0;
  const lastClose = ohlc[count - 1].close;

  // 从所有情景中收集价位标注
  const markLines: unknown[] = [];
  for (const s of scenarios) {
    const levels: Array<{ key: keyof typeof LEVEL_COLORS; value: number | null }> = [
      { key: "support", value: s.support },
      { key: "resistance", value: s.resistance },
      { key: "target", value: s.target },
      { key: "stop_loss", value: s.stop_loss },
    ];
    for (const { key, value } of levels) {
      if (value !== null && value !== undefined) {
        markLines.push({
          yAxis: value,
          lineStyle: { type: "dashed", color: LEVEL_COLORS[key], width: 1, opacity: 0.7 },
          label: {
            formatter: `${s.name}-${key === "support" ? "支撑" : key === "resistance" ? "阻力" : key === "target" ? "目标" : "止损"}`,
            position: "insideEndTop",
            fontSize: 9,
            color: LEVEL_COLORS[key],
          },
        });
      }
    }
  }

  // 当前位置 markPoint
  const markPoints: unknown[] = [
    {
      coord: [count - 1, lastClose],
      value: formatPrice(lastClose),
      itemStyle: { color: "#6366f1" },
      label: { fontSize: 10, color: "#fff", position: "inside" },
      symbol: "pin",
      symbolSize: 48,
    },
  ];

  const grids = hasVolume
    ? [
        { left: 60, right: 20, top: 20, height: "60%" },
        { left: 60, right: 20, top: "76%", height: "16%" },
      ]
    : [{ left: 60, right: 20, top: 20, bottom: 56 }];

  const xAxes = hasVolume
    ? [
        {
          type: "category" as const,
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false },
          splitLine: { show: false },
          axisLabel: { show: false },
        },
        {
          type: "category" as const,
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false },
          splitLine: { show: false },
          axisLabel: { fontSize: 10 },
          gridIndex: 1,
        },
      ]
    : [
        {
          type: "category" as const,
          data: dates,
          boundaryGap: false,
          axisLine: { onZero: false },
          splitLine: { show: false },
          axisLabel: { fontSize: 10 },
        },
      ];

  const yAxes = hasVolume
    ? [
        { type: "value" as const, scale: true, splitLine: { show: true, lineStyle: { type: "dashed" } } },
        { type: "value" as const, scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { fontSize: 9 } },
      ]
    : [{ type: "value" as const, scale: true, splitLine: { show: true, lineStyle: { type: "dashed" } } }];

  const series: unknown[] = [
    {
      type: "candlestick",
      data: candleData,
      itemStyle: {
        color: "#16a34a",
        color0: "#dc2626",
        borderColor: "#16a34a",
        borderColor0: "#dc2626",
      },
      markPoint: { data: markPoints },
      markLine: {
        silent: true,
        symbol: "none",
        data: markLines,
      },
    },
  ];

  if (hasVolume) {
    series.push({
      type: "bar",
      data: volumeData,
      xAxisIndex: 1,
      yAxisIndex: 1,
    });
  }

  return {
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: hasVolume
      ? [
          { type: "inside", start, end: 100, xAxisIndex: [0, 1] },
          { type: "slider", start, end: 100, height: 18, bottom: 8, xAxisIndex: [0, 1] },
        ]
      : [
          { type: "inside", start, end: 100 },
          { type: "slider", start, end: 100, height: 18, bottom: 8 },
        ],
    series,
  };
}

/** 单个关键价位展示项。 */
function LevelItem({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg border border-surface-border px-3 py-2">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-ink-primary">{formatPrice(value)}</p>
    </div>
  );
}

/** 单个情景卡片（T2.3：集成 WaveSketchChart）。 */
function ScenarioCard({ scenario, currentPrice }: { scenario: Scenario; currentPrice?: number | null }) {
  const dirBadge = DIRECTION_BADGE[scenario.direction_label];

  return (
    <Card
      title={scenario.name}
      actions={
        <div className="flex items-center gap-2">
          <Badge variant={dirBadge}>{directionLabel(scenario.direction_label)}</Badge>
          <span
            className={`text-sm font-semibold ${directionColor(scenario.direction_label)}`}
          >
            {formatPercent(scenario.probability)}
          </span>
        </div>
      }
    >
      <div className="space-y-4">
        {/* 关键价位 */}
        <div className="grid grid-cols-2 gap-3">
          <LevelItem label="支撑价" value={scenario.support} />
          <LevelItem label="阻力价" value={scenario.resistance} />
          <LevelItem label="目标价" value={scenario.target} />
          <LevelItem label="止损价" value={scenario.stop_loss} />
        </div>

        {/* 仓位建议 */}
        <div className="flex items-center justify-between rounded-lg bg-surface-hover px-3 py-2">
          <span className="text-xs text-ink-muted">仓位建议</span>
          <span className="text-sm font-semibold text-ink-primary">
            {formatPercent(scenario.position_size)}
          </span>
        </div>

        {/* 波段概览波形图 (T2.3) */}
        {scenario.wave_sketch.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-ink-secondary">波段概览走势</p>
            <WaveSketchChart
              data={scenario.wave_sketch}
              direction={scenario.direction_label}
              currentPrice={currentPrice}
              height={160}
            />
          </div>
        )}

        {/* 描述 */}
        {scenario.description && (
          <p className="border-t border-surface-border pt-3 text-xs leading-relaxed text-ink-muted">
            {scenario.description}
          </p>
        )}
      </div>
    </Card>
  );
}

export default function ScenarioPage() {
  const subIndex = useGlobalStore((s) => s.subIndex);
  const period = useGlobalStore((s) => s.period);

  // 通过 ref 携带「是否强制刷新」标记，刷新后自动复位，避免影响后续常规请求
  const refreshRef = useRef(false);
  const [refreshCounter, setRefreshCounter] = useState(0);

  const scenario = useAsync(
    (signal) => {
      const refresh = refreshRef.current;
      refreshRef.current = false;
      return api.scenario.generate(subIndex, period, refresh, signal);
    },
    [subIndex, period, refreshCounter],
  );

  const ohlc = useAsync(
    (signal) => api.scenario.ohlc(subIndex, period, signal),
    [subIndex, period],
  );

  // T2.5: 接入历史相似 API
  const history = useAsync(
    (signal) => api.scenario.history(subIndex, period, "knn", 10, signal),
    [subIndex, period],
  );

  // T2.6: 接入模板匹配 API
  const templates = useAsync(
    (signal) => api.scenario.templates(subIndex, period, 0.5, signal),
    [subIndex, period],
  );

  const handleRefresh = () => {
    refreshRef.current = true;
    setRefreshCounter((c) => c + 1);
  };

  const ohlcBars = ohlc.data?.ohlc ?? [];
  const scenarios = scenario.data?.scenarios ?? [];
  const currentPrice = ohlcBars.length > 0 ? ohlcBars[ohlcBars.length - 1].close : null;
  const ohlcOption = buildEnhancedOhlcOption(ohlcBars, scenarios);

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">情景分析</h1>
        <p className="mt-1 text-sm text-ink-muted">
          基于历史相似度生成的多情景预测、关键价位与 K 线走势
        </p>
      </div>

      {/* 标的与周期选择器 + 重新生成 */}
      <SubIndexSelector
        onRefresh={handleRefresh}
        loading={scenario.loading}
        refreshLabel="重新生成"
      />

      {/* 增强版 K 线图 (T2.1 + T2.2) */}
      <Card
        title="K线图（含价位标注）"
        subtitle={`${subIndex} · ${period}`}
        actions={
          ohlc.data ? (
            <span className="text-xs text-ink-muted">共 {ohlc.data.count} 根K线</span>
          ) : undefined
        }
      >
        {ohlc.loading ? (
          <Spinner className="py-10" />
        ) : ohlc.error ? (
          <ErrorState message={ohlc.error} onRetry={ohlc.refetch} />
        ) : ohlcBars.length === 0 ? (
          <EmptyState title="暂无K线数据" description="请尝试切换标的或周期。" />
        ) : (
          <ReactECharts option={ohlcOption} style={{ height: 420, width: "100%" }} />
        )}
      </Card>

      {/* 未来走势预测图 (T2.4) */}
      {ohlcBars.length > 0 && scenarios.length > 0 && (
        <Card
          title="未来走势预测"
          subtitle="基于情景 wave_sketch 生成的模拟走势（颜色区分情景，透明度表示概率）"
        >
          <ForecastChart ohlc={ohlcBars} scenarios={scenarios} height={420} />
        </Card>
      )}

      {/* 生成元数据 */}
      {scenario.data && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-surface-border bg-surface-card px-4 py-3 text-xs text-ink-secondary shadow-card">
          <span>
            生成时间：
            <span className="text-ink-primary">{formatDate(scenario.data.generated_at)}</span>
          </span>
          <span className="text-ink-muted">|</span>
          <span>
            耗时：
            <span className="text-ink-primary">
              {formatDuration(scenario.data.generation_time_ms)}
            </span>
          </span>
          <span className="text-ink-muted">|</span>
          <Badge variant={scenario.data.cached ? "default" : "info"}>
            {scenario.data.cached ? "缓存命中" : "实时生成"}
          </Badge>
          <span className="text-ink-muted">|</span>
          <span>
            情景数：
            <span className="text-ink-primary">{scenario.data.scenarios.length}</span>
          </span>
        </div>
      )}

      {/* 情景列表 (T2.3: 每张卡片含 WaveSketchChart) */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">情景列表</h2>
        {scenario.loading ? (
          <Spinner className="py-10" />
        ) : scenario.error ? (
          <ErrorState message={scenario.error} onRetry={scenario.refetch} />
        ) : scenarios.length === 0 ? (
          <Card title="情景列表">
            <EmptyState
              title="暂无情景"
              description="未生成任何情景，请点击右上角「重新生成」。"
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {scenarios.map((s, idx) => (
              <ScenarioCard key={`${s.name}-${idx}`} scenario={s} currentPrice={currentPrice} />
            ))}
          </div>
        )}
      </section>

      {/* 历史相似度匹配 (T2.5) */}
      {history.data && history.data.matches.length > 0 && (
        <Card title="历史相似片段" subtitle={`方法：${history.data.method} · 共 ${history.data.matches.length} 条匹配`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                  <th className="px-3 py-2 font-medium">日期</th>
                  <th className="px-3 py-2 text-right font-medium">相似度</th>
                  <th className="px-3 py-2 text-right font-medium">未来收益</th>
                  {history.data.matches[0]?.label && (
                    <th className="px-3 py-2 font-medium">标签</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {history.data.matches.map((m, idx) => (
                  <tr key={idx} className="hover:bg-surface-hover">
                    <td className="px-3 py-2 text-ink-secondary">{formatDate(m.date)}</td>
                    <td className="px-3 py-2 text-right text-ink-primary">
                      {formatPercent(m.similarity)}
                    </td>
                    <td className={`px-3 py-2 text-right font-semibold ${m.future_return >= 0 ? "text-bull" : "text-bear"}`}>
                      {formatPercent(m.future_return)}
                    </td>
                    {m.label && <td className="px-3 py-2 text-ink-muted">{m.label}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* 模板匹配 (T2.6) */}
      {templates.data && templates.data.matches.length > 0 && (
        <Card title="经典图形匹配" subtitle={`最低置信度：${formatPercent(templates.data.min_confidence)} · 共 ${templates.data.matches.length} 条匹配`}>
          <div className="space-y-3">
            {templates.data.matches.map((t, idx) => (
              <div key={idx} className="flex items-start justify-between rounded-lg border border-surface-border px-4 py-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-ink-primary">{t.name}</span>
                    <Badge variant={t.direction === "bullish" ? "bull" : t.direction === "bearish" ? "bear" : "neutral"}>
                      {directionLabel(t.direction as "bullish" | "bearish" | "neutral")}
                    </Badge>
                  </div>
                  {t.description && (
                    <p className="mt-1 text-xs text-ink-muted">{t.description}</p>
                  )}
                </div>
                <span className="ml-3 shrink-0 text-sm font-semibold text-ink-primary">
                  {formatPercent(t.confidence)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
