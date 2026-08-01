import { Card, StatCard } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { SubIndexSelector } from "../components/Selector";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import {
  formatPercent,
  formatNumber,
  formatPrice,
  formatDate,
  exitReasonLabel,
} from "../lib/format";
import type { EquityPoint, TradeRecord } from "../types/api";
import { useGlobalStore } from "../store/globalStore";
import { EChart } from "../components/EChart";

/** 品牌主色（与 tailwind brand-600 一致）。 */
const BRAND_COLOR = "#2563eb";

/** 构建 ECharts 权益曲线配置项。 */
function buildEquityOption(equityCurve: EquityPoint[]) {
  return {
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: number) => formatNumber(v),
    },
    grid: { left: 64, right: 20, top: 20, bottom: 32 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: equityCurve.map((p) => p.timestamp.slice(0, 10)),
      axisLabel: { fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      splitLine: { show: true, lineStyle: { type: "dashed" } },
    },
    series: [
      {
        type: "line",
        data: equityCurve.map((p) => p.equity),
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, color: BRAND_COLOR },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(37, 99, 235, 0.25)" },
              { offset: 1, color: "rgba(37, 99, 235, 0)" },
            ],
          },
        },
      },
    ],
  };
}

/** 退出原因到 Badge 颜色变体的映射。 */
function exitReasonBadge(reason: string): "bull" | "bear" | "neutral" | "info" {
  switch (reason) {
    case "take_profit":
      return "bull";
    case "stop_loss":
    case "trailing_stop":
      return "bear";
    case "signal_exit":
      return "info";
    default:
      return "neutral";
  }
}

/** 盈亏数值，正数绿色、负数红色。 */
function PnlText({ value, isPercent = false }: { value: number; isPercent?: boolean }) {
  const positive = value >= 0;
  return (
    <span className={positive ? "text-bull" : "text-bear"}>
      {isPercent ? formatPercent(value) : formatNumber(value)}
    </span>
  );
}

/** 交易明细表。 */
function TradesTable({ trades }: { trades: TradeRecord[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
            <th className="px-3 py-2 font-medium">序号</th>
            <th className="px-3 py-2 font-medium">入场时间</th>
            <th className="px-3 py-2 text-right font-medium">入场价</th>
            <th className="px-3 py-2 font-medium">出场时间</th>
            <th className="px-3 py-2 text-right font-medium">出场价</th>
            <th className="px-3 py-2 font-medium">退出原因</th>
            <th className="px-3 py-2 text-right font-medium">盈亏</th>
            <th className="px-3 py-2 text-right font-medium">收益率</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, idx) => (
            <tr
              key={idx}
              className="border-b border-surface-border last:border-0 transition-colors hover:bg-surface-hover"
            >
              <td className="px-3 py-2 text-ink-secondary">{idx + 1}</td>
              <td className="px-3 py-2 text-ink-secondary">{formatDate(t.entry_time)}</td>
              <td className="px-3 py-2 text-right font-medium text-ink-primary">
                {formatPrice(t.entry_price)}
              </td>
              <td className="px-3 py-2 text-ink-secondary">{formatDate(t.exit_time)}</td>
              <td className="px-3 py-2 text-right font-medium text-ink-primary">
                {formatPrice(t.exit_price)}
              </td>
              <td className="px-3 py-2">
                <Badge variant={exitReasonBadge(t.exit_reason)}>
                  {exitReasonLabel(t.exit_reason)}
                </Badge>
              </td>
              <td className="px-3 py-2 text-right font-semibold">
                <PnlText value={t.pnl} />
              </td>
              <td className="px-3 py-2 text-right font-semibold">
                <PnlText value={t.return_pct} isPercent />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BacktestPage() {
  const subIndex = useGlobalStore((s) => s.subIndex);
  const period = useGlobalStore((s) => s.period);

  const backtest = useAsync((signal) => api.backtest.mvp(subIndex, period, signal), [subIndex, period]);

  const metrics = backtest.data?.metrics;
  const equityCurve = backtest.data?.equity_curve ?? [];
  const trades = backtest.data?.trades ?? [];

  const equityOption = buildEquityOption(equityCurve);

  // 指标颜色：总收益按正负，最大回撤恒为风险（红色）
  const totalReturnColor =
    metrics === undefined ? "default" : metrics.total_return >= 0 ? "bull" : "bear";

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">回测分析</h1>
        <p className="mt-1 text-sm text-ink-muted">
          MVP 策略回测的收益指标、权益曲线与逐笔交易明细
        </p>
      </div>

      {/* 标的与周期选择器 + 重新回测 */}
      <SubIndexSelector
        onRefresh={backtest.refetch}
        loading={backtest.loading}
        refreshLabel="重新回测"
      />

      {/* 核心指标卡片 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">核心指标</h2>
        {backtest.loading ? (
          <Spinner className="py-10" />
        ) : backtest.error ? (
          <ErrorState message={backtest.error} onRetry={backtest.refetch} />
        ) : !metrics ? (
          <EmptyState title="暂无回测数据" description="请尝试切换标的或周期。" />
        ) : (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            <StatCard
              label="总收益率"
              value={formatPercent(metrics.total_return)}
              color={totalReturnColor}
              hint={`期末权益 ${formatPrice(metrics.final_equity)}`}
            />
            <StatCard
              label="最大回撤"
              value={formatPercent(metrics.max_drawdown)}
              color="bear"
              hint="历史最大亏损幅度"
            />
            <StatCard
              label="夏普比率"
              value={formatNumber(metrics.sharpe_ratio)}
              hint="风险调整后收益"
            />
            <StatCard
              label="胜率"
              value={formatPercent(metrics.win_rate)}
              hint={`平均单笔 ${formatPercent(metrics.avg_trade_return)}`}
            />
            <StatCard
              label="交易次数"
              value={formatNumber(metrics.total_trades, 0)}
              hint="已完成交易笔数"
            />
            <StatCard
              label="盈亏比"
              value={formatNumber(metrics.profit_factor)}
              color={metrics.profit_factor >= 1 ? "bull" : "bear"}
              hint="总盈利 / 总亏损"
            />
          </div>
        )}
      </section>

      {/* 权益曲线 */}
      <Card
        title="权益曲线"
        subtitle={`${subIndex} · ${period}`}
        actions={
          backtest.data ? (
            <span className="text-xs text-ink-muted">
              生成时间 {formatDate(backtest.data.generated_at)}
            </span>
          ) : undefined
        }
      >
        {backtest.loading ? (
          <Spinner className="py-10" />
        ) : backtest.error ? (
          <ErrorState message={backtest.error} onRetry={backtest.refetch} />
        ) : equityCurve.length === 0 ? (
          <EmptyState title="暂无权益数据" description="未返回任何权益曲线点位。" />
        ) : (
          <EChart option={equityOption} style={{ height: 380, width: "100%" }} />
        )}
      </Card>

      {/* 交易明细 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">交易明细</h2>
        <Card
          title="逐笔交易记录"
          subtitle={`共 ${trades.length} 笔交易`}
        >
          {backtest.loading ? (
            <Spinner className="py-10" />
          ) : backtest.error ? (
            <ErrorState message={backtest.error} onRetry={backtest.refetch} />
          ) : trades.length === 0 ? (
            <EmptyState title="暂无交易记录" description="本次回测未产生任何交易。" />
          ) : (
            <TradesTable trades={trades} />
          )}
        </Card>
      </section>
    </div>
  );
}
