import { Card, StatCard } from "../components/ui/Card";
import { Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { SubIndexSelector } from "../components/Selector";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { formatPercent, formatNumber, formatDate } from "../lib/format";
import type { EnsembleResponse, StrategyResult } from "../types/api";
import { useGlobalStore } from "../store/globalStore";
import { EChart } from "../components/EChart";

/** 策略 key 到中文展示名的映射。 */
const STRATEGY_LABELS: Record<string, string> = {
  ensemble: "集成策略",
  pullback: "回调策略",
  trend_following: "趋势跟踪",
};

/** 各策略在叠加曲线中的颜色（与 tailwind 主题一致）。 */
const STRATEGY_COLORS: Record<string, string> = {
  ensemble: "#2563eb", // brand-600
  pullback: "#16a34a", // bull
  trend_following: "#f59e0b", // neutral
};

interface StrategyRow {
  key: string;
  label: string;
  result: StrategyResult;
}

/** 从 EnsembleResponse 提取带展示名的策略列表，顺序固定。 */
function buildStrategyRows(data: EnsembleResponse): StrategyRow[] {
  return [
    { key: "ensemble", label: STRATEGY_LABELS.ensemble, result: data.ensemble },
    { key: "pullback", label: STRATEGY_LABELS.pullback, result: data.pullback },
    { key: "trend_following", label: STRATEGY_LABELS.trend_following, result: data.trend_following },
  ];
}

/** 构建三条策略叠加的权益曲线配置项。 */
function buildOverlayOption(rows: StrategyRow[]) {
  const [ensembleRow, pullbackRow, trendRow] = rows;
  const dates = ensembleRow.result.equity_curve.map((p) => p.timestamp.slice(0, 10));

  const series = [ensembleRow, pullbackRow, trendRow].map((row) => ({
    name: row.label,
    type: "line" as const,
    data: row.result.equity_curve.map((p) => p.equity),
    smooth: true,
    symbol: "none",
    lineStyle: { width: 2, color: STRATEGY_COLORS[row.key] },
  }));

  return {
    legend: { data: [STRATEGY_LABELS.ensemble, STRATEGY_LABELS.pullback, STRATEGY_LABELS.trend_following], bottom: 0 },
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: number) => formatNumber(v),
    },
    grid: { left: 64, right: 20, top: 20, bottom: 48 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: dates,
      axisLabel: { fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      splitLine: { show: true, lineStyle: { type: "dashed" } },
    },
    series,
  };
}

/** 取指标最优策略。 */
function pickBest(rows: StrategyRow[], selector: (m: StrategyResult["metrics"]) => number): StrategyRow {
  return rows.reduce((best, cur) =>
    selector(cur.result.metrics) > selector(best.result.metrics) ? cur : best,
  );
}

/** 单元格数值颜色：总收益按正负，最大回撤恒红。 */
function metricColor(metric: "total_return" | "max_drawdown", value: number): string {
  if (metric === "max_drawdown") return "text-bear";
  return value >= 0 ? "text-bull" : "text-bear";
}

export default function EnsemblePage() {
  const subIndex = useGlobalStore((s) => s.subIndex);
  const period = useGlobalStore((s) => s.period);

  const ensemble = useAsync((signal) => api.ensemble.run(subIndex, period, signal), [subIndex, period]);

  const data = ensemble.data;
  const rows = data ? buildStrategyRows(data) : [];
  const overlayOption = data ? buildOverlayOption(rows) : null;

  // 最优策略
  const bestReturn = rows.length ? pickBest(rows, (m) => m.total_return) : null;
  const bestSharpe = rows.length ? pickBest(rows, (m) => m.sharpe_ratio) : null;
  const bestWinRate = rows.length ? pickBest(rows, (m) => m.win_rate) : null;

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">集成策略对比</h1>
        <p className="mt-1 text-sm text-ink-muted">
          对比集成、回调、趋势跟踪三类策略的回测表现与权益走势
        </p>
      </div>

      {/* 标的与周期选择器 + 重新运行 */}
      <SubIndexSelector
        onRefresh={ensemble.refetch}
        loading={ensemble.loading}
        refreshLabel="重新运行"
      />

      {/* 最优策略概览 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">最优策略概览</h2>
        {ensemble.loading ? (
          <Spinner className="py-10" />
        ) : ensemble.error ? (
          <ErrorState message={ensemble.error} onRetry={ensemble.refetch} />
        ) : !data ? (
          <EmptyState title="暂无策略数据" description="请尝试切换标的或周期。" />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard
              label="最高收益"
              value={bestReturn ? formatPercent(bestReturn.result.metrics.total_return) : "--"}
              color="bull"
              hint={bestReturn ? bestReturn.label : undefined}
            />
            <StatCard
              label="最佳夏普"
              value={bestSharpe ? formatNumber(bestSharpe.result.metrics.sharpe_ratio) : "--"}
              color="bull"
              hint={bestSharpe ? bestSharpe.label : undefined}
            />
            <StatCard
              label="最高胜率"
              value={bestWinRate ? formatPercent(bestWinRate.result.metrics.win_rate) : "--"}
              color="bull"
              hint={bestWinRate ? bestWinRate.label : undefined}
            />
          </div>
        )}
      </section>

      {/* 策略对比表 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">策略对比</h2>
        <Card
          title="指标对比表"
          subtitle={`${subIndex} · ${period}`}
          actions={
            data ? (
              <span className="text-xs text-ink-muted">
                生成时间 {formatDate(data.generated_at)}
              </span>
            ) : undefined
          }
        >
          {ensemble.loading ? (
            <Spinner className="py-10" />
          ) : ensemble.error ? (
            <ErrorState message={ensemble.error} onRetry={ensemble.refetch} />
          ) : rows.length === 0 ? (
            <EmptyState title="暂无对比数据" description="未返回任何策略结果。" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                    <th className="px-3 py-2 font-medium">策略名称</th>
                    <th className="px-3 py-2 text-right font-medium">总收益</th>
                    <th className="px-3 py-2 text-right font-medium">最大回撤</th>
                    <th className="px-3 py-2 text-right font-medium">夏普比率</th>
                    <th className="px-3 py-2 text-right font-medium">胜率</th>
                    <th className="px-3 py-2 text-right font-medium">交易次数</th>
                    <th className="px-3 py-2 text-right font-medium">盈亏比</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const m = row.result.metrics;
                    return (
                      <tr
                        key={row.key}
                        className="border-b border-surface-border last:border-0 transition-colors hover:bg-surface-hover"
                      >
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span
                              className="inline-block h-2.5 w-2.5 rounded-full"
                              style={{ backgroundColor: STRATEGY_COLORS[row.key] }}
                            />
                            <span className="font-medium text-ink-primary">{row.label}</span>
                          </div>
                        </td>
                        <td className={`px-3 py-2 text-right font-semibold ${metricColor("total_return", m.total_return)}`}>
                          {formatPercent(m.total_return)}
                        </td>
                        <td className={`px-3 py-2 text-right font-semibold ${metricColor("max_drawdown", m.max_drawdown)}`}>
                          {formatPercent(m.max_drawdown)}
                        </td>
                        <td className="px-3 py-2 text-right text-ink-primary">
                          {formatNumber(m.sharpe_ratio)}
                        </td>
                        <td className="px-3 py-2 text-right text-ink-primary">
                          {formatPercent(m.win_rate)}
                        </td>
                        <td className="px-3 py-2 text-right text-ink-primary">
                          {formatNumber(m.total_trades, 0)}
                        </td>
                        <td className="px-3 py-2 text-right text-ink-primary">
                          {formatNumber(m.profit_factor)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      {/* 叠加权益曲线 */}
      <Card title="权益曲线对比" subtitle="三类策略叠加展示">
        {ensemble.loading ? (
          <Spinner className="py-10" />
        ) : ensemble.error ? (
          <ErrorState message={ensemble.error} onRetry={ensemble.refetch} />
        ) : !overlayOption ? (
          <EmptyState title="暂无权益数据" description="未返回任何策略权益曲线。" />
        ) : (
          <EChart option={overlayOption} style={{ height: 400, width: "100%" }} />
        )}
      </Card>
    </div>
  );
}
