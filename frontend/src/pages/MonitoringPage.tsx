import { useEffect, useState } from "react";
import { Button } from "../components/ui/Button";
import { Card, StatCard } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { formatPercent, formatNumber, formatDuration } from "../lib/format";
import type { MonitoringResponse } from "../types/api";

/** 告警指标名到中文标签的映射。 */
const METRIC_LABELS: Record<string, string> = {
  failure_rate: "失败率",
  failure_count: "失败数",
  latency_p99_ms: "P99延迟",
  latency_p50_ms: "P50延迟",
  request_count: "请求数",
  brier_baseline: "Brier基线",
  brier_drift: "Brier漂移",
};

/** 将指标名翻译为中文，未知指标回退为原始名称。 */
function metricLabel(metric: string): string {
  return METRIC_LABELS[metric] ?? metric;
}

/** 根据指标类型智能选择格式化方式（百分比 / 时长 / 数量）。 */
function formatMetricValue(metric: string, value: number): string {
  const m = metric.toLowerCase();
  if (m === "failure_rate" || m.includes("rate") || m.includes("ratio")) {
    return formatPercent(value);
  }
  if (m.includes("brier")) {
    return formatNumber(value, 4);
  }
  if (m.includes("latency") || m.endsWith("_ms")) {
    return formatDuration(value);
  }
  if (m.includes("count") || m.includes("request")) {
    return formatNumber(value, 0);
  }
  return formatNumber(value);
}

type BadgeVariant = "default" | "bull" | "bear" | "neutral" | "info";

/** 将告警严重级别映射为 Badge 颜色与中文标签。 */
function severityInfo(severity: string): { variant: BadgeVariant; label: string } {
  const s = severity.toLowerCase();
  if (s === "critical") return { variant: "bear", label: "严重" };
  if (s === "warning") return { variant: "neutral", label: "警告" };
  if (s === "info") return { variant: "info", label: "提示" };
  if (s === "low") return { variant: "default", label: "低" };
  return { variant: "default", label: severity };
}

/** 自动刷新间隔（毫秒）。 */
const REFRESH_INTERVAL_MS = 10_000;

export default function MonitoringPage() {
  // 通过 useAsync 管理初始加载与手动 / 定时 refetch
  const monitoring = useAsync((signal) => api.monitoring.metrics(signal), []);
  const { refetch } = monitoring;

  // 保留最近一次成功的数据，避免定时刷新时因 useAsync 重置 data 而产生闪烁
  const [lastData, setLastData] = useState<MonitoringResponse | null>(null);
  useEffect(() => {
    if (monitoring.data) {
      setLastData(monitoring.data);
    }
  }, [monitoring.data]);

  // 每 10 秒自动刷新一次监控指标
  useEffect(() => {
    const id = setInterval(() => {
      refetch();
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refetch]);

  const metrics = lastData?.metrics;
  const alerts = lastData?.alerts ?? [];
  const thresholds = lastData?.thresholds ?? {};
  const endpoints = metrics?.per_endpoint ?? {};

  // 失败率颜色：0% 为正常（绿），>=10% 为严重（红），其余为警告（橙）
  const failureRate = metrics?.failure_rate ?? 0;
  const failureRateColor: "bull" | "neutral" | "bear" =
    failureRate === 0 ? "bull" : failureRate >= 0.1 ? "bear" : "neutral";

  // P99 延迟颜色：超过 1s 标记为警告
  const p99Color: "default" | "neutral" =
    (metrics?.latency_p99_ms ?? 0) > 1000 ? "neutral" : "default";

  // 初次加载尚未拿到任何数据时展示全屏 loading / error
  const showInitialLoading = monitoring.loading && !lastData;
  const showInitialError = monitoring.error && !lastData;
  // 后台刷新中（已有数据，正在拉取新一轮）
  const backgroundRefreshing = monitoring.loading && !!lastData;

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">系统监控</h1>
          <p className="mt-1 text-sm text-ink-muted">
            实时查看请求量、延迟、失败率与告警状态，每 10 秒自动刷新
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="info">
            <span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500 align-middle" />
            自动刷新中
          </Badge>
          <Button
            variant="secondary"
            size="md"
            onClick={refetch}
            loading={monitoring.loading}
          >
            立即刷新
          </Button>
        </div>
      </div>

      {/* 监控概要信息条 */}
      {lastData && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-surface-border bg-surface-card px-4 py-3 text-xs text-ink-secondary shadow-card">
          <span>
            监控窗口：
            <span className="text-ink-primary">{metrics?.window_seconds ?? "--"}s</span>
          </span>
          <span className="text-ink-muted">|</span>
          <span>
            失败数：
            <span className="text-ink-primary">
              {formatNumber(metrics?.failure_count ?? 0, 0)}
            </span>
          </span>
          {metrics?.brier_baseline !== null && metrics?.brier_baseline !== undefined && (
            <>
              <span className="text-ink-muted">|</span>
              <span>
                Brier基线：
                <span className="text-ink-primary">
                  {formatNumber(metrics.brier_baseline, 4)}
                </span>
              </span>
            </>
          )}
          {backgroundRefreshing && (
            <>
              <span className="text-ink-muted">|</span>
              <span className="text-brand-600">正在拉取最新数据…</span>
            </>
          )}
        </div>
      )}

      {/* 核心指标卡片 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">核心指标</h2>
        {showInitialLoading ? (
          <Spinner className="py-10" />
        ) : showInitialError ? (
          <ErrorState message={monitoring.error ?? "加载失败"} onRetry={refetch} />
        ) : (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard
              label="请求总数"
              value={formatNumber(metrics?.request_count ?? 0, 0)}
              hint={`窗口 ${metrics?.window_seconds ?? "--"}s`}
            />
            <StatCard
              label="失败率"
              value={formatPercent(failureRate)}
              color={failureRateColor}
              hint={`失败 ${formatNumber(metrics?.failure_count ?? 0, 0)} 次`}
            />
            <StatCard
              label="P50延迟"
              value={formatDuration(metrics?.latency_p50_ms ?? 0)}
              hint="中位响应时间"
            />
            <StatCard
              label="P99延迟"
              value={formatDuration(metrics?.latency_p99_ms ?? 0)}
              color={p99Color}
              hint="长尾响应时间"
            />
          </div>
        )}
      </section>

      {/* 告警列表 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">告警</h2>
        <Card
          title="活跃告警"
          subtitle={
            lastData
              ? `监控窗口 ${metrics?.window_seconds ?? "--"}s`
              : undefined
          }
          actions={
            lastData ? <Badge variant={alerts.length > 0 ? "bear" : "bull"}>共 {alerts.length} 条</Badge> : undefined
          }
        >
          {showInitialLoading ? (
            <Spinner className="py-8" />
          ) : showInitialError ? (
            <ErrorState message={monitoring.error ?? "加载失败"} onRetry={refetch} />
          ) : alerts.length === 0 ? (
            <EmptyState
              title="暂无告警"
              description="当前系统运行正常，所有指标均在阈值范围内。"
            />
          ) : (
            <ul className="divide-y divide-surface-border">
              {alerts.map((alert, idx) => {
                const sev = severityInfo(alert.severity);
                return (
                  <li
                    key={`${alert.metric}-${idx}`}
                    className="flex flex-wrap items-center justify-between gap-2 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <Badge variant={sev.variant}>{sev.label}</Badge>
                      <span className="text-sm font-medium text-ink-primary">
                        {metricLabel(alert.metric)}
                      </span>
                    </div>
                    <div className="text-right text-xs text-ink-secondary">
                      <span className="text-ink-primary">
                        当前 {formatMetricValue(alert.metric, alert.value)}
                      </span>
                      <span className="mx-2 text-ink-muted">/</span>
                      <span>
                        阈值 {formatMetricValue(alert.metric, alert.threshold)}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </section>

      {/* 端点监控明细 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">端点监控</h2>
        <Card
          title="端点指标明细"
          subtitle="按接口维度统计的请求量、失败率与延迟"
          actions={
            lastData ? (
              <Badge variant="info">共 {Object.keys(endpoints).length} 个端点</Badge>
            ) : undefined
          }
          bodyClassName="p-0"
        >
          {showInitialLoading ? (
            <Spinner className="py-8" />
          ) : showInitialError ? (
            <ErrorState message={monitoring.error ?? "加载失败"} onRetry={refetch} />
          ) : Object.keys(endpoints).length === 0 ? (
            <EmptyState
              title="暂无端点数据"
              description="当前监控窗口内未采集到任何端点请求。"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-border bg-surface-hover text-left text-xs text-ink-muted">
                    <th className="px-5 py-3 font-medium">端点</th>
                    <th className="px-5 py-3 text-right font-medium">请求次数</th>
                    <th className="px-5 py-3 text-right font-medium">失败率</th>
                    <th className="px-5 py-3 text-right font-medium">P99延迟</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {Object.entries(endpoints).map(([endpoint, stat]) => (
                    <tr
                      key={endpoint}
                      className="transition-colors hover:bg-surface-hover"
                    >
                      <td className="px-5 py-3 font-medium text-ink-primary">
                        {endpoint}
                      </td>
                      <td className="px-5 py-3 text-right text-ink-secondary">
                        {formatNumber(stat.request_count, 0)}
                      </td>
                      <td className="px-5 py-3 text-right text-ink-secondary">
                        <span
                          className={
                            stat.failure_rate > 0 ? "text-bear font-medium" : ""
                          }
                        >
                          {formatPercent(stat.failure_rate)}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right text-ink-secondary">
                        {formatDuration(stat.latency_p99_ms)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      {/* 告警阈值配置 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">告警阈值</h2>
        <Card title="当前阈值配置" subtitle="超过以下阈值的指标将触发告警">
          {showInitialLoading ? (
            <Spinner className="py-8" />
          ) : showInitialError ? (
            <ErrorState message={monitoring.error ?? "加载失败"} onRetry={refetch} />
          ) : Object.keys(thresholds).length === 0 ? (
            <EmptyState title="暂无阈值配置" description="后端未返回任何告警阈值。" />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(thresholds).map(([metric, threshold]) => (
                <div
                  key={metric}
                  className="flex items-center justify-between rounded-lg border border-surface-border bg-surface-hover px-4 py-3"
                >
                  <span className="text-sm text-ink-secondary">
                    {metricLabel(metric)}
                  </span>
                  <span className="text-sm font-semibold text-ink-primary">
                    {formatMetricValue(metric, threshold)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
