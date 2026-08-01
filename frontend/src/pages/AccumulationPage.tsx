import { useEffect, useState } from "react";
import { Card, StatCard } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { Button } from "../components/ui/Button";
import { Select, TextInput } from "../components/ui/Select";
import { useMeta, PERIOD_LABELS } from "../components/Selector";
import { ItemSearchBar } from "../components/ItemSearchBar";
import { EChart } from "../components/EChart";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { formatPercent, formatDuration, formatNumber, formatDate } from "../lib/format";
import type {
  AccumulationAnalysis,
  AccumulationFeatures,
  AccumulationSignals,
  AccumulationScanResponse,
  ItemInventoryResponse,
  ItemHolder,
  ItemTrend,
  FusedAccumulationResponse,
  FusionPattern,
  TeamAnalysisResponse,
  TeamRelatedItem,
  TeamHolderCross,
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

/**
 * 库存变动 type → 中文标签（CSQAQ monitor 约定）。
 * 0-7 分别对应不同的入/出库行为；买卖方向用于着色。
 */
const TREND_TYPE_LABEL: Record<number, string> = {
  0: "未知变动",
  1: "买入入库",
  2: "卖出出库",
  3: "库存增加",
  4: "库存减少",
  5: "转移入库",
  6: "转移出库",
  7: "其他",
};

/** 变动方向（买入/入库=多方，卖出/出库=空方），用于着色。 */
function trendDirection(type: number): "bull" | "bear" | "neutral" {
  if ([1, 3, 5].includes(type)) return "bull";
  if ([2, 4, 6].includes(type)) return "bear";
  return "neutral";
}

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

/** 双轨融合模式 → 中文标签与颜色。 */
const PATTERN_META: Record<FusionPattern, { label: string; desc: string; color: string; variant: "bull" | "bear" | "neutral" }> = {
  strong: { label: "明牌吸货", desc: "K线吸货 + 库存加仓，双高信号", color: "#16a34a", variant: "bull" },
  hidden: { label: "隐蔽吸货", desc: "K线不动但库存加仓，最稀缺信号", color: "#0ea5e9", variant: "bull" },
  weak: { label: "疑似误判", desc: "K线看似吸货但库存不配合，可能下跌中继", color: "#f59e0b", variant: "neutral" },
  none: { label: "无信号", desc: "双低，无明显吸货迹象", color: "#9ca3af", variant: "neutral" },
};

/** 双轨融合吸货分析展示。 */
function FusedAnalysisPanel({ data }: { data: FusedAccumulationResponse }) {
  const meta = PATTERN_META[data.pattern];
  const klinePct = Math.round(data.kline_score * 100);
  const invPct = Math.round(data.inventory_score * 100);
  const fusedPct = Math.round(data.fused_score * 100);

  return (
    <div className="space-y-4">
      {/* 融合评分总览 */}
      <Card title="双轨融合评分" subtitle="K线行为 × 库存行为 交叉验证">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="融合吸货评分"
            value={
              <span style={{ color: scoreColor(data.fused_score) }}>
                {formatPercent(data.fused_score, 1)}
              </span>
            }
            hint={<Badge variant={PHASE_BADGE[data.phase]}>{PHASE_LABEL[data.phase]}</Badge>}
          />
          <StatCard
            label="融合模式"
            value={<span style={{ color: meta.color }}>{meta.label}</span>}
            hint={meta.desc}
          />
          <StatCard
            label="持续K线数"
            value={data.duration_bars}
            hint={`数据源：${data.data_source}`}
          />
        </div>

        {/* 双轨对比条 */}
        <div className="mt-4 space-y-3">
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-ink-secondary">K线行为评分</span>
              <span className="font-semibold" style={{ color: scoreColor(data.kline_score) }}>
                {formatPercent(data.kline_score, 1)}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${klinePct}%`, backgroundColor: scoreColor(data.kline_score) }}
              />
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-ink-secondary">库存行为评分</span>
              <span className="font-semibold" style={{ color: scoreColor(data.inventory_score) }}>
                {formatPercent(data.inventory_score, 1)}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${invPct}%`, backgroundColor: scoreColor(data.inventory_score) }}
              />
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-medium text-ink-primary">融合评分</span>
              <span className="font-bold" style={{ color: scoreColor(data.fused_score) }}>
                {formatPercent(data.fused_score, 1)}
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-surface-hover">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${fusedPct}%`, backgroundColor: scoreColor(data.fused_score) }}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* 证据链 */}
      {data.evidence.length > 0 && (
        <Card title="证据链" subtitle="双轨信号交叉验证依据">
          <ul className="space-y-2">
            {data.evidence.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-secondary">
                <span className="mt-1 text-xs text-ink-muted">▸</span>
                <span>{e}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* 库存子分明细 */}
      <Card title="库存行为子分" subtitle="4 项库存特征明细">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          <SignalBar label="集中度" value={data.inventory_signals.concentration} />
          <SignalBar label="净流入" value={data.inventory_signals.net_inflow} />
          <SignalBar label="活跃度" value={data.inventory_signals.holder_activity} />
          <SignalBar label="团队协同" value={data.inventory_signals.team_synergy} />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-surface-border pt-3 text-xs sm:grid-cols-3">
          <div className="flex justify-between">
            <span className="text-ink-muted">TOP3 集中度</span>
            <span className="font-medium text-ink-primary">
              {formatPercent(data.inventory_stats.top3_concentration, 1)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-muted">总持仓量</span>
            <span className="font-medium text-ink-primary">{formatNumber(data.inventory_stats.total_hold, 0)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-muted">近7日净流入</span>
            <span
              className="font-medium"
              style={{ color: data.inventory_stats.net_inflow_7d >= 0 ? "#16a34a" : "#dc2626" }}
            >
              {data.inventory_stats.net_inflow_7d > 0 ? "+" : ""}
              {formatNumber(data.inventory_stats.net_inflow_7d, 0)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-muted">活跃主力</span>
            <span className="font-medium text-ink-primary">
              {data.inventory_stats.active_holder_count} / {data.inventory_stats.holder_total}
            </span>
          </div>
          {data.inventory_stats.team_confidence !== null && (
            <div className="flex justify-between">
              <span className="text-ink-muted">团队置信度</span>
              <span className="font-medium text-ink-primary">
                {formatPercent(data.inventory_stats.team_confidence, 0)}
              </span>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

/** 单品库存监控数据展示（先看数据，不加算法）。 */
function ItemInventoryPanel({ data }: { data: ItemInventoryResponse }) {
  const holders = data.holders;
  const trends = data.trends;
  const topHolders = holders.slice(0, 10);
  // 持有量总和与集中度（top3 占比）
  const totalHold = holders.reduce((s, h) => s + (h.hold_count || 0), 0);
  const top3Hold = topHolders.slice(0, 3).reduce((s, h) => s + (h.hold_count || 0), 0);
  const top3Ratio = totalHold > 0 ? (top3Hold / totalHold) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* 概览统计 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="监控到的持有者" value={data.holder_count} hint="主力分布广度" />
        <StatCard label="近期变动笔数" value={data.trend_count} hint="买卖活跃度" />
        <StatCard label="总持有量" value={formatNumber(totalHold, 0)} hint="主力手里货量" />
        <StatCard
          label="TOP3 集中度"
          value={formatPercent(top3Ratio / 100, 1)}
          hint="头部主力占比"
          color={top3Ratio >= 50 ? "bull" : "neutral"}
        />
      </div>

      {/* 主力持有量排行 */}
      <Card title="主力持有量排行" subtitle="持有该饰品最多的 Steam 用户（货量分布）">
        {topHolders.length === 0 ? (
          <EmptyState title="暂无持有者数据" description="可能是该饰品暂未被监控，或未配置 API token。" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                  <th className="px-3 py-2 font-medium">排名</th>
                  <th className="px-3 py-2 font-medium">用户</th>
                  <th className="px-3 py-2 text-right font-medium">持有量</th>
                  <th className="px-3 py-2 text-right font-medium">持仓价值</th>
                  <th className="px-3 py-2 text-right font-medium">占比</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {topHolders.map((h: ItemHolder, idx) => (
                  <tr key={h.task_id} className="transition-colors hover:bg-surface-hover">
                    <td className="px-3 py-2 text-ink-muted">#{idx + 1}</td>
                    <td className="px-3 py-2 font-medium text-ink-primary">{h.steam_name || h.steam_id}</td>
                    <td className="px-3 py-2 text-right">{formatNumber(h.hold_count, 0)}</td>
                    <td className="px-3 py-2 text-right text-ink-secondary">¥{formatNumber(h.hold_value, 0)}</td>
                    <td className="px-3 py-2 text-right text-ink-secondary">
                      {totalHold > 0 ? formatPercent((h.hold_count || 0) / totalHold, 1) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 近期买卖变动 */}
      <Card title="近期库存变动" subtitle="主力对该饰品的买卖动态（结合 K 线判断吸/出货）">
        {trends.length === 0 ? (
          <EmptyState title="暂无变动数据" description="该饰品近期无库存变动记录。" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                  <th className="px-3 py-2 font-medium">时间</th>
                  <th className="px-3 py-2 font-medium">用户</th>
                  <th className="px-3 py-2 font-medium">方向</th>
                  <th className="px-3 py-2 text-right font-medium">数量</th>
                  <th className="px-3 py-2 text-right font-medium">价格</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {trends.slice(0, 20).map((t: ItemTrend) => {
                  const dir = trendDirection(t.type);
                  return (
                    <tr key={t.trend_id} className="transition-colors hover:bg-surface-hover">
                      <td className="px-3 py-2 text-xs text-ink-muted">{formatDate(t.time)}</td>
                      <td className="px-3 py-2 font-medium text-ink-primary">{t.steam_name}</td>
                      <td className="px-3 py-2">
                        <Badge variant={dir}>{TREND_TYPE_LABEL[t.type] ?? `类型${t.type}`}</Badge>
                      </td>
                      <td className="px-3 py-2 text-right">{formatNumber(t.count, 0)}</td>
                      <td className="px-3 py-2 text-right text-ink-secondary">¥{formatNumber(t.price, 2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {data.description && (
        <p className="text-xs text-ink-muted">{data.description}</p>
      )}
    </div>
  );
}

/** 跨品主力团队识别结果展示。 */
function TeamAnalysisPanel({
  data,
  onSelectSeed,
  relatedScores,
}: {
  data: TeamAnalysisResponse;
  /** 点击关联品设为新种子品做二次分析。 */
  onSelectSeed?: (goodId: string, name?: string) => void;
  /** 关联品的同步吸货评分（good_id → score），用于联动加权。 */
  relatedScores?: Record<string, number>;
}) {
  const summary = data.team_summary;
  const related = data.related_items;
  const holders = data.holders_cross;
  const coreHolders = holders.filter((h) => h.is_core);
  const confidencePct = Math.max(0, Math.min(1, summary.confidence)) * 100;
  const hasScores = relatedScores && Object.keys(relatedScores).length > 0;

  return (
    <div className="space-y-4">
      {/* 团队判定信号 */}
      <div
        className={`rounded-lg border p-4 ${
          summary.is_likely_team_operated
            ? "border-bull/40 bg-bull/5"
            : "border-surface-border bg-surface-hover"
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge variant={summary.is_likely_team_operated ? "bull" : "neutral"}>
              {summary.is_likely_team_operated ? "疑似团队操作" : "未发现明显团队信号"}
            </Badge>
            <span className="text-sm font-medium text-ink-primary">
              置信度 {formatPercent(summary.confidence, 1)}
            </span>
          </div>
          <span className="text-xs text-ink-muted">
            种子主力 {data.analyzed_holder_count} 人 · 关联品 {summary.related_item_count} 个
          </span>
        </div>
        {/* 置信度进度条 */}
        <div className="mt-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${confidencePct}%`,
                backgroundColor: summary.is_likely_team_operated ? "#16a34a" : "#9ca3af",
              }}
            />
          </div>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-ink-secondary">{summary.reason}</p>
      </div>

      {/* 团队指标概览 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="核心团队规模"
          value={summary.core_team_size}
          hint="跨≥3品的主力人数"
          color={summary.core_team_size >= 2 ? "bull" : "neutral"}
        />
        <StatCard
          label="核心团队集中度"
          value={formatPercent(summary.core_team_ratio_in_seed, 1)}
          hint="核心团队占种子品持仓"
          color={summary.core_team_ratio_in_seed >= 0.4 ? "bull" : "neutral"}
        />
        <StatCard
          label="最高重合度"
          value={formatPercent(summary.max_overlap_ratio, 1)}
          hint={`关联品最多被 ${summary.max_overlap_count} 人共同持有`}
          color={summary.max_overlap_ratio >= 0.3 ? "bull" : "neutral"}
        />
        <StatCard
          label="主力平均跨品数"
          value={formatNumber(summary.avg_cross_items_per_holder, 1)}
          hint="每个主力平均持有的其他品数"
        />
      </div>

      {/* 关联品表 */}
      <Card
        title="关联品（疑似同团队标的）"
        subtitle="被多个种子主力共同持有的其他饰品，重合度越高越可疑；点击行可设为新种子做二次分析"
      >
        {related.length === 0 ? (
          <EmptyState
            title="暂无关联品"
            description="未发现被多个种子主力共同持有的其他饰品，主力可能独立操作。"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                  <th className="px-3 py-2 font-medium">排名</th>
                  <th className="px-3 py-2 font-medium">关联品</th>
                  <th className="px-3 py-2 text-right font-medium">重合主力数</th>
                  <th className="px-3 py-2 text-right font-medium">重合度</th>
                  {hasScores && <th className="px-3 py-2 text-right font-medium">吸货评分</th>}
                  <th className="px-3 py-2 text-right font-medium">团队合计持仓</th>
                  <th className="px-3 py-2 text-right font-medium">团队合计价值</th>
                  {onSelectSeed && <th className="px-3 py-2 text-center font-medium">操作</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {related.slice(0, 20).map((r: TeamRelatedItem, idx) => {
                  const score = relatedScores?.[r.good_id];
                  const isAccumulating = typeof score === "number" && score >= 0.6;
                  return (
                    <tr key={r.good_id} className="transition-colors hover:bg-surface-hover">
                      <td className="px-3 py-2 text-ink-muted">#{idx + 1}</td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-ink-primary">
                          {r.good_name || `(未命名 #${r.good_id})`}
                        </div>
                        <div className="text-xs text-ink-muted">good_id: {r.good_id}</div>
                      </td>
                      <td className="px-3 py-2 text-right text-ink-secondary">
                        {r.overlap_count} / {data.seed_holder_count}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <span
                          className="font-semibold"
                          style={{ color: r.overlap_ratio >= 0.5 ? "#16a34a" : r.overlap_ratio >= 0.3 ? "#f59e0b" : "#9ca3af" }}
                        >
                          {formatPercent(r.overlap_ratio, 1)}
                        </span>
                      </td>
                      {hasScores && (
                        <td className="px-3 py-2 text-right">
                          {typeof score === "number" ? (
                            <span
                              className="font-semibold"
                              style={{ color: isAccumulating ? "#16a34a" : score <= 0.4 ? "#dc2626" : "#9ca3af" }}
                            >
                              {formatPercent(score, 1)}
                            </span>
                          ) : (
                            <span className="text-xs text-ink-muted">-</span>
                          )}
                        </td>
                      )}
                      <td className="px-3 py-2 text-right">{formatNumber(r.total_hold_in_team, 0)}</td>
                      <td className="px-3 py-2 text-right text-ink-secondary">
                        ¥{formatNumber(r.total_value_in_team, 0)}
                      </td>
                      {onSelectSeed && (
                        <td className="px-3 py-2 text-center">
                          <button
                            type="button"
                            onClick={() => onSelectSeed(r.good_id, r.good_name)}
                            className="rounded-md bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-100"
                          >
                            设为种子
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 主力跨品分布 */}
      <Card title="主力跨品分布" subtitle="每个种子主力还持有哪些其他品（跨品多者疑为核心团队）">
        {holders.length === 0 ? (
          <EmptyState title="暂无主力数据" description="该饰品暂无持仓主力。" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                  <th className="px-3 py-2 font-medium">主力</th>
                  <th className="px-3 py-2 text-right font-medium">种子品持仓</th>
                  <th className="px-3 py-2 text-right font-medium">跨品数</th>
                  <th className="px-3 py-2 text-center font-medium">核心团队</th>
                  <th className="px-3 py-2 font-medium">持有的其他品</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {holders.map((h: TeamHolderCross) => (
                  <tr key={h.steam_id} className="transition-colors hover:bg-surface-hover">
                    <td className="px-3 py-2 font-medium text-ink-primary">
                      {h.steam_name || h.steam_id}
                    </td>
                    <td className="px-3 py-2 text-right">{formatNumber(h.hold_in_seed, 0)}</td>
                    <td className="px-3 py-2 text-right text-ink-secondary">{h.cross_item_count}</td>
                    <td className="px-3 py-2 text-center">
                      {h.is_core ? <Badge variant="bull">核心</Badge> : <span className="text-xs text-ink-muted">-</span>}
                    </td>
                    <td className="px-3 py-2 text-xs text-ink-muted">
                      {h.cross_good_ids.length > 0
                        ? h.cross_good_ids.slice(0, 8).join(", ") + (h.cross_good_ids.length > 8 ? " ..." : "")
                        : "（无）"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 持仓关系网络图 */}
      <TeamNetworkChart data={data} relatedScores={relatedScores} onSelectSeed={onSelectSeed} />

      {coreHolders.length > 0 && (
        <p className="text-xs text-ink-muted">
          核心团队 {coreHolders.length} 人：{coreHolders.map((h) => h.steam_name || h.steam_id).join("、")}
        </p>
      )}
    </div>
  );
}

/**
 * 主力-饰品持仓关系网络图（force 布局）。
 *
 * 节点：种子品（中心）、主力（人形）、关联品（方块）。边表示持有关系。
 * 关联品节点颜色随吸货评分变化（绿=吸货、红=出货、灰=中性）。
 */
function TeamNetworkChart({
  data,
  relatedScores,
  onSelectSeed,
}: {
  data: TeamAnalysisResponse;
  relatedScores?: Record<string, number>;
  onSelectSeed?: (goodId: string, name?: string) => void;
}) {
  const { seed_good_id, holders_cross, related_items, team_summary } = data;
  const hasScores = relatedScores && Object.keys(relatedScores).length > 0;

  // ── 构造 echarts graph 数据 ──
  const nodes: Array<Record<string, unknown>> = [];
  const links: Array<Record<string, unknown>> = [];
  const categories = [
    { name: "种子品" },
    { name: "主力" },
    { name: "关联品" },
  ];

  // 种子品节点（中心，最大）
  nodes.push({
    id: `good:${seed_good_id}`,
    name: "种子品",
    symbolSize: 48,
    category: 0,
    itemStyle: { color: "#6366f1" },
    label: { show: true, position: "bottom", formatter: "种子品" },
  });

  // 主力节点
  for (const h of holders_cross) {
    const nodeId = `user:${h.steam_id}`;
    nodes.push({
      id: nodeId,
      name: h.steam_name || h.steam_id,
      symbolSize: h.is_core ? 36 : 24,
      category: 1,
      itemStyle: { color: h.is_core ? "#16a34a" : "#9ca3af" },
      label: { show: h.is_core, position: "bottom", formatter: h.steam_name || h.steam_id },
    });
    // 主力 → 种子品
    links.push({
      source: nodeId,
      target: `good:${seed_good_id}`,
      value: h.hold_in_seed,
      lineStyle: { width: Math.max(1, Math.min(8, h.hold_in_seed / 20)) },
    });
    // 主力 → 关联品
    for (const gid of h.cross_good_ids) {
      links.push({
        source: nodeId,
        target: `good:${gid}`,
        value: 1,
        lineStyle: { width: 1, opacity: 0.4 },
      });
    }
  }

  // 关联品节点（去重，仅展示 top-15 重合度最高的）
  const relatedToShow = related_items.slice(0, 15);
  for (const r of relatedToShow) {
    const score = relatedScores?.[r.good_id];
    const isAccumulating = typeof score === "number" && score >= 0.6;
    const isDistributing = typeof score === "number" && score <= 0.4;
    const color = isAccumulating ? "#16a34a" : isDistributing ? "#dc2626" : "#9ca3af";
    nodes.push({
      id: `good:${r.good_id}`,
      name: r.good_name || r.good_id,
      symbolSize: 20 + r.overlap_count * 4,
      category: 2,
      itemStyle: { color },
      label: {
        show: r.overlap_count >= 2,
        position: "bottom",
        formatter: r.good_name || r.good_id,
      },
    });
  }

  // 移除指向不存在节点的边（关联品 top-15 之外的）
  const nodeIds = new Set(nodes.map((n) => n.id as string));
  const validLinks = links.filter(
    (l) => nodeIds.has(l.source as string) && nodeIds.has(l.target as string),
  );

  const option: Record<string, unknown> = {
    tooltip: {
      formatter: (p: { dataType?: string; data?: Record<string, unknown> }) => {
        if (!p) return "";
        if (p.dataType === "node") {
          const d = p.data || {};
          return `<b>${d.name ?? ""}</b><br/>类别: ${categories[(d.category as number) ?? 0].name}`;
        }
        if (p.dataType === "edge") {
          const v = p.data?.value;
          return v ? `持仓: ${v}` : "持仓关系";
        }
        return "";
      },
    },
    legend: [
      {
        data: categories.map((c) => c.name),
        top: 8,
        textStyle: { fontSize: 11 },
      },
    ],
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        categories,
        data: nodes,
        links: validLinks,
        // 关联品节点点击事件通过 onEvents 处理
        force: {
          repulsion: 220,
          edgeLength: [50, 120],
          gravity: 0.12,
        },
        focusNodeAdjacency: true,
        lineStyle: { color: "source", curveness: 0.1, opacity: 0.5 },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 3 },
          label: { show: true },
        },
      },
    ],
  };

  return (
    <Card
      title="持仓关系网络图"
      subtitle="主力（圆点）与饰品（方块）的持仓关系；绿色关联品=吸货阶段，红色=出货，灰色=中性。可拖拽缩放，点击关联品节点设为新种子"
    >
      <EChart
        option={option}
        style={{ width: "100%", height: "420px" }}
        onEvents={{
          click: (params: unknown) => {
            const p = params as { dataType?: string; data?: Record<string, unknown> };
            if (p?.dataType !== "node" || !onSelectSeed) return;
            const id = p.data?.id as string | undefined;
            if (!id || !id.startsWith("good:") || id === `good:${seed_good_id}`) return;
            const gid = id.slice(5);
            const name = p.data?.name as string | undefined;
            onSelectSeed(gid, name);
          },
        }}
      />
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
        <span>核心团队 {team_summary.core_team_size} 人</span>
        <span>关联品 {team_summary.related_item_count} 个</span>
        {hasScores && <span>吸货评分着色：绿≥60% · 红≤40%</span>}
      </div>
    </Card>
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
  const itemGoodId = useGlobalStore((s) => s.itemGoodId);
  const platform = useGlobalStore((s) => s.platform);
  const setPlatform = useGlobalStore((s) => s.setPlatform);

  const meta = useMeta();
  const periods = meta?.supported_periods?.length ? meta.supported_periods : FALLBACK_PERIODS;

  // 分析模式：index=指数模式，item=单品模式
  const [mode, setMode] = useState<"index" | "item">(itemGoodId ? "item" : "index");
  // 单品输入框值（独立于全局 store，避免输入时全局联动）
  const [goodIdInput, setGoodIdInput] = useState(itemGoodId ?? "");
  // 通过名称搜索选中的饰品名（用于展示），与 goodIdInput 配合
  const [selectedItemName, setSelectedItemName] = useState("");
  // 单品价格指标选择
  const [itemKey, setItemKey] = useState<"sell_price" | "buy_price">("sell_price");

  // 初始化状态（挂载时自动查询一次）
  const status = useAsync((signal) => api.accumulation.status(signal), []);

  // 单品库存监控数据：goodIdInput 变化且为单品模式时自动拉取（先看数据，不加算法）
  const inventory = useAsync(
    (signal) => api.accumulation.itemInventory(goodIdInput, 20, signal),
    [goodIdInput],
    mode === "item" && goodIdInput.trim() !== "",
  );

  // 双轨融合吸货分析：按钮触发（含团队分析耗时约 10s，避免每次切换都拉取）
  const [fusedTrigger, setFusedTrigger] = useState(0);
  const fused = useAsync(
    (signal) => api.accumulation.analyzeFused(goodIdInput, period, platform, itemKey, true, signal),
    [goodIdInput, fusedTrigger, period, platform, itemKey],
    fusedTrigger > 0 && mode === "item" && goodIdInput.trim() !== "",
  );

  // 跨品主力团队识别：goodIdInput 变化且为单品模式时自动拉取（按钮触发，避免每次切换都拉取 N 个用户持仓）
  const [teamTrigger, setTeamTrigger] = useState(0);
  const team = useAsync(
    (signal) => api.accumulation.teamAnalysis(goodIdInput, 10, 2, signal),
    [goodIdInput, teamTrigger],
    teamTrigger > 0 && mode === "item" && goodIdInput.trim() !== "",
  );

  // 种子品历史栈：记录用户切换过的种子品，便于回溯二次分析路径
  const [seedHistory, setSeedHistory] = useState<Array<{ goodId: string; name: string }>>([]);

  // 关联品吸货评分联动：team 数据返回后，并发拉取每个关联品的吸货评分
  // 用于在关联品表与网络图中以颜色区分吸/出货阶段，并加权团队置信度
  const [relatedScores, setRelatedScores] = useState<Record<string, number>>({});
  useEffect(() => {
    if (!team.data || team.data.related_items.length === 0) {
      setRelatedScores({});
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    const items = team.data.related_items.slice(0, 10); // 限制并发数避免过载
    Promise.all(
      items.map(async (r) => {
        try {
          const res = await api.accumulation.analyzeItem(
            r.good_id,
            period,
            platform,
            "sell_price",
            controller.signal,
          );
          return [r.good_id, res.accumulation_score] as const;
        } catch {
          return [r.good_id, null] as const;
        }
      }),
    ).then((results) => {
      if (cancelled) return;
      const scores: Record<string, number> = {};
      for (const [gid, score] of results) {
        if (typeof score === "number") scores[gid] = score;
      }
      setRelatedScores(scores);
    });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [team.data, period, platform]);

  // 设为新种子：将当前种子压入历史栈，切换 goodIdInput 并自动触发团队分析
  const handleSelectSeed = (newGoodId: string, name?: string) => {
    setSeedHistory((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].goodId === goodIdInput) {
        // 避免重复压栈
        return prev;
      }
      return [...prev, { goodId: goodIdInput, name: selectedItemName }];
    });
    setGoodIdInput(newGoodId);
    setSelectedItemName(name ?? "");
    // 重置评分，待新 team 数据返回后重新拉取
    setRelatedScores({});
    setTeamTrigger((c) => c + 1);
  };

  // 回退到上一个种子品
  const handlePopSeed = () => {
    setSeedHistory((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      setGoodIdInput(last.goodId);
      setSelectedItemName(last.name);
      setRelatedScores({});
      setTeamTrigger((c) => c + 1);
      return prev.slice(0, -1);
    });
  };

  // 数据预热（按钮触发）
  const [initTrigger, setInitTrigger] = useState(0);
  const init = useAsync(
    (signal) => api.accumulation.init(undefined, undefined, signal),
    [initTrigger],
    initTrigger > 0,
  );

  // 单标的分析（按钮触发，捕获点击时的参数）
  const [analyzeTrigger, setAnalyzeTrigger] = useState(0);
  const [analyzeParams, setAnalyzeParams] = useState<{
    mode: "index" | "item";
    subIndex: string;
    goodId: string;
    period: string;
    platform: number;
    key: string;
  }>({ mode, subIndex, goodId: goodIdInput, period, platform, key: itemKey });
  const analysis = useAsync(
    (signal) =>
      analyzeParams.mode === "item"
        ? api.accumulation.analyzeItem(
            analyzeParams.goodId,
            analyzeParams.period,
            analyzeParams.platform,
            analyzeParams.key,
            signal,
          )
        : api.accumulation.analyze(analyzeParams.subIndex, analyzeParams.period, signal),
    [analyzeParams.mode, analyzeParams.subIndex, analyzeParams.goodId, analyzeParams.period, analyzeParams.platform, analyzeParams.key, analyzeTrigger],
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
    setAnalyzeParams({ mode, subIndex, goodId: goodIdInput, period, platform, key: itemKey });
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
  const canAnalyze = mode === "item" ? goodIdInput.trim() !== "" : subIndex.trim() !== "";

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">库存吸货分析</h1>
        <p className="mt-1 text-sm text-ink-muted">识别主力资金隐蔽建仓行为（支持指数与单品）</p>
      </div>

      {/* 分析参数 */}
      <Card title="分析参数" subtitle="选择分析模式并设置参数">
        <div className="space-y-4">
          {/* 模式切换 */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode("index")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === "index"
                  ? "bg-indigo-600 text-white"
                  : "bg-surface-hover text-ink-secondary hover:bg-surface-border"
              }`}
            >
              指数模式
            </button>
            <button
              type="button"
              onClick={() => setMode("item")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === "item"
                  ? "bg-indigo-600 text-white"
                  : "bg-surface-hover text-ink-secondary hover:bg-surface-border"
              }`}
            >
              单品模式
            </button>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            {mode === "index" ? (
              <TextInput
                label="标的 (sub_index)"
                value={subIndex}
                onChange={(e) => setSubIndex(e.target.value)}
                placeholder="如：饰品指数"
              />
            ) : (
              <>
                <div className="flex-1">
                  <label className="mb-1 block text-xs font-medium text-ink-secondary">
                    饰品名称搜索 → good_id
                  </label>
                  <ItemSearchBar
                    placeholder="输入饰品名称搜索，如「蝴蝶刀 | 渐变」"
                    onSelect={(item) => {
                      setGoodIdInput(item.good_id);
                      setSelectedItemName(item.name);
                    }}
                  />
                  {goodIdInput && (
                    <div className="mt-1.5 flex items-center gap-2 text-xs">
                      <Badge variant="bull">已选</Badge>
                      <span className="text-ink-primary">
                        {selectedItemName || "(未命名)"}
                      </span>
                      <span className="text-ink-muted">good_id: {goodIdInput}</span>
                    </div>
                  )}
                </div>
                <Select
                  label="平台"
                  value={String(platform)}
                  onChange={(e) => setPlatform(Number(e.target.value) as 1 | 2 | 3 | 4)}
                >
                  <option value="1">BUFF</option>
                  <option value="2">悠悠有品</option>
                  <option value="3">Steam</option>
                  <option value="4">C5GAME</option>
                </Select>
                <Select
                  label="价格指标"
                  value={itemKey}
                  onChange={(e) => setItemKey(e.target.value as "sell_price" | "buy_price")}
                >
                  <option value="sell_price">卖价</option>
                  <option value="buy_price">买价</option>
                </Select>
              </>
            )}
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
              disabled={!canAnalyze}
            >
              执行分析
            </Button>
          </div>
          {mode === "item" && (
            <p className="text-xs text-ink-muted">
              提示：单品模式下数据来自 CSQAQ /info/chart 价格序列，按周期聚合为 OHLC 后分析。
              在上方搜索框输入饰品名称即可自动填入 good_id，无需手动查找。
            </p>
          )}
        </div>
      </Card>

      {/* 双轨融合吸货分析（仅单品模式，按钮触发） */}
      {mode === "item" && goodIdInput.trim() !== "" && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-ink-secondary">双轨融合吸货分析</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                K线行为 × 库存行为 交叉验证，识别明牌/隐蔽/误判三种模式（含团队分析约 10s）
              </p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setFusedTrigger((c) => c + 1)}
              loading={fused.loading}
            >
              执行融合分析
            </Button>
          </div>
          {fused.loading ? (
            <Card>
              <Spinner className="py-10" />
            </Card>
          ) : fused.error ? (
            <Card>
              <ErrorState message={fused.error} onRetry={() => setFusedTrigger((c) => c + 1)} />
            </Card>
          ) : fused.data ? (
            <FusedAnalysisPanel data={fused.data} />
          ) : (
            <Card>
              <EmptyState
                title="点击「执行融合分析」"
                description="将并发拉取 K线、库存、团队数据，输出双轨融合吸货评分与证据链。"
              />
            </Card>
          )}
        </section>
      )}

      {/* 单品库存监控数据（仅单品模式，先看数据不加算法） */}
      {mode === "item" && goodIdInput.trim() !== "" && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-secondary">库存监控数据</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => inventory.refetch()}
              loading={inventory.loading}
            >
              刷新库存
            </Button>
          </div>
          {inventory.loading ? (
            <Card>
              <Spinner className="py-10" />
            </Card>
          ) : inventory.error ? (
            <Card>
              <ErrorState message={inventory.error} onRetry={() => inventory.refetch()} />
            </Card>
          ) : !inventory.data ? (
            <Card>
              <EmptyState
                title="尚无库存数据"
                description="搜索并选择饰品后，将自动拉取该饰品的主力持有量与买卖变动。"
              />
            </Card>
          ) : (
            <ItemInventoryPanel data={inventory.data} />
          )}
        </section>
      )}

      {/* 跨品主力团队识别（仅单品模式，按钮触发） */}
      {mode === "item" && goodIdInput.trim() !== "" && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-ink-secondary">跨品主力团队识别</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                分析种子品 top-10 主力的全量持仓，识别是否同一团队跨品操作（耗时约 10s）
              </p>
            </div>
            <div className="flex items-center gap-2">
              {seedHistory.length > 0 && (
                <Button variant="ghost" size="sm" onClick={handlePopSeed}>
                  ← 回到上一种子
                </Button>
              )}
              <Button
                variant="primary"
                size="sm"
                onClick={() => setTeamTrigger((c) => c + 1)}
                loading={team.loading}
              >
                {team.data ? "重新分析" : "开始团队分析"}
              </Button>
            </div>
          </div>

          {/* 种子品历史栈 */}
          {seedHistory.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-surface-border bg-surface-hover px-3 py-2 text-xs">
              <span className="text-ink-muted">分析路径：</span>
              {seedHistory.map((s, i) => (
                <span key={`${s.goodId}-${i}`} className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setGoodIdInput(s.goodId);
                      setSelectedItemName(s.name);
                      setRelatedScores({});
                      setTeamTrigger((c) => c + 1);
                      // 截断到点击位置
                      setSeedHistory((prev) => prev.slice(0, i));
                    }}
                    className="text-brand-700 hover:underline"
                  >
                    {s.name || s.goodId}
                  </button>
                  <span className="text-ink-muted">→</span>
                </span>
              ))}
              <span className="font-medium text-ink-primary">{selectedItemName || goodIdInput}</span>
            </div>
          )}

          {/* 关联品吸货评分加载提示 */}
          {team.data && Object.keys(relatedScores).length === 0 && team.data.related_items.length > 0 && (
            <div className="flex items-center gap-2 text-xs text-ink-muted">
              <Spinner size="sm" />
              <span>正在并发拉取关联品吸货评分用于联动着色...</span>
            </div>
          )}

          {team.loading ? (
            <Card>
              <Spinner className="py-10" />
            </Card>
          ) : team.error ? (
            <Card>
              <ErrorState message={team.error} onRetry={() => setTeamTrigger((c) => c + 1)} />
            </Card>
          ) : !team.data ? (
            <Card>
              <EmptyState
                title="尚未执行团队分析"
                description="点击「开始团队分析」按钮，将拉取种子品主力各自的全量持仓，识别跨品协同信号。"
              />
            </Card>
          ) : (
            <TeamAnalysisPanel
              data={team.data}
              onSelectSeed={handleSelectSeed}
              relatedScores={relatedScores}
            />
          )}
        </section>
      )}

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
