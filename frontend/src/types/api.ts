/** TypeScript interfaces for all API responses. */

// ── Scenario ──────────────────────────────────────────────

export interface WavePoint {
  label: string;
  price: number;
}

export interface Scenario {
  name: string;
  direction_label: "bullish" | "bearish" | "neutral";
  probability: number;
  support: number | null;
  resistance: number | null;
  target: number | null;
  stop_loss: number | null;
  position_size: number;
  wave_sketch: WavePoint[];
  description?: string;
}

export interface ScenarioResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  generation_time_ms: number;
  scenarios: Scenario[];
  per_period?: Record<string, unknown>;
  cached?: boolean;
}

export interface OhlcBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  /** 成交量（可选，部分数据源不提供）。 */
  volume?: number;
}

export interface OhlcResponse {
  sub_index: string;
  period: string;
  count: number;
  ohlc: OhlcBar[];
}

export interface SimilarityMatch {
  query_index: number;
  neighbor_index: number;
  distance: number;
  state: Record<string, number>;
  query_timestamp?: string;
  neighbor_timestamp?: string;
  future_return_5: number | null;
  future_return_7: number | null;
}

export interface HistoryResponse {
  sub_index: string;
  period: string;
  method: string;
  matches: SimilarityMatch[];
}

export interface TemplateMatch {
  template_name: string;
  matched_index: number;
  matched_timestamp: string | null;
  direction: string;
  confidence: number;
  support: number | null;
  resistance: number | null;
  target: number | null;
  stop_loss: number | null;
  suggestion: string;
  probability_prior: number;
}

export interface TemplatesResponse {
  sub_index: string;
  period: string;
  min_confidence: number;
  matches: TemplateMatch[];
}

export interface ExplainResponse {
  prompt: string;
  explanation: string;
  wave_sketch_description: string;
}

export interface MetaResponse {
  available_sub_indices: string[];
  supported_periods: string[];
  default_period: string;
}

// ── Backtest ──────────────────────────────────────────────

export interface EquityPoint {
  timestamp: string;
  equity: number;
}

export interface TradeRecord {
  entry_index: number;
  entry_time: string | null;
  entry_price: number;
  exit_time: string | null;
  exit_price: number | null;
  exit_reason: string;
  pnl: number;
  return_pct: number;
}

export interface BacktestMetrics {
  initial_capital: number;
  final_equity: number;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  avg_trade_return: number;
}

export interface BacktestEquityResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
  total_return: number;
  final_equity: number;
  trade_count: number;
}

export interface MvpBacktestResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
}

// ── Ensemble ──────────────────────────────────────────────

export interface StrategyResult {
  strategy_name: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  trade_count: number;
}

export interface EnsembleResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  ensemble: StrategyResult;
  pullback: StrategyResult;
  trend_following: StrategyResult;
}

// ── Trend Scan ────────────────────────────────────────────

export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface TaskInfo {
  task_id: string;
  status: TaskStatus;
  progress: number;
  message: string;
  result: unknown | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanResultItem {
  params: Record<string, unknown>;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  total_trades: number;
}

export interface ScanResult {
  sub_index: string;
  period: string;
  total_combinations: number;
  top_10: ScanResultItem[];
  bottom_10: ScanResultItem[];
  non_negative_count: number;
  all_results: ScanResultItem[];
}

// ── Reports ───────────────────────────────────────────────

export interface ReportFile {
  filename: string;
  size_bytes: number;
  modified_at: string;
}

export interface ReportsListResponse {
  reports: ReportFile[];
}

export interface ReportGetResponse {
  filename: string;
  content: Record<string, unknown>;
}

// ── Data ──────────────────────────────────────────────────

export interface CacheFile {
  filename: string;
  size_bytes: number;
  bar_count: number | null;
  modified_at: string;
}

export interface CacheStatusResponse {
  cache_dir: string;
  total_files: number;
  total_size_bytes: number;
  files: CacheFile[];
}

export interface DataRefreshResponse {
  sub_index: string;
  period: string;
  success: boolean;
  bar_count: number;
  message: string;
}

// ── Monitoring ────────────────────────────────────────────

export interface MonitoringMetrics {
  window_seconds: number;
  request_count: number;
  failure_count: number;
  failure_rate: number;
  latency_p50_ms: number;
  latency_p99_ms: number;
  brier_baseline: number | null;
  per_endpoint?: Record<string, {
    request_count: number;
    failure_rate: number;
    latency_p99_ms: number;
  }>;
}

export interface Alert {
  metric: string;
  value: number;
  threshold: number;
  severity: string;
  [key: string]: unknown;
}

export interface MonitoringResponse {
  metrics: MonitoringMetrics;
  alerts: Alert[];
  thresholds: Record<string, number>;
}

// ── Generic ───────────────────────────────────────────────

export interface ApiError {
  detail: string;
}

export interface TaskIdResponse {
  task_id: string;
}

// ── Accumulation (吸货分析) ──────────────────────────────

export interface AccumulationSignals {
  price_position: number;
  volume_price_divergence: number;
  consolidation: number;
  bottom_rising: number;
  volatility_contracting: number;
  volume_trend: number;
}

export interface AccumulationFeatures {
  price_position: number;
  distance_to_low: number;
  atr_percent: number;
  volatility_regime: number;
  volume_ratio: number;
  volume_trend: number;
  volume_price_divergence: number;
  bottom_rising: number;
  consolidation_score: number;
  consolidation_bars: number;
}

export interface AccumulationAnalysis {
  sub_index: string;
  period: string;
  accumulation_score: number;
  phase: "accumulation" | "distribution" | "neutral";
  signals: AccumulationSignals;
  total_rule_score: number;
  features: AccumulationFeatures;
  duration_bars: number;
  data_source: string;
  description: string;
  cached?: boolean;
}

export interface AccumulationScanItem {
  sub_index: string;
  accumulation_score: number;
  phase: "accumulation" | "distribution" | "neutral";
  duration_bars: number;
  data_source: string;
}

export interface AccumulationScanResponse {
  period: string;
  total_scanned: number;
  top_results: AccumulationScanItem[];
  latency_ms: number;
}

export interface AccumulationInitResponse {
  initialized: boolean;
  items_cached: number;
  errors: string[];
  latency_ms: number;
  message: string;
}

export interface AccumulationStatusResponse {
  initialized: boolean;
  last_run: string | null;
  items_cached: number;
  errors: string[];
}

// ── 单品库存监控（吸货页面用，先看数据） ────────────────

/** 持有该饰品的主力用户项（来自 /monitor/get_good_rank）。 */
export interface ItemHolder {
  task_id: string;
  steam_id: string;
  steam_name: string;
  avatar: string;
  hold_count: number;
  hold_value: number;
  [key: string]: unknown;
}

/** 该饰品近期库存变动项（来自 /monitor/get_task_trends）。 */
export interface ItemTrend {
  trend_id: string;
  task_id: string;
  steam_name: string;
  good_id: string;
  good_name: string;
  good_img: string;
  /** 变动类型（0-7，标识买入/卖出等行为）。 */
  type: number;
  count: number;
  price: number;
  time: string;
  [key: string]: unknown;
}

/** 单品库存聚合响应（GET /accumulation/item-inventory）。 */
export interface ItemInventoryResponse {
  good_id: string;
  holders: ItemHolder[];
  trends: ItemTrend[];
  data_source: string;
  holder_count: number;
  trend_count: number;
  description?: string;
}

// ── 跨品主力团队识别（吸货页面用） ──────────────────────

/** 关联品：被多个种子主力共同持有的其他饰品。 */
export interface TeamRelatedItem {
  good_id: string;
  good_name: string;
  good_img: string;
  /** 持有该关联品的种子主力数。 */
  overlap_count: number;
  /** 重合度 = overlap_count / 种子主力总数。 */
  overlap_ratio: number;
  /** 这些主力持有该关联品的合计持仓量。 */
  total_hold_in_team: number;
  /** 这些主力持有该关联品的合计持仓价值。 */
  total_value_in_team: number;
  /** 共同持有该关联品的主力 steam_id 列表。 */
  shared_steam_ids: string[];
  /** 共同持有该关联品的主力名称列表。 */
  shared_steam_names: string[];
}

/** 团队识别汇总指标。 */
export interface TeamSummary {
  /** 核心团队规模（跨品数 ≥ 阈值的主力数）。 */
  core_team_size: number;
  /** 核心团队在种子品的合计持仓量。 */
  core_team_hold_in_seed: number;
  /** 核心团队在种子品的持仓占比。 */
  core_team_ratio_in_seed: number;
  /** 关联品最高重合度。 */
  max_overlap_ratio: number;
  /** 关联品最高重合数。 */
  max_overlap_count: number;
  /** 主力平均跨品数。 */
  avg_cross_items_per_holder: number;
  /** 关联品总数。 */
  related_item_count: number;
  /** 是否疑似团队操作。 */
  is_likely_team_operated: boolean;
  /** 判定置信度（0-1）。 */
  confidence: number;
  /** 判定理由（中文）。 */
  reason: string;
}

/** 主力跨品分布项。 */
export interface TeamHolderCross {
  steam_id: string;
  steam_name: string;
  avatar: string;
  /** 该主力在种子品的持仓量。 */
  hold_in_seed: number;
  /** 该主力跨品数。 */
  cross_item_count: number;
  /** 该主力持有的其他品 good_id 列表。 */
  cross_good_ids: string[];
  /** 是否为核心团队成员（跨品数 ≥ 阈值）。 */
  is_core: boolean;
}

/** 跨品团队识别响应（GET /accumulation/team-analysis）。 */
export interface TeamAnalysisResponse {
  seed_good_id: string;
  seed_holder_count: number;
  analyzed_holder_count: number;
  related_items: TeamRelatedItem[];
  team_summary: TeamSummary;
  holders_cross: TeamHolderCross[];
  data_source?: string;
}
