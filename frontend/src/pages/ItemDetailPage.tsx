import { useMemo } from "react";
import { useParams } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { Card, StatCard } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { Select } from "../components/ui/Select";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { useGlobalStore, type ChartKey, type Platform } from "../store/globalStore";
import { formatPrice, formatNumber, formatPercent } from "../lib/format";

// ── 类型定义 ──────────────────────────────────────────────

/** 单平台数据（7 平台之一的 10 个字段）。 */
interface PlatformData {
  sell_price: number | null;
  buy_price: number | null;
  sell_num: number | null;
  buy_num: number | null;
  short_lease_price: number | null;
  long_lease_price: number | null;
  short_lease_annual: number | null;
  long_lease_annual: number | null;
  lease_num: number | null;
  transfer_price: number | null;
}

/** 单品详情（CSQAQ /info/good 展开后的扁平结构）。 */
interface ItemDetail {
  good_id: string;
  name: string;
  img: string;
  min_float: number | null;
  max_float: number | null;
  quality: string | null;
  category: string | null;
  big_category: string | null;
  supply: number | null;
  hot_rank: number | null;
  hot_rank_change: number | null;
  buff: PlatformData | null;
  yyyp: PlatformData | null;
  steam: PlatformData | null;
  c5: PlatformData | null;
  igxe: PlatformData | null;
  eco: PlatformData | null;
  r8: PlatformData | null;
  chg_1: number | null;
  chg_7: number | null;
  chg_30: number | null;
  chg_180: number | null;
  chg_rate_1: number | null;
  chg_rate_7: number | null;
  chg_rate_30: number | null;
  chg_rate_180: number | null;
}

/** 存世量走势数据点。 */
interface SupplyPoint {
  date: string;
  supply: number;
}

/** 单品图表数据点。 */
interface ChartPoint {
  timestamp: string;
  value: number;
}

// ── 常量配置 ──────────────────────────────────────────────

/** 7 平台行配置：详情对象上的字段名 -> 展示中文名。 */
const PLATFORM_ROWS: { key: keyof ItemDetail; label: string }[] = [
  { key: "buff", label: "BUFF" },
  { key: "yyyp", label: "悠悠有品" },
  { key: "steam", label: "Steam" },
  { key: "c5", label: "C5GAME" },
  { key: "igxe", label: "IGXE" },
  { key: "eco", label: "ECOSteam" },
  { key: "r8", label: "R8GAME" },
];

/** 数值类型：价格 / 数量 / 百分比（小数）。 */
type ColumnType = "price" | "number" | "percent";

/** 价格对比表列配置。 */
interface TableColumn {
  field: keyof PlatformData;
  label: string;
  type: ColumnType;
}

const TABLE_COLUMNS: TableColumn[] = [
  { field: "sell_price", label: "在售价", type: "price" },
  { field: "buy_price", label: "求购价", type: "price" },
  { field: "sell_num", label: "在售量", type: "number" },
  { field: "buy_num", label: "求购量", type: "number" },
  { field: "short_lease_price", label: "短租", type: "price" },
  { field: "long_lease_price", label: "长租", type: "price" },
  { field: "short_lease_annual", label: "短租年化", type: "percent" },
  { field: "long_lease_annual", label: "长租年化", type: "percent" },
  { field: "lease_num", label: "在租量", type: "number" },
  { field: "transfer_price", label: "过户价", type: "price" },
];

/** 图表指标选项：ChartKey -> 中文标签。 */
const CHART_KEY_OPTIONS: { value: ChartKey; label: string }[] = [
  { value: "sell_price", label: "在售价" },
  { value: "buy_price", label: "求购价" },
  { value: "short_lease_price", label: "短租价" },
  { value: "long_lease_price", label: "长租价" },
  { value: "lease_annual", label: "短租年化" },
  { value: "long_lease_annual", label: "长租年化" },
  { value: "sell_num", label: "在售量" },
  { value: "buy_num", label: "求购量" },
  { value: "lease_num", label: "在租量" },
  { value: "turnover_number", label: "成交量" },
  { value: "transfer_price", label: "过户价" },
];

/** 图表平台选项：1-BUFF / 2-悠悠有品 / 3-Steam / 4-C5GAME。 */
const CHART_PLATFORM_OPTIONS: { value: Platform; label: string }[] = [
  { value: 1, label: "BUFF" },
  { value: 2, label: "悠悠有品" },
  { value: 3, label: "Steam" },
  { value: 4, label: "C5GAME" },
];

/** 图表周期选项（天）。 */
const CHART_PERIOD_OPTIONS: { value: number; label: string }[] = [
  { value: 7, label: "7天" },
  { value: 15, label: "15天" },
  { value: 30, label: "30天" },
  { value: 90, label: "90天" },
  { value: 180, label: "180天" },
  { value: 365, label: "1年" },
  { value: 1095, label: "3年" },
];

/** 涨跌卡片配置：涨跌率字段 + 涨跌额字段 + 标签。 */
const CHANGE_CARDS: {
  rateField: keyof ItemDetail;
  amountField: keyof ItemDetail;
  label: string;
}[] = [
  { rateField: "chg_rate_1", amountField: "chg_1", label: "1日涨跌" },
  { rateField: "chg_rate_7", amountField: "chg_7", label: "7日涨跌" },
  { rateField: "chg_rate_30", amountField: "chg_30", label: "30日涨跌" },
  { rateField: "chg_rate_180", amountField: "chg_180", label: "180日涨跌" },
];

// ── 辅助函数 ──────────────────────────────────────────────

/**
 * 从可能被 `{ data: [...] }` 包裹的响应中提取数组，
 * 兼容后端直接返回数组的情况。
 */
function toArray<T>(res: unknown): T[] {
  if (Array.isArray(res)) return res as T[];
  if (res && typeof res === "object" && Array.isArray((res as { data?: unknown }).data)) {
    return (res as { data: T[] }).data;
  }
  return [];
}

/**
 * 从可能被 `{ data: {...} }` 包裹的响应中提取详情对象，
 * 兼容后端直接返回扁平对象的情况。
 */
function toDetail(res: unknown): ItemDetail | null {
  if (!res || typeof res !== "object") return null;
  const obj = res as Record<string, unknown>;
  const inner = obj.data;
  if (inner && typeof inner === "object" && !Array.isArray(inner)) {
    const d = inner as Record<string, unknown>;
    if (d.good_id !== undefined || d.name !== undefined || d.buff !== undefined) {
      return d as unknown as ItemDetail;
    }
  }
  if (obj.good_id !== undefined || obj.name !== undefined || obj.buff !== undefined) {
    return obj as unknown as ItemDetail;
  }
  return null;
}

/** 判断图表指标的类型。 */
function chartKeyType(key: ChartKey): ColumnType {
  if (key === "lease_annual" || key === "long_lease_annual") return "percent";
  if (key === "sell_num" || key === "buy_num" || key === "lease_num" || key === "turnover_number") {
    return "number";
  }
  return "price";
}

/** 按类型格式化表格单元格。 */
function formatCell(type: ColumnType, value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  if (type === "percent") return formatPercent(value);
  if (type === "number") return formatNumber(value, 0);
  return formatPrice(value);
}

/** 按指标类型格式化图表数值。 */
function formatChartValue(key: ChartKey, value: number | null | undefined): string {
  return formatCell(chartKeyType(key), value);
}

/** 格式化涨跌率（值已为百分数，如 5.0 表示 5%）。 */
function formatSignedRate(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

/** 格式化涨跌额（绝对值，带正负号）。 */
function formatSignedAmount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, 2)}`;
}

/** 根据数值正负返回 StatCard 颜色语义。 */
function changeColor(value: number | null | undefined): "bull" | "bear" | "neutral" {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return "neutral";
  return value > 0 ? "bull" : "bear";
}

/** 品质 -> Badge 颜色。 */
function qualityVariant(
  quality: string | null | undefined,
): "default" | "bull" | "bear" | "neutral" | "info" {
  const q = (quality ?? "").trim();
  if (q === "隐秘" || q === "违禁") return "bear";
  if (q === "受限" || q === "保密") return "neutral";
  if (q === "军规级" || q === "卓越") return "info";
  return "default";
}

// ── 页面组件 ──────────────────────────────────────────────

export default function ItemDetailPage() {
  const { goodId } = useParams<{ goodId: string }>();
  const platform = useGlobalStore((s) => s.platform);
  const chartKey = useGlobalStore((s) => s.chartKey);
  const chartPeriod = useGlobalStore((s) => s.chartPeriod);
  const setPlatform = useGlobalStore((s) => s.setPlatform);
  const setChartKey = useGlobalStore((s) => s.setChartKey);
  const setChartPeriod = useGlobalStore((s) => s.setChartPeriod);

  const effectiveGoodId = goodId ?? "";

  // 详情数据（7 平台 50+ 字段）
  const detail = useAsync<unknown>(
    (signal) =>
      effectiveGoodId
        ? api.item.detail(effectiveGoodId, signal)
        : Promise.resolve(null),
    [effectiveGoodId],
  );
  const { refetch: refetchDetail } = detail;

  // 存世量走势（近 180 天）
  const supply = useAsync<unknown>(
    (signal) =>
      effectiveGoodId
        ? api.item.supply(effectiveGoodId, signal)
        : Promise.resolve(null),
    [effectiveGoodId],
  );
  const { refetch: refetchSupply } = supply;

  // 单品图表数据（指标 × 平台 × 周期）
  const chart = useAsync<unknown>(
    (signal) =>
      effectiveGoodId
        ? api.item.chart(
            {
              good_id: effectiveGoodId,
              key: chartKey,
              platform,
              period: chartPeriod,
              style: "all_style",
            },
            signal,
          )
        : Promise.resolve(null),
    [effectiveGoodId, chartKey, platform, chartPeriod],
  );
  const { refetch: refetchChart } = chart;

  // 派生数据
  const item = useMemo(() => toDetail(detail.data), [detail.data]);
  const supplyPoints = useMemo(() => toArray<SupplyPoint>(supply.data), [supply.data]);
  const chartPoints = useMemo(() => toArray<ChartPoint>(chart.data), [chart.data]);

  // 图表展示文案
  const chartKeyLabel =
    CHART_KEY_OPTIONS.find((o) => o.value === chartKey)?.label ?? chartKey;
  const platformLabel =
    CHART_PLATFORM_OPTIONS.find((o) => o.value === platform)?.label ?? String(platform);
  const isPercentKey = chartKeyType(chartKey) === "percent";

  // 价格走势折线图配置
  const chartOption = useMemo(() => {
    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        formatter: (params: unknown) => {
          const arr = params as { axisValue?: string; value?: number }[];
          const p = Array.isArray(arr) ? arr[0] : arr;
          return `${p?.axisValue ?? ""}<br/>${chartKeyLabel}: <b>${formatChartValue(
            chartKey,
            p?.value,
          )}</b>`;
        },
      },
      grid: { left: 64, right: 24, top: 24, bottom: 56 },
      xAxis: {
        type: "category",
        data: chartPoints.map((p) => p.timestamp),
        boundaryGap: false,
        axisLabel: { fontSize: 10 },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: {
          fontSize: 10,
          formatter: (v: number) => (isPercentKey ? formatPercent(v) : formatPrice(v)),
        },
        splitLine: { show: true, lineStyle: { type: "dashed" } },
      },
      dataZoom: [
        { type: "inside", start: 0, end: 100 },
        { type: "slider", start: 0, end: 100, height: 18, bottom: 28 },
      ],
      series: [
        {
          name: `${platformLabel} · ${chartKeyLabel}`,
          type: "line",
          data: chartPoints.map((p) => p.value),
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
          lineStyle: { width: 2, color: "#2563eb" },
          itemStyle: { color: "#2563eb" },
        },
      ],
    };
  }, [chartPoints, chartKey, chartKeyLabel, platformLabel, isPercentKey]);

  // 存世量面积图配置
  const supplyOption = useMemo(() => {
    return {
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const arr = params as { axisValue?: string; value?: number }[];
          const p = Array.isArray(arr) ? arr[0] : arr;
          return `${p?.axisValue ?? ""}<br/>存世量: <b>${formatNumber(
            p?.value ?? Number.NaN,
            0,
          )}</b>`;
        },
      },
      grid: { left: 64, right: 24, top: 24, bottom: 56 },
      xAxis: {
        type: "category",
        data: supplyPoints.map((p) => p.date),
        boundaryGap: false,
        axisLabel: { fontSize: 10 },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: {
          fontSize: 10,
          formatter: (v: number) => formatNumber(v, 0),
        },
        splitLine: { show: true, lineStyle: { type: "dashed" } },
      },
      dataZoom: [
        { type: "inside", start: 0, end: 100 },
        { type: "slider", start: 0, end: 100, height: 18, bottom: 28 },
      ],
      series: [
        {
          name: "存世量",
          type: "line",
          data: supplyPoints.map((p) => p.supply),
          smooth: true,
          symbol: "none",
          lineStyle: { width: 2, color: "#16a34a" },
          itemStyle: { color: "#16a34a" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(22, 163, 74, 0.28)" },
                { offset: 1, color: "rgba(22, 163, 74, 0.02)" },
              ],
            },
          },
        },
      ],
    };
  }, [supplyPoints]);

  // 未指定饰品 ID
  if (!goodId) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">饰品详情</h1>
          <p className="mt-1 text-sm text-ink-muted">
            查看单件饰品的 7 平台价格、涨跌与存世量走势
          </p>
        </div>
        <Card>
          <EmptyState
            title="未指定饰品"
            description="请从饰品列表或搜索结果进入详情页。"
          />
        </Card>
      </div>
    );
  }

  // 详情是否处于无数据的初始加载/错误态
  const detailLoading = detail.loading && !item;
  const detailError = detail.error && !item;

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">饰品详情</h1>
        <p className="mt-1 text-sm text-ink-muted">
          查看单件饰品的 7 平台价格、涨跌与存世量走势
        </p>
      </div>

      {/* 1. 饰品头部信息 */}
      <Card bodyClassName="p-0">
        {detailLoading ? (
          <Spinner className="py-12" />
        ) : detailError ? (
          <ErrorState message={detail.error ?? "加载失败"} onRetry={refetchDetail} />
        ) : !item ? (
          <EmptyState title="未找到饰品" description="可能该饰品已下架或 ID 无效。" />
        ) : (
          <div className="flex flex-col gap-5 p-5 sm:flex-row">
            {/* 饰品图片 */}
            <div className="shrink-0">
              {item.img ? (
                <img
                  src={item.img}
                  alt={item.name ?? "饰品图片"}
                  className="h-40 w-40 rounded-lg border border-surface-border bg-surface-hover object-contain"
                  loading="lazy"
                />
              ) : (
                <div className="flex h-40 w-40 items-center justify-center rounded-lg border border-surface-border bg-surface-hover text-xs text-ink-muted">
                  暂无图片
                </div>
              )}
            </div>
            {/* 饰品信息 */}
            <div className="flex-1 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                {item.quality && <Badge variant={qualityVariant(item.quality)}>{item.quality}</Badge>}
                {item.category && <Badge variant="default">{item.category}</Badge>}
                {item.big_category && <Badge variant="info">{item.big_category}</Badge>}
              </div>
              <h2 className="text-xl font-bold text-ink-primary">
                {item.name ?? `饰品 #${item.good_id ?? goodId}`}
              </h2>
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-secondary">
                <span>
                  磨损范围：
                  <span className="font-medium text-ink-primary">
                    {item.min_float !== null && item.min_float !== undefined
                      ? formatNumber(item.min_float, 4)
                      : "--"}
                    {" ~ "}
                    {item.max_float !== null && item.max_float !== undefined
                      ? formatNumber(item.max_float, 4)
                      : "--"}
                  </span>
                </span>
                <span>
                  存世量：
                  <span className="font-medium text-ink-primary">
                    {item.supply !== null && item.supply !== undefined
                      ? formatNumber(item.supply, 0)
                      : "--"}
                  </span>
                </span>
                <span>
                  热度排名：
                  <span className="font-medium text-ink-primary">
                    {item.hot_rank !== null && item.hot_rank !== undefined
                      ? `#${item.hot_rank}`
                      : "--"}
                  </span>
                  {item.hot_rank_change !== null &&
                    item.hot_rank_change !== undefined &&
                    item.hot_rank_change !== 0 && (
                      <span className="ml-1 text-xs text-ink-muted">
                        较前 {item.hot_rank_change > 0 ? "↑" : "↓"}
                        {Math.abs(item.hot_rank_change)}
                      </span>
                    )}
                </span>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* 2. 7 平台价格对比表 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">7 平台价格对比</h2>
        <Card
          title="多平台价格"
          subtitle="BUFF / 悠悠有品 / Steam / C5GAME / IGXE / ECOSteam / R8GAME"
          bodyClassName="p-0"
        >
          {detailLoading ? (
            <Spinner className="py-10" />
          ) : !item ? (
            <EmptyState title="暂无价格数据" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-border bg-surface-hover text-left text-xs text-ink-muted">
                    <th className="px-5 py-3 font-medium">平台</th>
                    {TABLE_COLUMNS.map((col) => (
                      <th key={col.field} className="px-4 py-3 text-right font-medium">
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {PLATFORM_ROWS.map((row) => {
                    const data = item[row.key] as PlatformData | null;
                    return (
                      <tr key={row.key} className="transition-colors hover:bg-surface-hover">
                        <td className="px-5 py-3 font-medium text-ink-primary">{row.label}</td>
                        {TABLE_COLUMNS.map((col) => (
                          <td
                            key={col.field}
                            className="px-4 py-3 text-right text-ink-secondary tabular-nums"
                          >
                            {data ? formatCell(col.type, data[col.field]) : "--"}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      {/* 3. 价格涨跌卡片 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">价格涨跌</h2>
        {detailLoading ? (
          <Spinner className="py-10" />
        ) : !item ? (
          <Card>
            <EmptyState title="暂无涨跌数据" />
          </Card>
        ) : (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {CHANGE_CARDS.map((card) => {
              const rate = item[card.rateField] as number | null;
              const amount = item[card.amountField] as number | null;
              return (
                <StatCard
                  key={card.label}
                  label={card.label}
                  value={formatSignedRate(rate)}
                  color={changeColor(rate)}
                  hint={`涨跌额 ${formatSignedAmount(amount)}`}
                />
              );
            })}
          </div>
        )}
      </section>

      {/* 4. 价格走势图表 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">价格走势</h2>
        <Card
          title="单品图表"
          subtitle={`${platformLabel} · ${chartKeyLabel} · 近 ${chartPeriod} 天`}
        >
          {/* 指标 / 平台 / 周期选择器（同步至全局 store） */}
          <div className="mb-4 flex flex-wrap items-end gap-3">
            <Select
              label="指标"
              value={chartKey}
              onChange={(e) => setChartKey(e.target.value as ChartKey)}
            >
              {CHART_KEY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
            <Select
              label="平台"
              value={String(platform)}
              onChange={(e) => setPlatform(Number(e.target.value) as Platform)}
            >
              {CHART_PLATFORM_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
            <Select
              label="周期"
              value={String(chartPeriod)}
              onChange={(e) => setChartPeriod(Number(e.target.value))}
            >
              {CHART_PERIOD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>

          {chart.loading && chartPoints.length === 0 ? (
            <Spinner className="py-10" />
          ) : chart.error && chartPoints.length === 0 ? (
            <ErrorState message={chart.error ?? "加载失败"} onRetry={refetchChart} />
          ) : chartPoints.length === 0 ? (
            <EmptyState
              title="暂无图表数据"
              description="该指标在所选平台与周期下暂无数据。"
            />
          ) : (
            <ReactECharts option={chartOption} style={{ height: 380, width: "100%" }} />
          )}
        </Card>
      </section>

      {/* 5. 存世量走势 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">存世量走势</h2>
        <Card title="存世量" subtitle="近 180 天存世量变化趋势">
          {supply.loading && supplyPoints.length === 0 ? (
            <Spinner className="py-10" />
          ) : supply.error && supplyPoints.length === 0 ? (
            <ErrorState message={supply.error ?? "加载失败"} onRetry={refetchSupply} />
          ) : supplyPoints.length === 0 ? (
            <EmptyState
              title="暂无存世量数据"
              description="该饰品暂无存世量历史记录。"
            />
          ) : (
            <ReactECharts option={supplyOption} style={{ height: 320, width: "100%" }} />
          )}
        </Card>
      </section>
    </div>
  );
}
