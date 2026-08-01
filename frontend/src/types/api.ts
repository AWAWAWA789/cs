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
