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
}

export interface OhlcResponse {
  sub_index: string;
  period: string;
  count: number;
  ohlc: OhlcBar[];
}

export interface SimilarityMatch {
  date: string;
  similarity: number;
  future_return: number;
  label?: string;
}

export interface HistoryResponse {
  sub_index: string;
  period: string;
  method: string;
  matches: SimilarityMatch[];
}

export interface TemplateMatch {
  name: string;
  confidence: number;
  direction: string;
  description?: string;
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
