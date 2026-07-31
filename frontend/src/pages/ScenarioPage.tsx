import { useRef, useState } from "react";
import { Card } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { SubIndexSelector } from "../components/Selector";
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
import ReactECharts from "echarts-for-react";

/** 方向标签到 Badge 颜色变体的映射。 */
const DIRECTION_BADGE: Record<Scenario["direction_label"], "bull" | "bear" | "neutral"> = {
  bullish: "bull",
  bearish: "bear",
  neutral: "neutral",
};

/** 构建 ECharts K 线（candlestick）配置项。 */
function buildOhlcOption(ohlc: OhlcBar[]) {
  const dates = ohlc.map((d) => formatDateShort(d.timestamp));
  const data = ohlc.map((d) => [d.open, d.close, d.low, d.high]);

  // 默认展示最近 120 根K线，数据较多时允许回溯滚动
  const visibleBars = 120;
  const count = ohlc.length;
  const start = count > visibleBars ? Math.round(((count - visibleBars) / count) * 100) : 0;

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
    },
    grid: { left: 60, right: 20, top: 20, bottom: 56 },
    xAxis: {
      type: "category",
      data: dates,
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
      { type: "slider", start, end: 100, height: 18, bottom: 8 },
    ],
    series: [
      {
        type: "candlestick",
        data,
        itemStyle: {
          color: "#16a34a",
          color0: "#dc2626",
          borderColor: "#16a34a",
          borderColor0: "#dc2626",
        },
      },
    ],
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

/** 单个情景卡片。 */
function ScenarioCard({ scenario }: { scenario: Scenario }) {
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

        {/* 波段概览 */}
        <div>
          <p className="mb-2 text-xs font-medium text-ink-secondary">波段概览</p>
          {scenario.wave_sketch.length === 0 ? (
            <p className="text-xs text-ink-muted">无波段数据</p>
          ) : (
            <ul className="space-y-1">
              {scenario.wave_sketch.map((w, i) => (
                <li
                  key={`${w.label}-${i}`}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-ink-secondary">{w.label}</span>
                  <span className="font-medium text-ink-primary">{formatPrice(w.price)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

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
  const [subIndex, setSubIndex] = useState("手套");
  const [period, setPeriod] = useState("1day");

  // 通过 ref 携带「是否强制刷新」标记，刷新后自动复位，避免影响后续常规请求
  const refreshRef = useRef(false);
  const [refreshCounter, setRefreshCounter] = useState(0);

  const scenario = useAsync(
    () => {
      const refresh = refreshRef.current;
      refreshRef.current = false;
      return api.scenario.generate(subIndex, period, refresh);
    },
    [subIndex, period, refreshCounter],
  );

  const ohlc = useAsync(
    () => api.scenario.ohlc(subIndex, period),
    [subIndex, period],
  );

  const handleRefresh = () => {
    refreshRef.current = true;
    setRefreshCounter((c) => c + 1);
  };

  const ohlcOption = buildOhlcOption(ohlc.data?.ohlc ?? []);

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
        subIndex={subIndex}
        period={period}
        onSubIndexChange={setSubIndex}
        onPeriodChange={setPeriod}
        onRefresh={handleRefresh}
        loading={scenario.loading}
        refreshLabel="重新生成"
      />

      {/* K 线图 */}
      <Card
        title="K线图"
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
        ) : !ohlc.data || ohlc.data.ohlc.length === 0 ? (
          <EmptyState title="暂无K线数据" description="请尝试切换标的或周期。" />
        ) : (
          <ReactECharts option={ohlcOption} style={{ height: 380, width: "100%" }} />
        )}
      </Card>

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

      {/* 情景列表 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">情景列表</h2>
        {scenario.loading ? (
          <Spinner className="py-10" />
        ) : scenario.error ? (
          <ErrorState message={scenario.error} onRetry={scenario.refetch} />
        ) : !scenario.data || scenario.data.scenarios.length === 0 ? (
          <Card title="情景列表">
            <EmptyState
              title="暂无情景"
              description="未生成任何情景，请点击右上角「重新生成」。"
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {scenario.data.scenarios.map((s, idx) => (
              <ScenarioCard key={`${s.name}-${idx}`} scenario={s} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
