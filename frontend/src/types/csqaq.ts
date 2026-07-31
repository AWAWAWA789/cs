/**
 * CSQAQ API 响应类型定义
 *
 * 为全部 24 个 CSQAQ API 端点定义 TypeScript 接口，
 * 覆盖饰品指数、饰品详情、涨跌排行、库存监控、实时成交、系统设置六大模块。
 */

// ════════════════════════════════════════════════════════════
// 2.1 饰品指数模块（3 个端点）
// ════════════════════════════════════════════════════════════

/** 子指数数据项。 */
export interface SubIndexItem {
  id: number;
  name: string;
  name_key: string;
  market_index: number;
  chg_num: number;
  chg_rate: number;
  open: number;
  close: number;
  high: number;
  low: number;
}

/** 涨跌分布数据项（按类型/价格区间）。 */
export interface ChgDistributionItem {
  name: string;
  chg_1: number;
  chg_7: number;
  chg_15: number;
  chg_30: number;
  chg_90: number;
  chg_180: number;
  [key: string]: string | number;
}

/** 在线人数数据。 */
export interface OnlineNumber {
  current: number;
  today_peak: number;
  month_peak: number;
  monthly_active: number;
  chg_rate: number;
}

/** 涨跌分布数量统计。 */
export interface RateData {
  up: number;
  down: number;
  flat: number;
  [key: string]: number;
}

/** current_data?type=init 响应。 */
export interface MarketOverviewResponse {
  sub_index_data: SubIndexItem[];
  chg_type_data: ChgDistributionItem[];
  chg_price_data: ChgDistributionItem[];
  rate_data: RateData;
  online_number: OnlineNumber;
}

/** current_data?type=hours|kline|lease 响应（泛型数据，根据 type 不同结构不同）。 */
export interface MarketDataResponse {
  type: "hours" | "kline" | "lease";
  data: unknown[];
}

/** sub/kline OHLCV 数据项。 */
export interface SubKlineBar {
  t: number; // 时间戳
  o: number; // 开盘
  c: number; // 收盘
  h: number; // 最高
  l: number; // 最低
  v: number; // 成交量
}

/** sub/kline 响应。 */
export interface SubKlineResponse {
  id: number;
  type: string;
  data: SubKlineBar[];
}

// ════════════════════════════════════════════════════════════
// 2.2 饰品详情模块（7 个端点）
// ════════════════════════════════════════════════════════════

/** 全量饰品 ID 映射项。 */
export interface GoodsIdItem {
  good_id: string;
  name: string;
  market_hash_name: string;
}

/** goods/get_all_goods_id 响应。 */
export interface AllGoodsIdResponse {
  data: GoodsIdItem[];
}

/** 搜索联想结果项。 */
export interface SearchSuggestItem {
  good_id: string;
  name: string;
}

/** search/suggest 响应。 */
export interface SearchSuggestResponse {
  data: SearchSuggestItem[];
}

/** 单平台数据（7 平台之一）。 */
export interface PlatformData {
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

/** 涨跌数据。 */
export interface PriceChangeData {
  chg_1: number | null;
  chg_7: number | null;
  chg_30: number | null;
  chg_180: number | null;
  chg_rate_1: number | null;
  chg_rate_7: number | null;
  chg_rate_30: number | null;
  chg_rate_180: number | null;
}

/** 挂刀比例数据。 */
export interface KnifeRatioData {
  steam_buy_knife_ratio: number | null;
  steam_sell_knife_ratio: number | null;
  buff_buy_cash_ratio: number | null;
  buff_sell_cash_ratio: number | null;
}

/** 基础信息。 */
export interface ItemBaseInfo {
  name: string;
  img: string;
  min_float: number;
  max_float: number;
  quality: string;
  category: string;
  big_category: string;
  supply: number;
  hot_rank: number;
  hot_rank_change: number;
}

/** Steam 成交数据。 */
export interface SteamTradeData {
  volume: number;
  avg_price: number;
}

/** info/good 响应（单品详情）。 */
export interface ItemDetailResponse {
  good_id: string;
  base_info: ItemBaseInfo;
  platforms: {
    buff: PlatformData;
    yyyp: PlatformData;
    steam: PlatformData;
    c5: PlatformData;
    igxe: PlatformData;
    eco: PlatformData;
    r8: PlatformData;
  };
  price_change: PriceChangeData;
  knife_ratio: KnifeRatioData;
  steam_trade: SteamTradeData;
}

/** 存世量走势数据点。 */
export interface SupplyDataPoint {
  date: string;
  supply: number;
}

/** info/good/statistic 响应。 */
export interface ItemSupplyResponse {
  good_id: string;
  data: SupplyDataPoint[];
}

/** 批量价格查询项。 */
export interface BatchPriceItem {
  market_hash_name: string;
  sell_price: number | null;
  buy_price: number | null;
  sell_num: number | null;
  buy_num: number | null;
}

/** getPriceByMarketHashName 响应。 */
export interface BatchPriceResponse {
  data: BatchPriceItem[];
}

/** 单品图表数据点。 */
export interface ChartDataPoint {
  timestamp: string;
  value: number;
}

/** info/chart 响应。 */
export interface ItemChartResponse {
  good_id: string;
  key: string;
  platform: number;
  period: number;
  style: string;
  data: ChartDataPoint[];
}

/** info/simple/chartAll 响应。 */
export interface ItemChartAllResponse {
  good_id: string;
  sell_price: ChartDataPoint[];
  sell_num: ChartDataPoint[];
}

// ════════════════════════════════════════════════════════════
// 2.3 涨跌/热门排行模块（4 个端点）
// ════════════════════════════════════════════════════════════

/** 排行榜单项。 */
export interface RankListItem {
  good_id: string;
  name: string;
  img: string;
  sell_price: number | null;
  buy_price: number | null;
  sell_num: number | null;
  buy_num: number | null;
  short_lease_price: number | null;
  long_lease_price: number | null;
  lease_annual: number | null;
  turnover_number: number | null;
  transfer_price: number | null;
  supply: number | null;
  total_market_value: number | null;
  chg_1: number | null;
  chg_7: number | null;
  chg_30: number | null;
  recently_price?: ChartDataPoint[];
  [key: string]: unknown;
}

/** get_rank_list 响应。 */
export interface RankListResponse {
  total: number;
  page_index: number;
  page_size: number;
  data: RankListItem[];
}

/** 饰品列表筛选项。 */
export interface ItemListFilter {
  type?: string;
  quality?: string;
  category?: string;
  wear?: string;
  search?: string;
}

/** 饰品列表单项。 */
export interface PageListItem {
  good_id: string;
  name: string;
  img: string;
  quality: string;
  category: string;
  type: string;
  sell_price: number | null;
  buy_price: number | null;
  [key: string]: unknown;
}

/** get_page_list 响应。 */
export interface PageListResponse {
  total: number;
  page_index: number;
  page_size: number;
  data: PageListItem[];
}

/** 热门系列列表项。 */
export interface SeriesListItem {
  series_id: string;
  name: string;
  chg_1: number;
  chg_7: number;
  chg_15: number;
  chg_30: number;
  chg_90: number;
  chg_180: number;
  item_count: number;
  total_floor_value: number;
  recently_price: ChartDataPoint[];
}

/** get_series_list 响应。 */
export interface SeriesListResponse {
  data: SeriesListItem[];
}

/** 系列详情中的饰品项。 */
export interface SeriesDetailItem {
  good_id: string;
  name: string;
  img: string;
  sell_price: number | null;
  buy_price: number | null;
  [key: string]: unknown;
}

/** get_series_detail 响应。 */
export interface SeriesDetailResponse {
  series_id: string;
  name: string;
  data: SeriesDetailItem[];
}

// ════════════════════════════════════════════════════════════
// 2.4 库存监控模块（7 个端点）
// ════════════════════════════════════════════════════════════

/** 库存监控任务项。 */
export interface MonitorTaskItem {
  task_id: string;
  steam_id: string;
  steam_name: string;
  avatar: string;
  inventory_count: number;
  inventory_value: number;
  hot_rank: number;
  create_time: string;
  last_change_time: string;
  [key: string]: unknown;
}

/** get_task_list 响应。 */
export interface MonitorTaskListResponse {
  total: number;
  page_index: number;
  page_size: number;
  data: MonitorTaskItem[];
}

/** 库存变动类型。 */
export type TrendType = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

/** 库存变动动态项。 */
export interface MonitorTrendItem {
  trend_id: string;
  task_id: string;
  steam_name: string;
  good_id: string;
  good_name: string;
  good_img: string;
  type: TrendType;
  count: number;
  price: number;
  time: string;
  [key: string]: unknown;
}

/** get_task_trends 响应。 */
export interface MonitorTrendsResponse {
  data: MonitorTrendItem[];
}

/** 饰品持有量排行项。 */
export interface GoodRankItem {
  task_id: string;
  steam_id: string;
  steam_name: string;
  avatar: string;
  hold_count: number;
  hold_value: number;
  [key: string]: unknown;
}

/** get_good_rank 响应。 */
export interface GoodRankResponse {
  data: GoodRankItem[];
}

/** 单个用户信息。 */
export interface MonitorUserInfo {
  task_id: string;
  steam_id: string;
  steam_name: string;
  avatar: string;
  inventory_count: number;
  inventory_value: number;
  hot_rank: number;
  create_time: string;
  last_change_time: string;
  [key: string]: unknown;
}

/** get_task_info 响应。 */
export interface MonitorUserInfoResponse {
  data: MonitorUserInfo;
}

/** 单个用户库存变动项。 */
export interface UserTrendItem extends MonitorTrendItem {}

/** get_task_trends_detail 响应。 */
export interface UserTrendsResponse {
  data: UserTrendItem[];
}

/** 库存物品项。 */
export interface InventoryItem {
  good_id: string;
  name: string;
  img: string;
  count: number;
  price: number;
  total_value: number;
  wear: string;
  [key: string]: unknown;
}

/** get_task_all 响应。 */
export interface UserInventoryResponse {
  task_id: string;
  snapshot_id: string | null;
  inventory_count: number;
  inventory_value: number;
  data: InventoryItem[];
}

/** 库存快照项。 */
export interface SnapshotItem {
  snapshot_id: string;
  date: string;
  inventory_count: number;
  inventory_value: number;
  [key: string]: unknown;
}

/** get_snapshot_list 响应。 */
export interface SnapshotListResponse {
  data: SnapshotItem[];
}

// ════════════════════════════════════════════════════════════
// 2.5 实时成交数据模块（2 个端点，暂停更新）
// ════════════════════════════════════════════════════════════

/** 平台实时成交量数据项。 */
export interface VolumeCurrentItem {
  platform: string;
  volume: number;
  [key: string]: unknown;
}

/** vol/current 响应。 */
export interface VolumeCurrentResponse {
  data: VolumeCurrentItem[];
  /** 数据暂停更新标记。 */
  paused: boolean;
}

/** 单品实时成交量历史数据点。 */
export interface VolumeDetailPoint {
  timestamp: string;
  volume: number;
  avg_price: number;
  [key: string]: unknown;
}

/** vol/detail 响应。 */
export interface VolumeDetailResponse {
  vol_id: string;
  data: VolumeDetailPoint[];
  /** 数据暂停更新标记。 */
  paused: boolean;
}

// ════════════════════════════════════════════════════════════
// 2.6 系统设置模块（1 个端点）
// ════════════════════════════════════════════════════════════

/** bind_local_ip 响应。 */
export interface BindIpResponse {
  success: boolean;
  message: string;
  ip: string;
  bind_time: string;
}
