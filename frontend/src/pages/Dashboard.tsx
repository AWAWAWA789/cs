import { useState } from "react";
import { Card, StatCard } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { SubIndexSelector } from "../components/Selector";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { formatPercent, formatNumber } from "../lib/format";

/** 告警指标的中文标签映射。 */
const METRIC_LABELS: Record<string, string> = {
  failure_rate: "失败率",
  failure_count: "失败数",
  latency_p99_ms: "P99 延迟",
  latency_p50_ms: "P50 延迟",
  request_count: "请求数",
  brier_baseline: "Brier 基线",
};

/** 根据指标名称智能选择格式化方式（百分比 / 毫秒 / 数量）。 */
function formatAlertValue(metric: string, value: number): string {
  const m = metric.toLowerCase();
  if (m.includes("rate") || m.includes("ratio") || m.includes("brier")) {
    return formatPercent(value);
  }
  if (m.includes("latency") || m.includes("p99") || m.includes("p50") || m.endsWith("_ms")) {
    return `${formatNumber(value, 0)} ms`;
  }
  if (m.includes("count") || m.includes("request") || m.includes("failure")) {
    return formatNumber(value, 0);
  }
  return formatNumber(value);
}

export default function Dashboard() {
  const [subIndex, setSubIndex] = useState("手套");
  const [period, setPeriod] = useState("1day");

  // 情景生成（用于情景数指标）
  const scenario = useAsync(
    () => api.scenario.generate(subIndex, period),
    [subIndex, period],
  );
  // MVP 回测（用于收益 / 夏普 / 胜率指标）
  const backtest = useAsync(
    () => api.backtest.mvp(subIndex, period),
    [subIndex, period],
  );
  // 系统监控（用于告警展示）
  const monitoring = useAsync(() => api.monitoring.metrics(), []);

  const statsLoading = scenario.loading || backtest.loading;
  const statsError = scenario.error ?? backtest.error;

  const totalReturn = backtest.data?.metrics.total_return;
  const totalReturnColor =
    totalReturn === undefined ? "default" : totalReturn >= 0 ? "bull" : "bear";

  // 仅展示 warning / critical 级别的告警
  const alerts = (monitoring.data?.alerts ?? []).filter(
    (a) => a.severity === "warning" || a.severity === "critical",
  );

  const handleStatsRetry = () => {
    scenario.refetch();
    backtest.refetch();
  };

  return (
    <div className="space-y-6">
      {/* 欢迎头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">量化分析仪表盘</h1>
        <p className="mt-1 text-sm text-ink-muted">
          实时查看情景生成、回测表现与系统告警概览
        </p>
      </div>

      {/* 标的与周期选择器 */}
      <SubIndexSelector
        subIndex={subIndex}
        period={period}
        onSubIndexChange={setSubIndex}
        onPeriodChange={setPeriod}
      />

      {/* 核心指标卡片 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">核心指标</h2>
        {statsLoading ? (
          <Spinner className="py-10" />
        ) : statsError ? (
          <ErrorState message={statsError} onRetry={handleStatsRetry} />
        ) : (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard
              label="最新情景数"
              value={scenario.data?.scenarios.length ?? "--"}
              hint={`标的 ${subIndex} · ${period}`}
            />
            <StatCard
              label="回测总收益"
              value={totalReturn !== undefined ? formatPercent(totalReturn) : "--"}
              color={totalReturnColor}
              hint="MVP 策略回测"
            />
            <StatCard
              label="夏普比率"
              value={
                backtest.data ? formatNumber(backtest.data.metrics.sharpe_ratio) : "--"
              }
              hint="风险调整后收益"
            />
            <StatCard
              label="胜率"
              value={
                backtest.data ? formatPercent(backtest.data.metrics.win_rate) : "--"
              }
              hint={`共 ${backtest.data?.metrics.total_trades ?? "--"} 笔交易`}
            />
          </div>
        )}
      </section>

      {/* 系统告警 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">系统告警</h2>
        <Card
          title="近期告警"
          subtitle={
            monitoring.data
              ? `监控窗口 ${monitoring.data.metrics.window_seconds}s`
              : undefined
          }
          actions={
            monitoring.data ? (
              <Badge variant="info">共 {alerts.length} 条</Badge>
            ) : undefined
          }
        >
          {monitoring.loading ? (
            <Spinner className="py-8" />
          ) : monitoring.error ? (
            <ErrorState message={monitoring.error} onRetry={monitoring.refetch} />
          ) : alerts.length === 0 ? (
            <EmptyState
              title="暂无告警"
              description="当前系统运行正常，没有需要关注的 warning / critical 告警。"
            />
          ) : (
            <ul className="divide-y divide-surface-border">
              {alerts.map((alert, idx) => (
                <li
                  key={`${alert.metric}-${idx}`}
                  className="flex items-center justify-between py-3"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant={alert.severity === "critical" ? "bear" : "neutral"}>
                      {alert.severity === "critical" ? "严重" : "警告"}
                    </Badge>
                    <span className="text-sm font-medium text-ink-primary">
                      {METRIC_LABELS[alert.metric] ?? alert.metric}
                    </span>
                  </div>
                  <div className="text-right text-xs text-ink-secondary">
                    <span className="text-ink-primary">
                      当前 {formatAlertValue(alert.metric, alert.value)}
                    </span>
                    <span className="mx-2 text-ink-muted">/</span>
                    <span>
                      阈值 {formatAlertValue(alert.metric, alert.threshold)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </div>
  );
}
