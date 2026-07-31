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

async function request<T>(
  path: string,
  params?: QueryParams,
  options?: RequestInit,
): Promise<T> {
  const url = buildUrl(path, params);
  const headers: Record<string, string> = {};
  if (options?.method === "POST") {
    headers["Content-Type"] = "application/json";
  }
  Object.assign(headers, options?.headers as Record<string, string> | undefined);
  const res = await fetch(url, {
    ...options,
    headers,
  });

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

// ── Scenario API ──────────────────────────────────────────
// All endpoints that accept a Chinese ``sub_index`` use POST with a JSON body
// to avoid URL-encoding issues in uvicorn's HTTP parser.

export const scenarioApi = {
  generate(subIndex: string, period: string, refresh = false): Promise<ScenarioResponse> {
    return request<ScenarioResponse>("/scenario/generate", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period, refresh }),
    });
  },

  ohlc(subIndex: string, period: string): Promise<OhlcResponse> {
    return request<OhlcResponse>("/scenario/ohlc", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
    });
  },

  history(
    subIndex: string,
    period: string,
    method = "knn",
    nNeighbors = 10,
  ): Promise<HistoryResponse> {
    return request<HistoryResponse>("/scenario/history", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period, method, n_neighbors: nNeighbors }),
    });
  },

  templates(subIndex: string, period: string, minConfidence = 0.5): Promise<TemplatesResponse> {
    return request<TemplatesResponse>("/scenario/templates", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period, min_confidence: minConfidence }),
    });
  },

  explain(scenario: Record<string, unknown>, context?: Record<string, unknown>): Promise<ExplainResponse> {
    return request<ExplainResponse>("/scenario/explain", undefined, {
      method: "POST",
      body: JSON.stringify({ scenario, context }),
    });
  },

  meta(): Promise<MetaResponse> {
    return request<MetaResponse>("/scenario/meta");
  },
};

// ── Backtest API ──────────────────────────────────────────

export const backtestApi = {
  equity(subIndex: string, period: string): Promise<BacktestEquityResponse> {
    return request<BacktestEquityResponse>("/backtest/equity", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
    });
  },

  mvp(subIndex: string, period: string): Promise<MvpBacktestResponse> {
    return request<MvpBacktestResponse>("/backtest/mvp", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
    });
  },
};

// ── Ensemble API ──────────────────────────────────────────

export const ensembleApi = {
  run(subIndex: string, period: string): Promise<EnsembleResponse> {
    return request<EnsembleResponse>("/ensemble/run", undefined, {
      method: "POST",
      body: JSON.stringify({ sub_index: subIndex, period }),
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
  list(): Promise<ReportsListResponse> {
    return request<ReportsListResponse>("/reports/list");
  },

  get(filename: string): Promise<ReportGetResponse> {
    return request<ReportGetResponse>("/reports/get", { filename });
  },
};

// ── Data API ──────────────────────────────────────────────

export const dataApi = {
  cacheStatus(): Promise<CacheStatusResponse> {
    return request<CacheStatusResponse>("/data/cache-status");
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
  metrics(): Promise<MonitoringResponse> {
    return request<MonitoringResponse>("/monitoring/metrics");
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
