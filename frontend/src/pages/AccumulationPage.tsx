import { useEffect, useState } from "react";
import { Card, StatCard } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { Button } from "../components/ui/Button";
import { Select, TextInput } from "../components/ui/Select";
import { useMeta, PERIOD_LABELS } from "../components/Selector";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { formatPercent, formatDuration, formatNumber, formatDate } from "../lib/format";
import type {
  AccumulationAnalysis,
  AccumulationFeatures,
  AccumulationSignals,
  AccumulationScanResponse,
} from "../types/api";
import { useGlobalStore, DEFAULT_PERIOD } from "../store/globalStore";

/** 阶段 → 中文标签。 */
const PHASE_LABEL: Record<AccumulationAnalysis["phase"], string> = {
  accumulation: "吸货阶段",
  distribution: "出货阶段",
  neutral: "中性",
};

/** 阶段 → Badge 颜色变体。 */
const PHASE_BADGE: Record<AccumulationAnalysis["phase"], "bull" | "bear" | "neutral"> = {
  accumulation: "bull",
  distribution: "bear",
  neutral: "neutral",
};

/** 信号分项展示顺序与中文标签。 */
const SIGNAL_LABELS: Array<{ key: keyof AccumulationSignals; label: string }> = [
  { key: "price_position", label: "价格位置" },
  { key: "volume_price_divergence", label: "量价背离" },
  { key: "consolidation", label: "横盘整理" },
  { key: "bottom_rising", label: "底部抬高" },
  { key: "volatility_contracting", label: "波动率收缩" },
  { key: "volume_trend", label: "成交量趋势" },
];

/** 原始特征展示顺序与中文标签。 */
const FEATURE_LABELS: Array<{ key: keyof AccumulationFeatures; label: string }> = [
  { key: "price_position", label: "价格位置" },
  { key: "distance_to_low", label: "距低点距离" },
  { key: "atr_percent", label: "ATR%" },
  { key: "volatility_regime", label: "波动率状态" },
  { key: "volume_ratio", label: "量比" },
  { key: "volume_trend", label: "量能趋势" },
  { key: "volume_price_divergence", label: "量价背离" },
  { key: "bottom_rising", label: "底部抬高" },
  { key: "consolidation_score", label: "横盘得分" },
  { key: "consolidation_bars", label: "横盘K线数" },
];

/** 周期下拉兜底选项（meta 未加载时使用）。 */
const FALLBACK_PERIODS = [DEFAULT_PERIOD, "4hour", "1hour", "7day"];

/** 持续时间条满刻度（K线根数），仅用于可视化比例。 */
const DURATION_FULL_BARS = 120;

/**
 * 根据吸货评分（0-1）返回颜色：高=绿、低=红、中性=灰。
 */
function scoreColor(score: number): string {
  if (score >= 0.6) return "#16a34a";
  if (score <= 0.4) return "#dc2626";
  return "#9ca3af";
}

/** 评分 → StatCard 颜色变体。 */
function scoreVariant(score: number): "bull" | "bear" | "neutral" {
  if (score >= 0.6) return "bull";
  if (score <= 0.4) return "bear";
  return "neutral";
}

/**
 * 根据信号分值（0-1）返回条形颜色：越高越绿。
 */
function signalColor(value: number): string {
  if (value >= 0.66) return "#16a34a";
  if (value >= 0.33) return "#f59e0b";
  return "#dc2626";
}

/** 单条信号水平条。 */
function SignalBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const color = signalColor(value);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-ink-secondary">{label}</span>
        <span className="font-semibold text-ink-primary">{formatNumber(value, 3)}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

/** 紧凑的特征值表格。 */
function FeaturesTable({ features }: { features: AccumulationFeatures }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
      {FEATURE_LABELS.map(({ key, label }) => {
        const raw = features[key];
        const isInt = key === "consolidation_bars" || key === "volatility_regime";
        const display = isInt ? String(raw) : formatNumber(raw, 3);
        return (
          <div
            key={key}
            className="flex items-center justify-between border-b border-surface-border pb-1"
          >
            <span className="text-xs text-ink-muted">{label}</span>
            <span className="text-xs font-medium text-ink-primary">{display}</span>
          </div>
        );
      })}
    </div>
  );
}

/** 扫描结果排行表。 */
function ScanResultsTable({ data }: { data: AccumulationScanResponse }) {
  return (
    <div>
      <p className="mb-3 text-xs text-ink-secondary">
        共扫描 <span className="text-ink-primary">{data.total_scanned}</span> 个标的 · 耗时{" "}
        {formatDuration(data.latency_ms)} · 周期 {data.period}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
              <th className="px-3 py-2 font-medium">排名</th>
              <th className="px-3 py-2 font-medium">标的</th>
              <th className="px-3 py-2 text-right font-medium">吸货评分</th>
              <th className="px-3 py-2 text-center font-medium">阶段</th>
              <th className="px-3 py-2 text-right font-medium">持续K线</th>
              <th className="px-3 py-2 font-medium">数据源</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {data.top_results.map((r, idx) => (
              <tr key={r.sub_index} className="transition-colors hover:bg-surface-hover">
                <td className="px-3 py-2 text-ink-muted">#{idx + 1}</td>
                <td className="px-3 py-2 font-medium text-ink-primary">{r.sub_index}</td>
                <td className="px-3 py-2 text-right">
                  <span
                    className="font-semibold"
                    style={{ color: scoreColor(r.accumulation_score) }}
                  >
                    {formatPercent(r.accumulation_score, 1)}
                  </span>
                </td>
                <td className="px-3 py-2 text-center">
                  <Badge variant={PHASE_BADGE[r.phase]}>{PHASE_LABEL[r.phase]}</Badge>
                </td>
                <td className="px-3 py-2 text-right text-ink-secondary">{r.duration_bars}</td>
                <td className="px-3 py-2 text-xs text-ink-muted">{r.data_source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** 单个标的的吸货分析结果展示。 */
function AnalysisResult({ data }: { data: AccumulationAnalysis }) {
  const score = data.accumulation_score;
  const phase = data.phase;
  const color = scoreColor(score);
  const variant = scoreVariant(score);
  const scorePct = Math.max(0, Math.min(1, score)) * 100;
  const durPct = Math.min(100, (data.duration_bars / DURATION_FULL_BARS) * 100);

  return (
    <div className="space-y-4">
      {/* 顶部统计 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="吸货评分"
          value={formatPercent(score, 1)}
          hint="0% 出货 · 100% 吸货"
          color={variant}
        />
        <StatCard
          label="当前阶段"
          value={<span style={{ color }}>{PHASE_LABEL[phase]}</span>}
          hint={<Badge variant={PHASE_BADGE[phase]}>{PHASE_LABEL[phase]}</Badge>}
        />
        <StatCard
          label="持续K线数"
          value={data.duration_bars}
          hint={`数据源：${data.data_source}`}
        />
      </div>

      {/* 评分进度 + 持续时间条 */}
      <Card title="评分与持续时间" subtitle="综合吸货评分进度与当前阶段持续K线数">
        <div className="space-y-4">
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-ink-secondary">吸货评分</span>
              <span className="font-semibold" style={{ color }}>
                {formatPercent(score, 1)}
              </span>
            </div>
            <div className="relative h-3 w-full overflow-hidden rounded-full bg-gradient-to-r from-red-500 via-amber-400 to-green-500">
              <div
                className="absolute top-1/2 h-5 w-1 rounded-full bg-ink-primary shadow-md ring-2 ring-white"
                style={{ left: `${scorePct}%`, transform: "translate(-50%, -50%)" }}
              />
            </div>
            <div className="mt-1 flex justify-between text-xs text-ink-muted">
              <span>出货</span>
              <span>中性</span>
              <span>吸货</span>
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-ink-secondary">持续时间</span>
              <span className="font-semibold text-ink-primary">
                {data.duration_bars} 根K线
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
              <div
                className="h-full rounded-full bg-brand-500 transition-all duration-500"
                style={{ width: `${durPct}%` }}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* 描述 */}
      {data.description && (
        <Card title="分析说明">
          <p className="text-sm leading-relaxed text-ink-secondary">{data.description}</p>
        </Card>
      )}

      {/* 信号分项 */}
      <Card title="信号分项" subtitle="各项吸货信号得分（越高越偏向吸货）">
        <div className="space-y-3">
          {SIGNAL_LABELS.map(({ key, label }) => (
            <SignalBar key={key} label={label} value={data.signals[key]} />
          ))}
        </div>
      </Card>

      {/* 原始特征 */}
      <Card title="原始特征值" subtitle="吸货分析输入的底层特征">
        <FeaturesTable features={data.features} />
      </Card>
    </div>
  );
}

export default function AccumulationPage() {
  const subIndex = useGlobalStore((s) => s.subIndex);
  const period = useGlobalStore((s) => s.period);
  const setSubIndex = useGlobalStore((s) => s.setSubIndex);
  const setPeriod = useGlobalStore((s) => s.setPeriod);

  const meta = useMeta();
  const periods = meta?.supported_periods?.length ? meta.supported_periods : FALLBACK_PERIODS;

  // 初始化状态（挂载时自动查询一次）
  const status = useAsync((signal) => api.accumulation.status(signal), []);

  // 数据预热（按钮触发）
  const [initTrigger, setInitTrigger] = useState(0);
  const init = useAsync(
    (signal) => api.accumulation.init(undefined, undefined, signal),
    [initTrigger],
    initTrigger > 0,
  );

  // 单标的分析（按钮触发，捕获点击时的参数）
  const [analyzeTrigger, setAnalyzeTrigger] = useState(0);
  const [analyzeParams, setAnalyzeParams] = useState<{ subIndex: string; period: string }>({
    subIndex,
    period,
  });
  const analysis = useAsync(
    (signal) => api.accumulation.analyze(analyzeParams.subIndex, analyzeParams.period, signal),
    [analyzeParams.subIndex, analyzeParams.period, analyzeTrigger],
    analyzeTrigger > 0,
  );

  // 批量扫描（按钮触发）
  const [scanInput, setScanInput] = useState("");
  const [scanTrigger, setScanTrigger] = useState(0);
  const [scanParams, setScanParams] = useState<{ indices: string[]; period: string }>({
    indices: [],
    period,
  });
  const scan = useAsync(
    (signal) => api.accumulation.scan(scanParams.indices, scanParams.period, 10, signal),
    [scanParams.period, scanParams.indices.length, scanTrigger],
    scanTrigger > 0 && scanParams.indices.length > 0,
  );

  // 初始化成功后刷新状态卡片
  useEffect(() => {
    if (init.data) {
      status.refetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [init.data]);

  const handleInit = () => setInitTrigger((c) => c + 1);

  const handleAnalyze = () => {
    setAnalyzeParams({ subIndex, period });
    setAnalyzeTrigger((c) => c + 1);
  };

  const handleScan = () => {
    const indices = scanInput
      .split(/[,\n\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (indices.length === 0) return;
    setScanParams({ indices, period });
    setScanTrigger((c) => c + 1);
  };

  const analyzeBusy = analysis.loading || analysis.isStale;
  const initBusy = init.loading || init.isStale;
  const scanBusy = scan.loading || scan.isStale;

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">库存吸货分析</h1>
        <p className="mt-1 text-sm text-ink-muted">识别主力资金隐蔽建仓行为</p>
      </div>

      {/* 分析参数 */}
      <Card title="分析参数" subtitle="输入标的名称并选择周期">
        <div className="flex flex-wrap items-end gap-3">
          <TextInput
            label="标的 (sub_index)"
            value={subIndex}
            onChange={(e) => setSubIndex(e.target.value)}
            placeholder="如：饰品指数"
          />
          <Select label="周期" value={period} onChange={(e) => setPeriod(e.target.value)}>
            {periods.map((p) => (
              <option key={p} value={p}>
                {PERIOD_LABELS[p] ?? p}
              </option>
            ))}
          </Select>
          <Button
            variant="primary"
            onClick={handleAnalyze}
            loading={analyzeBusy}
            disabled={!subIndex.trim()}
          >
            执行分析
          </Button>
        </div>
      </Card>

      {/* 数据预热 */}
      <Card title="数据预热" subtitle="一次性初始化吸货分析所需缓存，加速后续分析">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" onClick={handleInit} loading={initBusy}>
              初始化缓存
            </Button>
            <Button variant="ghost" size="sm" onClick={() => status.refetch()} loading={status.loading}>
              刷新状态
            </Button>
            {status.data && (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-secondary">
                <Badge variant={status.data.initialized ? "bull" : "neutral"}>
                  {status.data.initialized ? "已初始化" : "未初始化"}
                </Badge>
                <span>
                  缓存标的数：
                  <span className="text-ink-primary">{status.data.items_cached}</span>
                </span>
                {status.data.last_run && (
                  <span>
                    上次运行：
                    <span className="text-ink-primary">{formatDate(status.data.last_run)}</span>
                  </span>
                )}
              </div>
            )}
          </div>

          {status.loading && <Spinner className="py-4" />}
          {status.error && (
            <ErrorState message={status.error} onRetry={() => status.refetch()} />
          )}

          {init.data && (
            <div className="rounded-lg border border-surface-border bg-surface-hover px-4 py-3 text-xs">
              <p className="font-medium text-ink-primary">{init.data.message}</p>
              <p className="mt-1 text-ink-secondary">
                缓存标的数：{init.data.items_cached} · 耗时：{formatDuration(init.data.latency_ms)}
              </p>
              {init.data.errors.length > 0 && (
                <ul className="mt-2 list-inside list-disc text-bear">
                  {init.data.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {init.error && <ErrorState message={init.error} onRetry={handleInit} />}
        </div>
      </Card>

      {/* 分析结果 */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-ink-secondary">分析结果</h2>
        {analysis.loading ? (
          <Card>
            <Spinner className="py-10" />
          </Card>
        ) : analysis.error ? (
          <Card>
            <ErrorState message={analysis.error} onRetry={handleAnalyze} />
          </Card>
        ) : !analysis.data ? (
          <Card>
            <EmptyState
              title="尚未执行分析"
              description="输入标的并点击「执行分析」按钮以查看吸货分析结果。"
            />
          </Card>
        ) : (
          <AnalysisResult data={analysis.data} />
        )}
      </section>

      {/* 批量扫描 */}
      <Card title="批量扫描" subtitle="扫描多个标的的吸货评分并排行">
        <div className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[240px] flex-1">
              <TextInput
                label="标的列表（逗号、空格或换行分隔）"
                value={scanInput}
                onChange={(e) => setScanInput(e.target.value)}
                placeholder="如：饰品指数,手套,刀"
              />
            </div>
            <Button variant="primary" onClick={handleScan} loading={scanBusy} disabled={!scanInput.trim()}>
              开始扫描
            </Button>
          </div>
          {scan.loading ? (
            <Spinner className="py-6" />
          ) : scan.error ? (
            <ErrorState message={scan.error} onRetry={handleScan} />
          ) : scan.data ? (
            <ScanResultsTable data={scan.data} />
          ) : (
            <EmptyState
              title="暂无扫描结果"
              description="输入多个标的名称后点击「开始扫描」。"
            />
          )}
        </div>
      </Card>
    </div>
  );
}
