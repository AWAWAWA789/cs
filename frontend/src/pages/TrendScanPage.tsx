import { useEffect, useRef, useState } from "react";
import type { EChartsOption } from "echarts";
import { Card, StatCard } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState } from "../components/ui/misc";
import { SubIndexSelector } from "../components/Selector";
import { api, pollScanTask } from "../lib/api";
import { formatPercent, formatNumber } from "../lib/format";
import type { TaskInfo, ScanResult, ScanResultItem } from "../types/api";
import { useGlobalStore } from "../store/globalStore";
import ReactECharts from "echarts-for-react";

/** 扫描生命周期阶段。 */
type ScanPhase = "idle" | "scanning" | "done" | "error";

/** 从扫描结果项的 params 中安全提取参数值并转为可读字符串。 */
function getParam(params: Record<string, unknown>, key: string): string {
  const v = params[key];
  if (v === undefined || v === null) return "--";
  if (typeof v === "number") return formatNumber(v);
  if (typeof v === "boolean") return String(v);
  return String(v);
}

/** 构建散点图配置项：x 轴为总收益，y 轴为夏普比率，点大小映射胜率。 */
function buildScatterOption(results: ScanResultItem[]): EChartsOption {
  return {
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params;
        const value = p.value as number[];
        const [totalReturn, sharpe, winRate] = value;
        return [
          `总收益：${formatPercent(totalReturn)}`,
          `夏普比率：${formatNumber(sharpe)}`,
          `胜率：${formatPercent(winRate)}`,
        ].join("<br/>");
      },
    },
    grid: { left: 64, right: 24, top: 24, bottom: 48 },
    xAxis: {
      name: "总收益",
      type: "value",
      axisLabel: { formatter: (v: number) => formatPercent(v) },
    },
    yAxis: {
      name: "夏普比率",
      type: "value",
    },
    series: [
      {
        type: "scatter",
        data: results.map((r) => [r.total_return, r.sharpe_ratio, r.win_rate]),
        symbolSize: (val: number[]) => 6 + Math.abs(val[2]) * 24,
        itemStyle: { color: "#4f46e5", opacity: 0.65 },
      },
    ],
  };
}

export default function TrendScanPage() {
  const subIndex = useGlobalStore((s) => s.subIndex);
  const period = useGlobalStore((s) => s.period);

  const [phase, setPhase] = useState<ScanPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 修复 B3：扫描开始时捕获参数快照，用于标题显示，避免实时 state 变化导致错位
  const [snapshot, setSnapshot] = useState<{ subIndex: string; period: string }>({
    subIndex,
    period,
  });

  // 用于标识当前扫描实例，避免过期回调更新状态（如组件卸载或发起新扫描后）
  const runIdRef = useRef(0);
  // 组件挂载状态标记，卸载后不再更新 state
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  /** 判断指定 runId 的扫描是否已被取消（新扫描发起或组件卸载）。 */
  const isCancelled = (runId: number) =>
    runId !== runIdRef.current || !mountedRef.current;

  const handleStartScan = async () => {
    const runId = ++runIdRef.current;
    // 捕获当前参数快照，用于扫描过程中和结果展示的标题
    const snap = { subIndex, period };
    setSnapshot(snap);
    setPhase("scanning");
    setProgress(0);
    setMessage("正在提交扫描任务...");
    setResult(null);
    setError(null);

    try {
      const { task_id } = await api.trendScan.start(snap.subIndex, snap.period);
      if (isCancelled(runId)) return;

      const scanResult = await pollScanTask(task_id, (info: TaskInfo) => {
        if (isCancelled(runId)) return;
        setProgress(info.progress);
        setMessage(info.message);
      });

      if (isCancelled(runId)) return;
      setResult(scanResult);
      setProgress(1);
      setPhase("done");
    } catch (err) {
      if (isCancelled(runId)) return;
      setError(err instanceof Error ? err.message : String(err));
      setPhase("error");
    }
  };

  const profitRatio =
    result && result.total_combinations > 0
      ? result.non_negative_count / result.total_combinations
      : 0;

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">趋势扫描</h1>
        <p className="mt-1 text-sm text-ink-muted">
          对多组策略参数进行网格扫描，筛选出收益与风险表现最优的参数组合
        </p>
      </div>

      {/* 标的与周期选择器 + 开始扫描按钮 */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <SubIndexSelector />
        <Button
          variant="primary"
          onClick={handleStartScan}
          loading={phase === "scanning"}
          disabled={phase === "scanning"}
        >
          {phase === "scanning" ? "扫描中" : "开始扫描"}
        </Button>
      </div>

      {/* 扫描进度 */}
      {phase === "scanning" && (
        <Card title="扫描进度" subtitle={`${snapshot.subIndex} · ${snapshot.period}`}>
          <div className="space-y-3">
            <div className="h-3 rounded-full bg-surface-border">
              <div
                className="h-3 rounded-full bg-brand-600 transition-all"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-xs text-ink-secondary">
              <span className="truncate">{message || "正在扫描..."}</span>
              <span className="ml-3 shrink-0 font-medium text-ink-primary">
                {formatPercent(progress, 1)}
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* 错误状态 */}
      {phase === "error" && (
        <Card title="扫描结果">
          <ErrorState message={error ?? "扫描失败"} onRetry={handleStartScan} />
        </Card>
      )}

      {/* 空闲初始状态 */}
      {phase === "idle" && (
        <Card title="扫描结果">
          <EmptyState
            title="尚未开始扫描"
            description="选择标的与周期后，点击「开始扫描」启动参数网格扫描。"
          />
        </Card>
      )}

      {/* 扫描结果 */}
      {phase === "done" && result && (
        <>
          {/* 统计卡片 */}
          <section>
            <h2 className="mb-3 text-sm font-semibold text-ink-secondary">扫描概览</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatCard
                label="总组合数"
                value={formatNumber(result.total_combinations, 0)}
                hint={`${snapshot.subIndex} · ${snapshot.period}`}
              />
              <StatCard
                label="盈利组合数"
                value={formatNumber(result.non_negative_count, 0)}
                color="bull"
                hint="总收益非负"
              />
              <StatCard
                label="盈利比例"
                value={formatPercent(profitRatio)}
                color={profitRatio >= 0.5 ? "bull" : "neutral"}
                hint="盈利组合 / 总组合数"
              />
            </div>
          </section>

          {/* 散点图 */}
          <Card title="参数组合分布" subtitle="总收益 vs 夏普比率（点大小代表胜率）">
            {result.all_results.length === 0 ? (
              <EmptyState title="暂无扫描数据" description="本次扫描未产生任何结果。" />
            ) : (
              <ReactECharts
                option={buildScatterOption(result.all_results)}
                style={{ height: 380, width: "100%" }}
              />
            )}
          </Card>

          {/* Top 10 结果表格 */}
          <Card title="Top 10 表现最优" subtitle="按总收益排序的前 10 组参数">
            {result.top_10.length === 0 ? (
              <EmptyState title="暂无结果" description="本次扫描未生成 Top 10 结果。" />
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-surface-border text-sm">
                  <thead>
                    <tr className="text-left text-xs text-ink-muted">
                      <th className="px-3 py-2 font-medium">排名</th>
                      <th className="px-3 py-2 font-medium">总收益</th>
                      <th className="px-3 py-2 font-medium">最大回撤</th>
                      <th className="px-3 py-2 font-medium">夏普比率</th>
                      <th className="px-3 py-2 font-medium">胜率</th>
                      <th className="px-3 py-2 font-medium">交易次数</th>
                      <th className="px-3 py-2 font-medium">swing_order</th>
                      <th className="px-3 py-2 font-medium">confirmations</th>
                      <th className="px-3 py-2 font-medium">trend_strength_threshold</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {result.top_10.map((item, idx) => (
                      <tr key={idx} className="hover:bg-surface-hover">
                        <td className="px-3 py-2 font-medium text-ink-primary">{idx + 1}</td>
                        <td
                          className={`px-3 py-2 font-medium ${
                            item.total_return >= 0 ? "text-bull" : "text-bear"
                          }`}
                        >
                          {formatPercent(item.total_return)}
                        </td>
                        <td className="px-3 py-2 text-bear">
                          {formatPercent(item.max_drawdown)}
                        </td>
                        <td className="px-3 py-2 text-ink-primary">
                          {formatNumber(item.sharpe_ratio)}
                        </td>
                        <td className="px-3 py-2 text-ink-primary">
                          {formatPercent(item.win_rate)}
                        </td>
                        <td className="px-3 py-2 text-ink-primary">
                          {formatNumber(item.total_trades, 0)}
                        </td>
                        <td className="px-3 py-2 text-ink-secondary">
                          {getParam(item.params, "swing_order")}
                        </td>
                        <td className="px-3 py-2 text-ink-secondary">
                          {getParam(item.params, "confirmations")}
                        </td>
                        <td className="px-3 py-2 text-ink-secondary">
                          {getParam(item.params, "trend_strength_threshold")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
