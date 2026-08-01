import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { Card } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { Select } from "../components/ui/Select";
import { Button } from "../components/ui/Button";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { useGlobalStore } from "../store/globalStore";
import { formatPrice, formatNumber, formatPercent } from "../lib/format";

// ── 类型定义 ──────────────────────────────────────────────

/** 价格走势数据点。 */
interface PricePoint {
  timestamp: string;
  value: number;
}

/** 涨跌排行榜单项。 */
interface RankListItem {
  good_id: string;
  name: string;
  img: string;
  sell_price: number | null;
  buy_price: number | null;
  sell_num: number | null;
  buy_num: number | null;
  chg_1: number | null;
  chg_7: number | null;
  chg_30: number | null;
  supply: number | null;
  total_market_value: number | null;
  recently_price?: PricePoint[];
}

/** 饰品列表单项。 */
interface PageListItem {
  good_id: string;
  name: string;
  img: string;
  quality: string;
  category: string;
  type: string;
  sell_price: number | null;
  buy_price: number | null;
}

/** 热门系列单项。 */
interface SeriesListItem {
  series_id: string;
  name: string;
  chg_1: number;
  chg_7: number;
  chg_15: number;
  chg_30: number;
  item_count: number;
  total_floor_value: number;
  recently_price: PricePoint[];
}

/** 分页响应结构。 */
interface PagedData<T> {
  total: number;
  page_index: number;
  page_size: number;
  data: T[];
}

// ── 常量配置 ──────────────────────────────────────────────

/** 每页条数。 */
const PAGE_SIZE = 20;

/** 选项卡配置。 */
const TABS = [
  { key: "rank", label: "涨跌排行" },
  { key: "items", label: "饰品列表" },
  { key: "series", label: "热门系列" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/** 排序方式选项（值传给 api.rank.list 的 sort 参数）。 */
const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "chg_1_desc", label: "1日涨幅" },
  { value: "chg_1_asc", label: "1日跌幅" },
  { value: "chg_7_desc", label: "7日涨幅" },
  { value: "chg_30_desc", label: "30日涨幅" },
  { value: "sell_num_desc", label: "成交量" },
];

/** 饰品类型筛选选项。 */
const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "全部" },
  { value: "刀", label: "刀" },
  { value: "手套", label: "手套" },
  { value: "步枪", label: "步枪" },
  { value: "手枪", label: "手枪" },
  { value: "狙击枪", label: "狙击枪" },
  { value: "微型冲锋枪", label: "微型冲锋枪" },
  { value: "重型武器", label: "重型武器" },
];

/** 饰品品质筛选选项。 */
const QUALITY_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "全部" },
  { value: "消费级", label: "消费级" },
  { value: "工业级", label: "工业级" },
  { value: "军规级", label: "军规级" },
  { value: "受限", label: "受限" },
  { value: "保密", label: "保密" },
  { value: "隐秘", label: "隐秘" },
  { value: "违禁", label: "违禁" },
];

// ── 辅助函数 ──────────────────────────────────────────────

/**
 * 从 unknown 分页响应中安全提取 { total, page_index, page_size, data }。
 * 兼容后端缺少分页字段或 data 字段缺失的情况。
 */
function extractPaged<T>(res: unknown): PagedData<T> {
  if (res && typeof res === "object") {
    const obj = res as Record<string, unknown>;
    const data = Array.isArray(obj.data) ? (obj.data as T[]) : [];
    const total = typeof obj.total === "number" ? obj.total : data.length;
    const pageIndex = typeof obj.page_index === "number" ? obj.page_index : 0;
    const pageSize = typeof obj.page_size === "number" ? obj.page_size : data.length;
    return { total, page_index: pageIndex, page_size: pageSize, data };
  }
  return { total: 0, page_index: 0, page_size: 0, data: [] };
}

/**
 * 从 unknown 列表响应中安全提取数组，
 * 兼容 { data: [] } 包裹与裸数组两种形式。
 */
function extractList<T>(res: unknown): T[] {
  if (Array.isArray(res)) return res as T[];
  if (res && typeof res === "object" && Array.isArray((res as { data?: unknown }).data)) {
    return (res as { data: T[] }).data;
  }
  return [];
}

/**
 * 格式化可空数值。formatNumber 不接受 null，此处统一兜底为 "--"。
 */
function fmtNum(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return formatNumber(value, digits);
}

/**
 * 格式化带符号的涨跌幅百分比。
 * 约定 chg_* 字段以百分数数值存储（如 5.2 表示 5.2%），
 * 除以 100 转为小数后复用 formatPercent 统一格式化。
 */
function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatPercent(value / 100)}`;
}

/** 根据涨跌值返回文字颜色 class：上涨绿、下跌红、持平/缺失灰。 */
function chgColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "text-ink-secondary";
  }
  return value > 0 ? "text-bull" : "text-bear";
}

/** 根据涨跌值返回迷你走势图颜色（hex）：上涨绿、下跌红、持平/缺失灰。 */
function chgSparkColor(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return "#94a3b8";
  return value > 0 ? "#16a34a" : "#dc2626";
}

/** 品质 -> Badge 颜色语义。 */
function qualityVariant(
  quality: string | null | undefined,
): "default" | "bull" | "bear" | "neutral" | "info" {
  const q = (quality ?? "").trim();
  if (q === "隐秘" || q === "违禁") return "bear";
  if (q === "受限" || q === "保密") return "neutral";
  if (q === "军规级" || q === "卓越") return "info";
  return "default";
}

/** 构建迷你走势图 ECharts 配置：无坐标轴、无提示框，仅一条折线带浅色填充。 */
function buildSparklineOption(points: PricePoint[], color: string) {
  return {
    grid: { left: 2, right: 2, top: 4, bottom: 4, containLabel: false },
    xAxis: { type: "category", show: false, boundaryGap: false },
    yAxis: { type: "value", show: false, scale: true },
    tooltip: { show: false },
    series: [
      {
        type: "line",
        data: points.map((p) => p.value),
        smooth: true,
        symbol: "none",
        lineStyle: { width: 1.5, color },
        areaStyle: { color, opacity: 0.12 },
      },
    ],
  };
}

// ── 子组件 ────────────────────────────────────────────────

/** 迷你折线走势图，数据不足两点时展示占位符。 */
function Sparkline({
  points,
  color,
  height = 40,
  width = 120,
}: {
  points: PricePoint[];
  color: string;
  height?: number;
  width?: number | string;
}) {
  const option = useMemo(() => buildSparklineOption(points, color), [points, color]);
  if (!points || points.length < 2) {
    return <span className="text-xs text-ink-muted">--</span>;
  }
  return <ReactECharts option={option} style={{ height, width }} />;
}

/** 分页器：总条数 + 上一页/下一页 + 当前页码。 */
function Pagination({
  total,
  page,
  pageSize,
  onPageChange,
}: {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-surface-border px-5 py-3">
      <span className="text-xs text-ink-muted">共 {formatNumber(total, 0)} 条</span>
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant="secondary"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          上一页
        </Button>
        <span className="text-xs text-ink-secondary">
          第 {page} / {totalPages} 页
        </span>
        <Button
          size="sm"
          variant="secondary"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          下一页
        </Button>
      </div>
    </div>
  );
}

// ── 页面组件 ──────────────────────────────────────────────

/**
 * 排行榜页面 —— CSQAQ 量化平台的饰品行情排行入口。
 *
 * 三个选项卡：
 * 1. 涨跌排行：按 1/7/30 日涨跌或成交量排序，展示排行表与迷你走势图
 * 2. 饰品列表：按类型/品质筛选全量饰品，分页浏览
 * 3. 热门系列：以卡片网格展示系列行情概览与近期走势
 *
 * - 三组数据各自独立 useAsync 请求，切换选项卡不丢失已加载内容
 * - 行点击写入全局 itemGoodId 并跳转至 /item/:good_id
 * - 每个选项卡独立处理 loading / error / empty 三态
 */
export default function RankingPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("rank");

  // 涨跌排行 tab 状态
  const [sort, setSort] = useState<string>("chg_1_desc");
  const [rankPage, setRankPage] = useState(1);

  // 饰品列表 tab 状态
  const [filterType, setFilterType] = useState("");
  const [filterQuality, setFilterQuality] = useState("");
  const [itemPage, setItemPage] = useState(1);

  const navigate = useNavigate();
  const setItemGoodId = useGlobalStore((s) => s.setItemGoodId);

  // 涨跌排行数据 — 仅在 rank 选项卡激活时请求，避免并发触发 429
  const rankAsync = useAsync(
    (signal) => api.rank.list(sort, rankPage, PAGE_SIZE, signal),
    [sort, rankPage],
    activeTab === "rank",
  );

  // 饰品列表数据 — 仅在 items 选项卡激活时请求
  const itemAsync = useAsync(
    (signal) =>
      api.rank.items({ type: filterType, quality: filterQuality }, itemPage, PAGE_SIZE, signal),
    [filterType, filterQuality, itemPage],
    activeTab === "items",
  );

  // 热门系列数据 — 仅在 series 选项卡激活时请求
  const seriesAsync = useAsync(
    (signal) => api.rank.series(signal),
    [],
    activeTab === "series",
  );

  // 派生数据：从 unknown 响应中安全提取
  const rankData = useMemo(() => extractPaged<RankListItem>(rankAsync.data), [rankAsync.data]);
  const itemData = useMemo(() => extractPaged<PageListItem>(itemAsync.data), [itemAsync.data]);
  const seriesData = useMemo(() => extractList<SeriesListItem>(seriesAsync.data), [seriesAsync.data]);

  /** 点击行：写入全局 itemGoodId 并跳转饰品详情。 */
  function handleRowClick(goodId: string) {
    setItemGoodId(goodId);
    navigate(`/item/${goodId}`);
  }

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">排行榜</h1>
        <p className="mt-1 text-sm text-ink-muted">
          查看饰品涨跌排行、全量饰品列表与热门系列行情概览
        </p>
      </div>

      {/* 选项卡 */}
      <div className="inline-flex items-center gap-1 rounded-lg border border-surface-border bg-surface-card p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-brand-600 text-white"
                : "text-ink-secondary hover:bg-surface-hover"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab 1: 涨跌排行 ── */}
      {activeTab === "rank" && (
        <Card bodyClassName="p-0">
          {/* 排序选择器 */}
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-surface-border px-5 py-3">
            <Select
              label="排序方式"
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setRankPage(1);
              }}
              className="w-40"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
            {rankAsync.isStale && <Spinner size="sm" />}
          </div>

          {/* 排行表格 */}
          {rankAsync.loading && rankData.data.length === 0 ? (
            <Spinner className="py-12" />
          ) : rankAsync.error && rankData.data.length === 0 ? (
            <ErrorState message={rankAsync.error ?? "加载失败"} onRetry={rankAsync.refetch} />
          ) : rankData.data.length === 0 ? (
            <EmptyState title="暂无排行数据" description="当前排序条件下没有符合条件的饰品。" />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface-hover text-left text-xs text-ink-muted">
                      <th className="px-3 py-3 font-medium">排名</th>
                      <th className="px-3 py-3 font-medium">图片</th>
                      <th className="px-3 py-3 font-medium">名称</th>
                      <th className="px-3 py-3 text-right font-medium">在售价</th>
                      <th className="px-3 py-3 text-right font-medium">求购价</th>
                      <th className="px-3 py-3 text-right font-medium">在售量</th>
                      <th className="px-3 py-3 text-right font-medium">1日涨跌</th>
                      <th className="px-3 py-3 text-right font-medium">7日涨跌</th>
                      <th className="px-3 py-3 text-right font-medium">30日涨跌</th>
                      <th className="px-3 py-3 text-center font-medium">走势</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {rankData.data.map((item, idx) => {
                      const rank = (rankPage - 1) * PAGE_SIZE + idx + 1;
                      return (
                        <tr
                          key={item.good_id}
                          onClick={() => handleRowClick(item.good_id)}
                          className="cursor-pointer transition-colors hover:bg-surface-hover"
                        >
                          <td className="px-3 py-3 font-medium text-ink-primary tabular-nums">
                            {rank}
                          </td>
                          <td className="px-3 py-3">
                            {item.img ? (
                              <img
                                src={item.img}
                                alt={item.name}
                                className="h-10 w-10 rounded border border-surface-border bg-surface-hover object-contain"
                                loading="lazy"
                              />
                            ) : (
                              <div className="flex h-10 w-10 items-center justify-center rounded border border-surface-border bg-surface-hover text-[10px] text-ink-muted">
                                无图
                              </div>
                            )}
                          </td>
                          <td className="max-w-[220px] truncate px-3 py-3 text-ink-primary">
                            {item.name}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums text-ink-secondary">
                            {formatPrice(item.sell_price)}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums text-ink-secondary">
                            {formatPrice(item.buy_price)}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums text-ink-secondary">
                            {fmtNum(item.sell_num, 0)}
                          </td>
                          <td
                            className={`px-3 py-3 text-right tabular-nums ${chgColorClass(item.chg_1)}`}
                          >
                            {formatSignedPercent(item.chg_1)}
                          </td>
                          <td
                            className={`px-3 py-3 text-right tabular-nums ${chgColorClass(item.chg_7)}`}
                          >
                            {formatSignedPercent(item.chg_7)}
                          </td>
                          <td
                            className={`px-3 py-3 text-right tabular-nums ${chgColorClass(item.chg_30)}`}
                          >
                            {formatSignedPercent(item.chg_30)}
                          </td>
                          <td className="px-3 py-3">
                            <Sparkline
                              points={item.recently_price ?? []}
                              color={chgSparkColor(item.chg_1)}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination
                total={rankData.total}
                page={rankPage}
                pageSize={PAGE_SIZE}
                onPageChange={setRankPage}
              />
            </>
          )}
        </Card>
      )}

      {/* ── Tab 2: 饰品列表 ── */}
      {activeTab === "items" && (
        <Card bodyClassName="p-0">
          {/* 筛选器 */}
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-surface-border px-5 py-3">
            <div className="flex flex-wrap items-end gap-3">
              <Select
                label="类型"
                value={filterType}
                onChange={(e) => {
                  setFilterType(e.target.value);
                  setItemPage(1);
                }}
                className="w-36"
              >
                {TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
              <Select
                label="品质"
                value={filterQuality}
                onChange={(e) => {
                  setFilterQuality(e.target.value);
                  setItemPage(1);
                }}
                className="w-36"
              >
                {QUALITY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
              {(filterType || filterQuality) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setFilterType("");
                    setFilterQuality("");
                    setItemPage(1);
                  }}
                >
                  重置
                </Button>
              )}
            </div>
            {itemAsync.isStale && <Spinner size="sm" />}
          </div>

          {/* 饰品表格 */}
          {itemAsync.loading && itemData.data.length === 0 ? (
            <Spinner className="py-12" />
          ) : itemAsync.error && itemData.data.length === 0 ? (
            <ErrorState message={itemAsync.error ?? "加载失败"} onRetry={itemAsync.refetch} />
          ) : itemData.data.length === 0 ? (
            <EmptyState
              title="暂无饰品"
              description="当前筛选条件下没有符合条件的饰品，请调整筛选条件后重试。"
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface-hover text-left text-xs text-ink-muted">
                      <th className="px-3 py-3 font-medium">图片</th>
                      <th className="px-3 py-3 font-medium">名称</th>
                      <th className="px-3 py-3 font-medium">品质</th>
                      <th className="px-3 py-3 font-medium">类型</th>
                      <th className="px-3 py-3 text-right font-medium">在售价</th>
                      <th className="px-3 py-3 text-right font-medium">求购价</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {itemData.data.map((item) => (
                      <tr
                        key={item.good_id}
                        onClick={() => handleRowClick(item.good_id)}
                        className="cursor-pointer transition-colors hover:bg-surface-hover"
                      >
                        <td className="px-3 py-3">
                          {item.img ? (
                            <img
                              src={item.img}
                              alt={item.name}
                              className="h-10 w-10 rounded border border-surface-border bg-surface-hover object-contain"
                              loading="lazy"
                            />
                          ) : (
                            <div className="flex h-10 w-10 items-center justify-center rounded border border-surface-border bg-surface-hover text-[10px] text-ink-muted">
                              无图
                            </div>
                          )}
                        </td>
                        <td className="max-w-[260px] truncate px-3 py-3 text-ink-primary">
                          {item.name}
                        </td>
                        <td className="px-3 py-3">
                          {item.quality ? (
                            <Badge variant={qualityVariant(item.quality)}>{item.quality}</Badge>
                          ) : (
                            <span className="text-xs text-ink-muted">--</span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-ink-secondary">{item.type || "--"}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-secondary">
                          {formatPrice(item.sell_price)}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-secondary">
                          {formatPrice(item.buy_price)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                total={itemData.total}
                page={itemPage}
                pageSize={PAGE_SIZE}
                onPageChange={setItemPage}
              />
            </>
          )}
        </Card>
      )}

      {/* ── Tab 3: 热门系列 ── */}
      {activeTab === "series" && (
        <div className="space-y-4">
          {seriesAsync.loading && seriesData.length === 0 ? (
            <Card>
              <Spinner className="py-12" />
            </Card>
          ) : seriesAsync.error && seriesData.length === 0 ? (
            <Card>
              <ErrorState message={seriesAsync.error ?? "加载失败"} onRetry={seriesAsync.refetch} />
            </Card>
          ) : seriesData.length === 0 ? (
            <Card>
              <EmptyState title="暂无系列数据" description="暂未获取到热门系列行情信息。" />
            </Card>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-xs text-ink-muted">
                  共 {formatNumber(seriesData.length, 0)} 个系列
                </p>
                {seriesAsync.isStale && <Spinner size="sm" />}
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {seriesData.map((s) => {
                  const sparkColor = chgSparkColor(s.chg_1);
                  return (
                    <Card
                      key={s.series_id}
                      title={s.name}
                      subtitle={`${formatNumber(s.item_count, 0)} 件饰品`}
                      actions={<Badge variant="info">系列</Badge>}
                    >
                      <div className="space-y-3">
                        {/* 地板总价 */}
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-ink-muted">地板总价</span>
                          <span className="text-sm font-semibold text-ink-primary">
                            {formatPrice(s.total_floor_value)}
                          </span>
                        </div>

                        {/* 1/7/30 日涨跌 */}
                        <div className="grid grid-cols-3 gap-2">
                          {[
                            { label: "1日", value: s.chg_1 },
                            { label: "7日", value: s.chg_7 },
                            { label: "30日", value: s.chg_30 },
                          ].map((c) => (
                            <div
                              key={c.label}
                              className="rounded-lg bg-surface-hover px-2 py-2 text-center"
                            >
                              <p className="text-[11px] text-ink-muted">{c.label}</p>
                              <p
                                className={`text-sm font-semibold tabular-nums ${chgColorClass(
                                  c.value,
                                )}`}
                              >
                                {formatSignedPercent(c.value)}
                              </p>
                            </div>
                          ))}
                        </div>

                        {/* 近期走势迷你图 */}
                        <div className="rounded-lg bg-surface-hover px-2 py-2">
                          <p className="mb-1 text-[11px] text-ink-muted">近期走势</p>
                          <Sparkline
                            points={s.recently_price}
                            color={sparkColor}
                            height={56}
                            width="100%"
                          />
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
