/** Unified API client for all backend endpoints. */

import type {
  ScenarioResponse,
  OhlcResponse,
  HistoryResponse,
  TemplatesResponse,
  ExplainResponse,
  MetaResponse,
  BacktestEquityResponse,
  MvpBacktestResponse,
  EnsembleResponse,
  TaskInfo,
  ScanResult,
  ReportsListResponse,
  ReportGetResponse,
  CacheStatusResponse,
  DataRefreshResponse,
  MonitoringResponse,
  TaskIdResponse,
  ApiError,
  AccumulationAnalysis,
  AccumulationScanResponse,
  AccumulationInitResponse,
  AccumulationStatusResponse,
  ItemInventoryResponse,
  FusedAccumulationResponse,
  TeamAnalysisResponse,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

/** Custom error with status code and detail message. */
export class ApiClientError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiClientError";
  }
}

type QueryParams = Record<string, string | number | boolean | undefined>;

/** 扩展 RequestInit，确保 signal 可传入。 */
type RequestOptions = RequestInit & { signal?: AbortSignal };

/**
 * Build a full URL string using the URL class, which handles
 * percent-encoding of non-ASCII characters correctly.
 */
function buildUrl(path: string, params?: QueryParams): string {
  const origin = BASE_URL || window.location.origin;
  const url = new URL(path, origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    }
  }
  // If BASE_URL is empty, return a relative URL (same-origin)
  if (!BASE_URL) {
    return url.pathname + url.search;
  }
  return url.toString();
}

/**
 * 底层请求函数，支持 AbortSignal 取消请求。
 * 遇到 429 (Too Many Requests) 时自动重试，最多重试 2 次。
 * @param signal 可选的 AbortSignal，用于取消请求
 */
async function request<T>(
  path: string,
  params?: QueryParams,
  options?: RequestOptions,
): Promise<T> {
  const url = buildUrl(path, params);
  const headers: Record<string, string> = {};
  if (options?.method === "POST") {
    headers["Content-Type"] = "application/json";
  }
  Object.assign(headers, options?.headers as Record<string, string> | undefined);

  const MAX_RETRIES = 2;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    // 如果 signal 已取消，直接抛出
    if (options?.signal?.aborted) {
      throw new ApiClientError(0, "请求已取消");
    }

    const res = await fetch(url, {
      ...options,
      headers,
      signal: options?.signal,
    });

    // 429 重试逻辑
    if (res.status === 429 && attempt < MAX_RETRIES) {
      const delay = 5000 * (attempt + 1); // 5s, 10s — match backend backoff
      await new Promise((resolve) => setTimeout(resolve, delay));
      continue;
    }

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = (await res.json()) as ApiError;
        detail = body.detail ?? detail;
      } catch {
        // ignore parse error
      }
      throw new ApiClientError(res.status, detail);
    }

    // Handle 204 No Content
    if (res.status === 204) {
      return undefined as T;
    }

    return (await res.json()) as T;
  }

  // 所有重试用尽
  throw new ApiClientError(429, "请求过于频繁，请稍后重试");
}

// ── Scenario API ──────────────────────────────────────────
// All endpoints that accept a Chinese ``sub_index`` use POST with a JSON body
// to avoid URL-encoding issues in uvicorn's HTTP parser.

export const scenarioApi = {
  generate(subIndex: string, period: string, refresh = false, signal?: AbortSignal): Promise<ScenarioResponse> {
    return request<ScenarioResponse>("/scenario/generate", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period, refresh }),
      signal,
    });
  },

  ohlc(subIndex: string, period: string, signal?: AbortSignal): Promise<OhlcResponse> {
    return request<OhlcResponse>("/scenario/ohlc", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
      signal,
    });
  },

  history(
    subIndex: string,
    period: string,
    method = "knn",
    nNeighbors = 10,
    signal?: AbortSignal,
  ): Promise<HistoryResponse> {
    return request<HistoryResponse>("/scenario/history", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period, method, n_neighbors: nNeighbors }),
      signal,
    });
  },

  templates(subIndex: string, period: string, minConfidence = 0.5, signal?: AbortSignal): Promise<TemplatesResponse> {
    return request<TemplatesResponse>("/scenario/templates", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period, min_confidence: minConfidence }),
      signal,
    });
  },

  explain(scenario: Record<string, unknown>, context?: Record<string, unknown>, signal?: AbortSignal): Promise<ExplainResponse> {
    return request<ExplainResponse>("/scenario/explain", undefined, {
      method: "POST",
      body: JSON.stringify({ scenario, context }),
      signal,
    });
  },

  meta(signal?: AbortSignal): Promise<MetaResponse> {
    return request<MetaResponse>("/scenario/meta", undefined, { signal });
  },
};

// ── Backtest API ──────────────────────────────────────────

export const backtestApi = {
  equity(subIndex: string, period: string, signal?: AbortSignal): Promise<BacktestEquityResponse> {
    return request<BacktestEquityResponse>("/backtest/equity", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
      signal,
    });
  },

  mvp(subIndex: string, period: string, signal?: AbortSignal): Promise<MvpBacktestResponse> {
    return request<MvpBacktestResponse>("/backtest/mvp", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
      signal,
    });
  },
};

// ── Ensemble API ──────────────────────────────────────────

export const ensembleApi = {
  run(subIndex: string, period: string, signal?: AbortSignal): Promise<EnsembleResponse> {
    return request<EnsembleResponse>("/ensemble/run", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
      signal,
    });
  },
};

// ── Trend Scan API ────────────────────────────────────────

export const trendScanApi = {
  start(subIndex: string, period: string): Promise<TaskIdResponse> {
    return request<TaskIdResponse>("/trend-scan/start", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
    });
  },

  status(taskId: string): Promise<TaskInfo> {
    return request<TaskInfo>(`/trend-scan/status/${encodeURIComponent(taskId)}`);
  },
};

// ── Reports API ───────────────────────────────────────────

export const reportsApi = {
  list(signal?: AbortSignal): Promise<ReportsListResponse> {
    return request<ReportsListResponse>("/reports/list", undefined, { signal });
  },

  get(filename: string, signal?: AbortSignal): Promise<ReportGetResponse> {
    return request<ReportGetResponse>("/reports/get", { filename }, { signal });
  },
};

// ── Data API ──────────────────────────────────────────────

export const dataApi = {
  cacheStatus(signal?: AbortSignal): Promise<CacheStatusResponse> {
    return request<CacheStatusResponse>("/data/cache-status", undefined, { signal });
  },

  refresh(subIndex: string, period: string): Promise<DataRefreshResponse> {
    return request<DataRefreshResponse>("/data/refresh", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
    });
  },
};

// ── Monitoring API ────────────────────────────────────────

export const monitoringApi = {
  metrics(signal?: AbortSignal): Promise<MonitoringResponse> {
    return request<MonitoringResponse>("/monitoring/metrics", undefined, { signal });
  },
};

// ── Item (饰品) API ───────────────────────────────────────
// 封装 CSQAQ 饰品详情模块的 7 个端点

/** 饰品搜索请求体。 */
interface ItemSearchRequest {
  text: string;
}

/** 单品图表请求体。 */
interface ItemChartRequest {
  good_id: string;
  key: string;
  platform: number;
  period: number;
  style: string;
}

/** 批量价格请求体。 */
interface BatchPriceRequest {
  market_hash_names: string[];
}

export const itemApi = {
  /** 饰品名称联想搜索。 */
  search(text: string, signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/item/search", undefined, {
      method: "POST",
      body: JSON.stringify({ text } satisfies ItemSearchRequest),
      signal,
    });
  },

  /** 全量饰品 ID 映射表。 */
  all(signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/item/all", undefined, { signal });
  },

  /** 单件饰品详情（7 平台 50+ 字段）。 */
  detail(goodId: string, signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/item/detail", { good_id: goodId }, { signal });
  },

  /** 单品多平台多周期图表数据。 */
  chart(req: ItemChartRequest, signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/item/chart", undefined, {
      method: "POST",
      body: JSON.stringify(req),
      signal,
    });
  },

  /** 全量图表（仅售价+在售量）。 */
  chartAll(goodId: string, signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/item/chart-all", undefined, {
      method: "POST",
      body: JSON.stringify({ good_id: goodId }),
      signal,
    });
  },

  /** 存世量走势（近 180 天）。 */
  supply(goodId: string, signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/item/supply", { good_id: goodId }, { signal });
  },

  /** 批量价格查询（≤50 个）。 */
  batchPrice(marketHashNames: string[], signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/item/batch-price", undefined, {
      method: "POST",
      body: JSON.stringify({ market_hash_names: marketHashNames } satisfies BatchPriceRequest),
      signal,
    });
  },
};

// ── Rank (排行榜) API ─────────────────────────────────────
// 封装 CSQAQ 涨跌排行与饰品列表模块

/** 涨跌排行请求体。 */
interface RankListRequest {
  sort: string;
  page_index: number;
  page_size: number;
}

/** 饰品列表筛选请求体。 */
interface ItemsListRequest {
  type?: string | null;
  quality?: string | null;
  category?: string | null;
  wear?: string | null;
  search?: string | null;
  page_index: number;
  page_size: number;
}

/** 饰品列表筛选条件。 */
export interface ItemListFilters {
  type?: string;
  quality?: string;
  category?: string;
  wear?: string;
  search?: string;
}

export const rankApi = {
  /** 涨跌排行榜。 */
  list(sort: string, pageIndex: number, pageSize: number, signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/rank/list", undefined, {
      method: "POST",
      body: JSON.stringify({ sort, page_index: pageIndex, page_size: pageSize } satisfies RankListRequest),
      signal,
    });
  },

  /** 饰品列表（带筛选与分页）。 */
  items(filters: ItemListFilters, pageIndex: number, pageSize: number, signal?: AbortSignal): Promise<unknown> {
    const body: ItemsListRequest = {
      type: filters.type || null,
      quality: filters.quality || null,
      category: filters.category || null,
      wear: filters.wear || null,
      search: filters.search || null,
      page_index: pageIndex,
      page_size: pageSize,
    };
    return request<unknown>("/rank/items", undefined, {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
  },

  /** 热门系列列表。 */
  series(signal?: AbortSignal): Promise<unknown> {
    return request<unknown>("/rank/series", undefined, { signal });
  },

  /** 系列详情。 */
  seriesDetail(seriesId: string, signal?: AbortSignal): Promise<unknown> {
    return request<unknown>(`/rank/series/${encodeURIComponent(seriesId)}`, undefined, { signal });
  },
};

// ── Accumulation (吸货分析) API ───────────────────────────

export const accumulationApi = {
  /** 对指定标的执行吸货分析（指数模式）。 */
  analyze(subIndex: string, period: string, signal?: AbortSignal): Promise<AccumulationAnalysis> {
    return request<AccumulationAnalysis>("/accumulation/analyze", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
      signal,
    });
  },

  /** 对指定单品执行吸货分析（单品模式，优先于指数）。 */
  analyzeItem(
    goodId: string,
    period: string,
    platform = 1,
    key = "sell_price",
    signal?: AbortSignal,
  ): Promise<AccumulationAnalysis> {
    return request<AccumulationAnalysis>("/accumulation/analyze", undefined, {
      method: "POST",
      body: JSON.stringify({ good_id: goodId, period, platform, key }),
      signal,
    });
  },

  /** 扫描多个标的的吸货评分排行。 */
  scan(subIndices: string[], period: string, topN = 10, signal?: AbortSignal): Promise<AccumulationScanResponse> {
    return request<AccumulationScanResponse>("/accumulation/scan", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_indices: subIndices, period, top_n: topN }),
      signal,
    });
  },

  /** 一次性数据预热初始化。 */
  init(subIndices?: string[], periods?: string[], signal?: AbortSignal): Promise<AccumulationInitResponse> {
    return request<AccumulationInitResponse>("/accumulation/init", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_indices: subIndices, periods }),
      signal,
    });
  },

  /** 查看初始化状态。 */
  status(signal?: AbortSignal): Promise<AccumulationStatusResponse> {
    return request<AccumulationStatusResponse>("/accumulation/status", undefined, { signal });
  },

  /** 拉取单品库存监控聚合数据（主力持有量 + 近期买卖变动，先看数据不加算法）。 */
  itemInventory(goodId: string, topN = 20, signal?: AbortSignal): Promise<ItemInventoryResponse> {
    return request<ItemInventoryResponse>(
      "/accumulation/item-inventory",
      { good_id: goodId, top_n: topN },
      { signal },
    );
  },

  /** 跨品主力团队识别（并发拉取 top-N 主力持仓，构建关联矩阵）。 */
  teamAnalysis(
    goodId: string,
    holderTopN = 10,
    minOverlap = 2,
    signal?: AbortSignal,
  ): Promise<TeamAnalysisResponse> {
    return request<TeamAnalysisResponse>(
      "/accumulation/team-analysis",
      { good_id: goodId, holder_top_n: holderTopN, min_overlap: minOverlap },
      { signal },
    );
  },

  /** 双轨融合吸货分析（K线行为 + 库存行为）。 */
  analyzeFused(
    goodId: string,
    period = "1day",
    platform = 1,
    key = "sell_price",
    includeTeam = true,
    signal?: AbortSignal,
  ): Promise<FusedAccumulationResponse> {
    return request<FusedAccumulationResponse>(
      "/accumulation/analyze-fused",
      { good_id: goodId, period, platform, key, include_team: includeTeam },
      { signal },
    );
  },
};

// ── Aggregate export ──────────────────────────────────────

export const api = {
  scenario: scenarioApi,
  backtest: backtestApi,
  ensemble: ensembleApi,
  trendScan: trendScanApi,
  reports: reportsApi,
  data: dataApi,
  monitoring: monitoringApi,
  item: itemApi,
  rank: rankApi,
  accumulation: accumulationApi,
};

/** Type guard for ApiClientError. */
export function isApiError(err: unknown): err is ApiClientError {
  return err instanceof ApiClientError;
}

/** Poll a trend scan task until completion. Returns the final ScanResult. */
export async function pollScanTask(
  taskId: string,
  onProgress?: (info: TaskInfo) => void,
  intervalMs = 2000,
  timeoutMs = 300_000,
): Promise<ScanResult> {
  const start = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (Date.now() - start > timeoutMs) {
      throw new Error(`扫描超时 (${timeoutMs / 1000}s)`);
    }
    const info = await trendScanApi.status(taskId);
    onProgress?.(info);

    if (info.status === "completed") {
      return info.result as ScanResult;
    }
    if (info.status === "failed") {
      throw new Error(info.error ?? "扫描失败");
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
