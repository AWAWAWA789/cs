# 全功能 Web 可视化平台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有 CLI 功能（MVP 回测、集成策略、趋势扫描、报告生成、数据管理）集成到统一的 React 网页平台，实现浅色现代仪表盘风格的全中文可视化交互。面向本地个人使用，无需 Docker 或生产部署。

**Architecture:** 前端使用 React 18 + Vite + TypeScript 构建单页应用（SPA），构建产物为静态文件，由现有 FastAPI 的 `StaticFiles` 挂载。后端新增 REST API 端点暴露所有 CLI 功能，长耗时操作（趋势扫描、参数扫描）采用异步任务队列模式（内存任务表 + 轮询）。前端按功能模块拆分为独立页面组件，通过 React Router 切换。图表使用 ECharts，UI 组件采用自定义组件。本地运行：`npm run build` 构建前端 → `python run_scenario_server.py` 启动服务。

**Tech Stack:** React 18, Vite 5, TypeScript 5, React Router 6, ECharts 5, Tailwind CSS 3, FastAPI, Python 3.10+

---

## 文件结构总览

### 前端（新建 `frontend/` 目录，完全替换现有前端）

```
frontend/
├── package.json                  # 依赖声明
├── vite.config.ts                # Vite 配置，构建产物输出到 dist/
├── tsconfig.json                 # TypeScript 配置
├── tailwind.config.js            # Tailwind 主题配置（浅色仪表盘主题）
├── postcss.config.js             # PostCSS 配置
├── index.html                    # SPA 入口 HTML
├── src/
│   ├── main.tsx                  # React 应用入口
│   ├── App.tsx                   # 根组件 + 路由
│   ├── types/
│   │   └── api.ts                # 所有 API 响应的 TypeScript 类型定义
│   ├── lib/
│   │   ├── api.ts                # 统一 API 客户端（fetch 封装）
│   │   └── format.ts             # 格式化工具函数（百分比、日期、数字）
│   ├── components/
│   │   ├── Layout.tsx            # 页面布局骨架（侧边栏 + 顶栏 + 内容区）
│   │   ├── Sidebar.tsx           # 左侧导航栏
│   │   ├── TopBar.tsx            # 顶部全局控制栏（子指数/周期选择、状态）
│   │   ├── Card.tsx              # 通用卡片容器组件
│   │   ├── MetricCard.tsx        # 指标展示卡片（单个数值 + 标签）
│   │   ├── LoadingState.tsx      # 骨架屏/加载态组件
│   │   ├── ErrorState.tsx        # 错误态组件（含重试按钮）
│   │   └── ScenarioBar.tsx       # 情景概率条形图组件
│   ├── pages/
│   │   ├── ScenarioPage.tsx      # 情景分析页（升级现有功能）
│   │   ├── BacktestPage.tsx      # MVP 回测页
│   │   ├── EnsemblePage.tsx      # 集成策略页
│   │   ├── TrendScanPage.tsx     # 趋势扫描页（异步任务）
│   │   ├── ReportsPage.tsx       # 报告查看页
│   │   └── DataManagementPage.tsx # 数据管理页
│   └── styles/
│       └── globals.css           # Tailwind 指令 + 全局样式
└── dist/                         # 构建产物（gitignore），由 FastAPI 挂载
```

### 后端（修改/新增 `src/api/` 下的文件）

```
src/api/
├── scenario_endpoints.py         # 已有，保持不变
├── backtest_endpoints.py         # 已有，保持不变
├── monitoring.py                 # 已有，保持不变
├── backtest_endpoints.py         # 修改：新增 /backtest/mvp 端点
├── ensemble_endpoints.py         # 新建：集成策略端点
├── trend_scan_endpoints.py       # 新建：趋势扫描端点（异步任务）
├── report_endpoints.py           # 新建：报告查看端点
├── data_endpoints.py             # 新建：数据管理端点
└── task_queue.py                 # 新建：轻量异步任务队列
```

### 测试（新建对应测试文件）

```
tests/
├── test_ensemble_endpoints.py
├── test_trend_scan_endpoints.py
├── test_report_endpoints.py
├── test_data_endpoints.py
└── test_task_queue.py
```

---

## Task 1: 前端项目初始化与构建集成

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles/globals.css`
- Modify: `run_scenario_server.py`
- Modify: `.gitignore`

- [ ] **Step 1: 创建 `frontend/package.json`**

```json
{
  "name": "csqaq-dashboard",
  "private": true,
  "version": "0.19.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.2"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: 创建 `frontend/vite.config.ts`**

配置 Vite 构建产物输出到 `dist/`，开发时代理 API 请求到 `localhost:8000`。

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      "/scenario": "http://localhost:8000",
      "/backtest": "http://localhost:8000",
      "/ensemble": "http://localhost:8000",
      "/trend-scan": "http://localhost:8000",
      "/reports": "http://localhost:8000",
      "/data": "http://localhost:8000",
      "/monitoring": "http://localhost:8000",
    },
  },
});
```

- [ ] **Step 3: 创建 `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: 创建 `frontend/tailwind.config.js`**

配置浅色仪表盘主题色板：主色 `#3b82f6`（蓝）、背景 `#f8fafc`（近白灰）、卡片 `#ffffff`、文字 `#1e293b`（深灰）、次级文字 `#64748b`。涨绿 `#16a34a`、跌红 `#dc2626`。

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
        surface: {
          base: "#f8fafc",
          card: "#ffffff",
          border: "#e2e8f0",
          hover: "#f1f5f9",
        },
        ink: {
          primary: "#1e293b",
          secondary: "#64748b",
          muted: "#94a3b8",
        },
        bull: "#16a34a",
        bear: "#dc2626",
        neutral: "#f59e0b",
      },
      fontFamily: {
        sans: ['"Inter"', '"Noto Sans SC"', '"PingFang SC"', "sans-serif"],
        mono: ['"JetBrains Mono"', '"Cascadia Code"', "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)",
        "card-hover": "0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)",
      },
      borderRadius: {
        xl: "0.875rem",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 5: 创建 `frontend/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: 创建 `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CSQAQ 量化策略平台</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7: 创建 `frontend/src/styles/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  background-color: #f8fafc;
  color: #1e293b;
  font-family: "Inter", "Noto Sans SC", "PingFang SC", sans-serif;
  -webkit-font-smoothing: antialiased;
}

#root {
  min-height: 100vh;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
```

- [ ] **Step 8: 创建 `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
```

- [ ] **Step 9: 创建 `frontend/src/App.tsx`**

最小可运行版本，包含路由骨架和占位页面。

```tsx
import { Routes, Route, Navigate } from "react-router-dom";

function Placeholder({ name }: { name: string }) {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-ink-primary">{name}</h1>
      <p className="mt-2 text-ink-secondary">页面开发中...</p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/scenario" replace />} />
      <Route path="/scenario" element={<Placeholder name="情景分析" />} />
      <Route path="/backtest" element={<Placeholder name="MVP 回测" />} />
      <Route path="/ensemble" element={<Placeholder name="集成策略" />} />
      <Route path="/trend-scan" element={<Placeholder name="趋势扫描" />} />
      <Route path="/reports" element={<Placeholder name="报告中心" />} />
      <Route path="/data" element={<Placeholder name="数据管理" />} />
    </Routes>
  );
}
```

- [ ] **Step 10: 修改 `run_scenario_server.py` 挂载 dist 目录**

将静态文件挂载从 `frontend/` 改为 `frontend/dist/`，兼容构建产物。

```python
frontend_dir = Path(__file__).parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
```

- [ ] **Step 11: 修改 `.gitignore` 增加 `frontend/node_modules/` 和 `frontend/dist/`**

在 `.gitignore` 末尾追加：

```
# Frontend build artifacts
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 12: 安装前端依赖并验证构建**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm install
npm run build
```

预期：`dist/` 目录生成，包含 `index.html`、`assets/` 子目录。

- [ ] **Step 13: 验证后端挂载构建产物**

```bash
cd /workspace/csqaq-glove-quant
python -c "
from run_scenario_server import app
from fastapi.testclient import TestClient
client = TestClient(app)
resp = client.get('/')
print(f'Status: {resp.status_code}')
print(f'Contains root div: {\"root\" in resp.text}')
"
```

预期：Status 200，包含 `<div id="root">`。

- [ ] **Step 14: 提交**

```bash
git add frontend/ run_scenario_server.py .gitignore
git commit -m "feat(web): 初始化 React + Vite + Tailwind 前端项目骨架"
```

---

## Task 2: API 类型定义与统一客户端

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/format.ts`

- [ ] **Step 1: 创建 `frontend/src/types/api.ts`**

定义所有 API 响应的 TypeScript 类型，覆盖现有端点和即将新增的端点。

```typescript
// ===== 情景分析 =====
export interface Scenario {
  name: string;
  scenario_key: string;
  probability: number;
  direction: number;
  direction_label: "bullish" | "bearish" | "neutral";
  support: number;
  resistance: number;
  target: number;
  stop_loss: number;
  position_size: number;
  wave_sketch: WavePoint[];
  description: string;
  source: string;
}

export interface WavePoint {
  label: string;
  price: number;
}

export interface ScenarioGenerateResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  generation_time_ms: number;
  cached: boolean;
  scenarios: Scenario[];
  per_period: Record<string, unknown>;
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

export interface HistoryMatch {
  neighbor_index?: number;
  neighbor_timestamp?: string;
  candidate_start?: string;
  candidate_end?: string;
  candidate_start_timestamp?: string;
  distance: number;
  future_return_5?: number;
  future_return_7?: number;
}

export interface HistoryResponse {
  sub_index: string;
  period: string;
  method: string;
  matches: HistoryMatch[];
}

export interface TemplateMatch {
  template_name: string;
  confidence: number;
  direction: string;
  support: number | null;
  resistance: number | null;
  target: number | null;
  stop_loss: number | null;
}

export interface TemplatesResponse {
  sub_index: string;
  period: string;
  min_confidence: number;
  matches: TemplateMatch[];
}

export interface MetaResponse {
  available_sub_indices: string[];
  supported_periods: string[];
  default_period: string;
}

// ===== 回测 =====
export interface TradeRecord {
  entry_index: number;
  entry_time: string;
  entry_price: number;
  exit_time: string;
  exit_price: number | null;
  exit_reason: string;
  pnl: number;
  return_pct: number;
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
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

export interface MvpBacktestResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
}

// ===== 集成策略 =====
export interface EnsembleBacktestResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  ensemble_metrics: BacktestMetrics;
  pullback_metrics: BacktestMetrics;
  trend_metrics: BacktestMetrics;
  ensemble_equity: EquityPoint[];
  pullback_equity: EquityPoint[];
  trend_equity: EquityPoint[];
  trades: TradeRecord[];
}

// ===== 趋势扫描 =====
export interface TrendScanResult {
  params: Record<string, unknown>;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
}

export interface TaskStatusResponse {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  message: string;
  result?: TrendScanResult[];
  error?: string;
}

// ===== 报告 =====
export interface ReportFile {
  name: string;
  path: string;
  size: number;
  modified: string;
}

export interface ReportsListResponse {
  reports: ReportFile[];
}

export interface ReportContentResponse {
  name: string;
  content: Record<string, unknown>;
}

// ===== 数据管理 =====
export interface CacheEntry {
  sub_index: string;
  period: string;
  file: string;
  bars: number;
  size: number;
  modified: string;
}

export interface CacheStatusResponse {
  cache_dir: string;
  entries: CacheEntry[];
}

// ===== 监控 =====
export interface MonitoringResponse {
  metrics: {
    window_seconds: number;
    request_count: number;
    failure_count: number;
    failure_rate: number;
    latency_p50_ms: number;
    latency_p99_ms: number;
    per_endpoint: Record<string, { request_count: number; failure_rate: number; latency_p99_ms: number }>;
  };
  alerts: Array<{ metric: string; value: number; threshold: number; severity: string }>;
}
```

- [ ] **Step 2: 创建 `frontend/src/lib/api.ts`**

统一 API 客户端，封装 fetch 请求、错误处理、类型推断。

```typescript
const BASE = "";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
  const query = params
    ? "?" + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      ).toString()
    : "";
  const res = await fetch(`${BASE}${path}${query}`);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // 情景分析
  getMeta: () => request<import("../types/api").MetaResponse>("/scenario/meta"),
  getScenarios: (sub_index: string, period: string, refresh = false) =>
    request<import("../types/api").ScenarioGenerateResponse>("/scenario/generate", { sub_index, period, refresh }),
  getOhlc: (sub_index: string, period: string) =>
    request<import("../types/api").OhlcResponse>("/scenario/ohlc", { sub_index, period }),
  getHistory: (sub_index: string, period: string, method: string, n_neighbors: number) =>
    request<import("../types/api").HistoryResponse>("/scenario/history", { sub_index, period, method, n_neighbors }),
  getTemplates: (sub_index: string, period: string, min_confidence: number) =>
    request<import("../types/api").TemplatesResponse>("/scenario/templates", { sub_index, period, min_confidence }),
  explainScenario: (scenario: unknown, context: unknown) =>
    postJson<{ prompt: string; explanation: string; wave_sketch_description: string }>("/scenario/explain", { scenario, context }),

  // 回测
  getBacktestEquity: (sub_index: string, period: string) =>
    request<import("../types/api").BacktestEquityResponse>("/backtest/equity", { sub_index, period }),
  runMvpBacktest: (sub_index: string, period: string) =>
    request<import("../types/api").MvpBacktestResponse>("/backtest/mvp", { sub_index, period }),

  // 集成策略
  runEnsemble: (sub_index: string, period: string) =>
    request<import("../types/api").EnsembleBacktestResponse>("/ensemble/run", { sub_index, period }),

  // 趋势扫描
  startTrendScan: (sub_index: string, period: string) =>
    request<{ task_id: string }>("/trend-scan/start", { sub_index, period }),
  getTaskStatus: (task_id: string) =>
    request<import("../types/api").TaskStatusResponse>(`/trend-scan/status/${task_id}`),

  // 报告
  listReports: () => request<import("../types/api").ReportsListResponse>("/reports/list"),
  getReport: (name: string) =>
    request<import("../types/api").ReportContentResponse>("/reports/get", { name }),

  // 数据管理
  getCacheStatus: () => request<import("../types/api").CacheStatusResponse>("/data/cache-status"),
  refreshData: (sub_index: string, period: string) =>
    request<{ success: boolean; bars: number }>("/data/refresh", { sub_index, period }),

  // 监控
  getMonitoring: () => request<import("../types/api").MonitoringResponse>("/monitoring/metrics"),
};
```

- [ ] **Step 3: 创建 `frontend/src/lib/format.ts`**

```typescript
export function formatPercent(value: number, decimals = 2): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number, decimals = 2): string {
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
```

- [ ] **Step 4: 验证 TypeScript 编译**

```bash
cd /workspace/csqaq-glove-quant/frontend
npx tsc --noEmit
```

预期：无错误输出。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/types/api.ts frontend/src/lib/api.ts frontend/src/lib/format.ts
git commit -m "feat(web): 添加 API 类型定义与统一客户端封装"
```

---

## Task 3: 通用 UI 组件库

**Files:**
- Create: `frontend/src/components/Card.tsx`
- Create: `frontend/src/components/MetricCard.tsx`
- Create: `frontend/src/components/LoadingState.tsx`
- Create: `frontend/src/components/ErrorState.tsx`
- Create: `frontend/src/components/ScenarioBar.tsx`

- [ ] **Step 1: 创建 `frontend/src/components/Card.tsx`**

通用卡片容器，带标题、可选操作区。

```tsx
import { ReactNode } from "react";

interface CardProps {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, actions, children, className = "" }: CardProps) {
  return (
    <div className={`bg-surface-card rounded-xl shadow-card border border-surface-border ${className}`}>
      {title && (
        <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
          <h3 className="text-sm font-semibold text-ink-primary">{title}</h3>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: 创建 `frontend/src/components/MetricCard.tsx`**

单个指标展示卡片：数值 + 标签 + 可选颜色。

```tsx
interface MetricCardProps {
  label: string;
  value: string | number;
  hint?: string;
  color?: "default" | "bull" | "bear" | "neutral";
}

const colorMap = {
  default: "text-ink-primary",
  bull: "text-bull",
  bear: "text-bear",
  neutral: "text-neutral",
};

export function MetricCard({ label, value, hint, color = "default" }: MetricCardProps) {
  return (
    <div className="bg-surface-card rounded-xl shadow-card border border-surface-border p-4">
      <div className="text-xs text-ink-secondary mb-1">{label}</div>
      <div className={`text-2xl font-bold ${colorMap[color]}`}>{value}</div>
      {hint && <div className="text-xs text-ink-muted mt-1">{hint}</div>}
    </div>
  );
}
```

- [ ] **Step 3: 创建 `frontend/src/components/LoadingState.tsx`**

骨架屏加载态，可配置行数。

```tsx
export function LoadingState({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-surface-hover rounded animate-pulse"
          style={{ width: `${100 - i * 15}%` }}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: 创建 `frontend/src/components/ErrorState.tsx`**

错误态组件，含重试按钮。

```tsx
interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-8">
      <div className="text-bear text-sm">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-1.5 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 transition-colors"
        >
          重试
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 创建 `frontend/src/components/ScenarioBar.tsx`**

情景概率条形图，点击高亮。

```tsx
import { Scenario } from "../types/api";

interface ScenarioBarProps {
  scenarios: Scenario[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

function scenarioColor(label: string): string {
  if (label === "bullish") return "bg-bull";
  if (label === "bearish") return "bg-bear";
  return "bg-neutral";
}

export function ScenarioBar({ scenarios, selectedIndex, onSelect }: ScenarioBarProps) {
  return (
    <div className="flex flex-col gap-3">
      {scenarios.map((s, i) => (
        <div
          key={i}
          onClick={() => onSelect(i)}
          className={`cursor-pointer p-2 rounded-lg transition-colors ${
            i === selectedIndex ? "bg-brand-50 ring-1 ring-brand-100" : "hover:bg-surface-hover"
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm text-ink-primary w-20 truncate">{s.name}</span>
            <div className="flex-1 h-5 bg-surface-base rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all duration-500 ${scenarioColor(s.direction_label)}`}
                style={{ width: `${(s.probability * 100).toFixed(1)}%` }}
              />
            </div>
            <span className="text-xs text-ink-secondary w-12 text-right">
              {(s.probability * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: 验证编译**

```bash
cd /workspace/csqaq-glove-quant/frontend
npx tsc --noEmit
```

预期：无错误。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/
git commit -m "feat(web): 添加通用 UI 组件库（Card/MetricCard/LoadingState/ErrorState/ScenarioBar）"
```

---

## Task 4: 页面布局与导航

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/TopBar.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/components/Sidebar.tsx`**

左侧导航栏，包含 6 个功能入口和监控状态摘要。

```tsx
import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/scenario", label: "情景分析", icon: "📊" },
  { to: "/backtest", label: "MVP 回测", icon: "📈" },
  { to: "/ensemble", label: "集成策略", icon: "🔀" },
  { to: "/trend-scan", label: "趋势扫描", icon: "🔍" },
  { to: "/reports", label: "报告中心", icon: "📋" },
  { to: "/data", label: "数据管理", icon: "💾" },
];

export function Sidebar() {
  return (
    <aside className="w-56 bg-surface-card border-r border-surface-border flex flex-col">
      <div className="px-5 py-4 border-b border-surface-border">
        <h1 className="text-base font-bold text-ink-primary">CSQAQ 量化平台</h1>
        <p className="text-xs text-ink-muted mt-0.5">饰品价格行为策略</p>
      </div>
      <nav className="flex-1 py-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                isActive
                  ? "bg-brand-50 text-brand-600 font-medium border-r-2 border-brand-500"
                  : "text-ink-secondary hover:bg-surface-hover hover:text-ink-primary"
              }`
            }
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: 创建 `frontend/src/components/TopBar.tsx`**

顶部全局控制栏：子指数选择、周期选择、刷新按钮、状态指示、监控摘要。

```tsx
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { MetaResponse, MonitoringResponse } from "../types/api";

interface TopBarProps {
  subIndex: string;
  period: string;
  onSubIndexChange: (v: string) => void;
  onPeriodChange: (v: string) => void;
  onRefresh: () => void;
  status: string;
}

export function TopBar({ subIndex, period, onSubIndexChange, onPeriodChange, onRefresh, status }: TopBarProps) {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [monitoring, setMonitoring] = useState<MonitoringResponse | null>(null);

  useEffect(() => {
    api.getMeta().then(setMeta).catch(() => {});
  }, []);

  useEffect(() => {
    const load = () => api.getMonitoring().then(setMonitoring).catch(() => {});
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const indices = meta?.available_sub_indices.length ? meta.available_sub_indices : ["手套", "匕首", "百元主战", "贴纸"];
  const periods = [
    { value: "1day", label: "日线" },
    { value: "4hour", label: "4小时" },
    { value: "1hour", label: "1小时" },
    { value: "7day", label: "周线" },
  ];

  return (
    <header className="h-14 bg-surface-card border-b border-surface-border flex items-center gap-4 px-5">
      <div className="flex items-center gap-2">
        <label className="text-xs text-ink-secondary">子指数</label>
        <select
          value={subIndex}
          onChange={(e) => onSubIndexChange(e.target.value)}
          className="bg-surface-base border border-surface-border rounded-lg px-2.5 py-1.5 text-sm text-ink-primary focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          {indices.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2">
        <label className="text-xs text-ink-secondary">周期</label>
        <select
          value={period}
          onChange={(e) => onPeriodChange(e.target.value)}
          className="bg-surface-base border border-surface-border rounded-lg px-2.5 py-1.5 text-sm text-ink-primary focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          {periods.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </div>

      <button
        onClick={onRefresh}
        className="px-3 py-1.5 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 transition-colors"
      >
        刷新
      </button>

      <span className="text-xs text-ink-muted">{status}</span>

      <div className="ml-auto flex items-center gap-3 text-xs text-ink-secondary">
        {monitoring && (
          <>
            <span>P99: {monitoring.metrics.latency_p99_ms.toFixed(0)}ms</span>
            <span>请求: {monitoring.metrics.request_count}</span>
            {monitoring.alerts.length > 0 ? (
              <span className="text-bear font-medium">告警: {monitoring.alerts.length}</span>
            ) : (
              <span className="text-bull">运行正常</span>
            )}
          </>
        )}
      </div>
    </header>
  );
}
```

- [ ] **Step 3: 创建 `frontend/src/components/Layout.tsx`**

页面布局骨架，通过 React Context 向子页面传递子指数/周期等全局状态。

```tsx
import { ReactNode, useState, useCallback } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface LayoutProps {
  children: (props: { subIndex: string; period: string; refreshKey: number }) => ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [subIndex, setSubIndex] = useState("手套");
  const [period, setPeriod] = useState("1day");
  const [refreshKey, setRefreshKey] = useState(0);
  const [status, setStatus] = useState("");

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setStatus("刷新中...");
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar
          subIndex={subIndex}
          period={period}
          onSubIndexChange={(v) => { setSubIndex(v); setRefreshKey((k) => k + 1); }}
          onPeriodChange={(v) => { setPeriod(v); setRefreshKey((k) => k + 1); }}
          onRefresh={handleRefresh}
          status={status}
        />
        <main className="flex-1 overflow-auto p-6 bg-surface-base">
          {children({ subIndex, period, refreshKey })}
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 修改 `frontend/src/App.tsx` 集成 Layout**

```tsx
import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/Layout";

function Placeholder({ name }: { name: string }) {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-ink-primary">{name}</h1>
      <p className="mt-2 text-ink-secondary">页面开发中...</p>
    </div>
  );
}

export default function App() {
  return (
    <Layout>
      {({ subIndex, period, refreshKey }) => (
        <Routes>
          <Route path="/" element={<Navigate to="/scenario" replace />} />
          <Route path="/scenario" element={<Placeholder name="情景分析" />} />
          <Route path="/backtest" element={<Placeholder name="MVP 回测" />} />
          <Route path="/ensemble" element={<Placeholder name="集成策略" />} />
          <Route path="/trend-scan" element={<Placeholder name="趋势扫描" />} />
          <Route path="/reports" element={<Placeholder name="报告中心" />} />
          <Route path="/data" element={<Placeholder name="数据管理" />} />
        </Routes>
      )}
    </Layout>
  );
}
```

- [ ] **Step 5: 构建验证**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build
```

预期：构建成功，`dist/` 生成。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/Layout.tsx frontend/src/components/Sidebar.tsx frontend/src/components/TopBar.tsx frontend/src/App.tsx
git commit -m "feat(web): 添加页面布局骨架与侧边栏导航"
```

---

## Task 5: 后端异步任务队列

**Files:**
- Create: `src/api/task_queue.py`
- Create: `tests/test_task_queue.py`

- [ ] **Step 1: 创建 `tests/test_task_queue.py`**

```python
"""Tests for the lightweight async task queue."""

import time
import threading
from src.api.task_queue import TaskQueue, TaskStatus


def test_create_task_returns_pending():
    queue = TaskQueue()
    task_id = queue.create(lambda: None)
    status = queue.get_status(task_id)
    assert status.status == TaskStatus.PENDING
    assert status.progress == 0.0


def test_run_task_completes():
    queue = TaskQueue()
    task_id = queue.create(lambda: {"result": "ok"})
    queue.run(task_id)
    time.sleep(0.1)
    status = queue.get_status(task_id)
    assert status.status == TaskStatus.COMPLETED
    assert status.result == {"result": "ok"}


def test_failed_task_records_error():
    def boom():
        raise RuntimeError("explosion")
    queue = TaskQueue()
    task_id = queue.create(boom)
    queue.run(task_id)
    time.sleep(0.1)
    status = queue.get_status(task_id)
    assert status.status == TaskStatus.FAILED
    assert "explosion" in status.error


def test_progress_callback():
    def work(progress):
        progress(0.5)
        time.sleep(0.05)
        progress(1.0)
        return "done"
    queue = TaskQueue()
    task_id = queue.create(work)
    queue.run(task_id)
    time.sleep(0.15)
    status = queue.get_status(task_id)
    assert status.status == TaskStatus.COMPLETED
    assert status.progress == 1.0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_task_queue.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'src.api.task_queue'`

- [ ] **Step 3: 创建 `src/api/task_queue.py`**

```python
"""Lightweight in-memory async task queue for long-running operations.

Tasks run in background threads. Progress is reported via a callback.
Results are stored in memory and evicted after 1 hour.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Any | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": round(self.progress, 4),
            "message": self.message,
            "result": self.result,
            "error": self.error,
        }


class TaskQueue:
    """Thread-safe in-memory task queue with TTL eviction."""

    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def create(self, fn: Callable[..., Any]) -> str:
        """Register a task and return its ID. Does not start execution."""
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = TaskInfo(task_id=task_id)
        return task_id

    def run(self, task_id: str) -> None:
        """Start a registered task in a background thread."""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                raise KeyError(f"Task not found: {task_id}")

    def get_status(self, task_id: str) -> TaskInfo:
        with self._lock:
            self._evict_old()
            info = self._tasks.get(task_id)
            if info is None:
                raise KeyError(f"Task not found: {task_id}")
            return info

    def _evict_old(self) -> None:
        cutoff = time.time() - self._ttl
        expired = [tid for tid, info in self._tasks.items() if info.created_at < cutoff]
        for tid in expired:
            del self._tasks[tid]


# Singleton instance
TASK_QUEUE = TaskQueue()
```

Wait - the `create` method stores `fn` but doesn't keep it. Let me fix the implementation to store the callable and run it.

- [ ] **Step 4: 修正 `src/api/task_queue.py` 完整实现**

```python
"""Lightweight in-memory async task queue for long-running operations.

Tasks run in background threads. Progress is reported via a callback.
Results are stored in memory and evicted after 1 hour.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Any | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": round(self.progress, 4),
            "message": self.message,
            "result": self.result,
            "error": self.error,
        }


class TaskQueue:
    """Thread-safe in-memory task queue with TTL eviction."""

    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._fns: dict[str, Callable[..., Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def create(self, fn: Callable[..., Any]) -> str:
        """Register a task and return its ID. Does not start execution."""
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = TaskInfo(task_id=task_id)
            self._fns[task_id] = fn
        return task_id

    def run(self, task_id: str) -> None:
        """Start a registered task in a background thread."""
        with self._lock:
            info = self._tasks.get(task_id)
            fn = self._fns.get(task_id)
            if info is None or fn is None:
                raise KeyError(f"Task not found: {task_id}")
            info.status = TaskStatus.RUNNING

        def _execute() -> None:
            try:
                def progress_cb(value: float, message: str = "") -> None:
                    with self._lock:
                        ti = self._tasks.get(task_id)
                        if ti:
                            ti.progress = value
                            ti.message = message

                result = fn(progress_cb)
                with self._lock:
                    ti = self._tasks.get(task_id)
                    if ti:
                        ti.status = TaskStatus.COMPLETED
                        ti.progress = 1.0
                        ti.result = result
            except Exception as exc:
                with self._lock:
                    ti = self._tasks.get(task_id)
                    if ti:
                        ti.status = TaskStatus.FAILED
                        ti.error = str(exc)

        thread = threading.Thread(target=_execute, daemon=True)
        thread.start()

    def get_status(self, task_id: str) -> TaskInfo:
        with self._lock:
            self._evict_old()
            info = self._tasks.get(task_id)
            if info is None:
                raise KeyError(f"Task not found: {task_id}")
            return info

    def _evict_old(self) -> None:
        cutoff = time.time() - self._ttl
        expired = [tid for tid, info in self._tasks.items() if info.created_at < cutoff]
        for tid in expired:
            del self._tasks[tid]
            self._fns.pop(tid, None)


# Singleton instance
TASK_QUEUE = TaskQueue()
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_task_queue.py -v
```

预期：4 个测试全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add src/api/task_queue.py tests/test_task_queue.py
git commit -m "feat(api): 添加轻量异步任务队列支持长耗时操作"
```

---

## Task 6: MVP 回测 API 端点

**Files:**
- Create: `tests/test_mvp_endpoint.py`
- Modify: `src/api/backtest_endpoints.py`

- [ ] **Step 1: 创建 `tests/test_mvp_endpoint.py`**

```python
"""Tests for the /backtest/mvp endpoint."""

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.backtest_endpoints import router as backtest_router


def _make_ohlc(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        "open": price,
        "high": price * 1.01,
        "low": price * 0.99,
        "close": price,
    })


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    monkeypatch.setenv("CSQAQ_CACHE_PATH", "/tmp/csqaq_test_cache_mvp")
    import src.api.backtest_endpoints as endpoints
    monkeypatch.setattr(endpoints, "_load_ohlc", lambda sub_index, period, **kw: _make_ohlc())
    app = FastAPI()
    app.include_router(backtest_router)
    return TestClient(app)


def test_mvp_returns_metrics_and_trades(client):
    resp = client.get("/backtest/mvp", params={"sub_index": "手套", "period": "1day"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sub_index"] == "手套"
    assert data["period"] == "1day"
    assert "metrics" in data
    metrics = data["metrics"]
    assert "total_return" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "win_rate" in metrics
    assert "total_trades" in metrics
    assert "equity_curve" in data
    assert "trades" in data
    assert isinstance(data["equity_curve"], list)
    assert isinstance(data["trades"], list)


def test_mvp_invalid_period_returns_400(client):
    resp = client.get("/backtest/mvp", params={"sub_index": "手套", "period": "10year"})
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_mvp_endpoint.py -v
```

预期：FAIL，404 或端点不存在。

- [ ] **Step 3: 在 `src/api/backtest_endpoints.py` 末尾添加 `/mvp` 端点**

在文件末尾追加：

```python
from src.analysis.metrics import summarize as _summarize_metrics


@router.get("/mvp")
def mvp_backtest(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, Any]:
    """Run the MVP pullback strategy backtest and return metrics + equity + trades."""
    period = _normalize_period(period)
    start = time.perf_counter()
    try:
        df = _load_ohlc(sub_index, period)
        df_with_signals = generate_signals(
            df,
            SignalParams(
                use_smart_money=True,
                use_trend_following=True,
            ),
        )
        result = run_backtest(df_with_signals, BacktestParams())
        metrics = _summarize_metrics(result)

        equity_records = [
            {"timestamp": _to_iso(ts), "equity": round(float(val), 4)}
            for ts, val in result.equity_curve.items()
        ]
        trade_records = [
            {
                "entry_index": t.entry_index,
                "entry_time": _to_iso(t.entry_time),
                "entry_price": round(float(t.entry_price), 6),
                "exit_time": _to_iso(t.exit_time),
                "exit_price": round(float(t.exit_price), 6) if t.exit_price else None,
                "exit_reason": t.exit_reason,
                "pnl": round(float(t.pnl), 4),
                "return_pct": round(float(t.return_pct), 6),
            }
            for t in result.trades
        ]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MVP backtest failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/backtest/mvp",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
        extra={"trade_count": metrics["total_trades"]},
    )
    return {
        "sub_index": sub_index,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "equity_curve": equity_records,
        "trades": trade_records,
    }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_mvp_endpoint.py -v
```

预期：2 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add tests/test_mvp_endpoint.py src/api/backtest_endpoints.py
git commit -m "feat(api): 添加 /backtest/mvp 端点返回回测指标与净值曲线"
```

---

## Task 7: 集成策略 API 端点

**Files:**
- Create: `tests/test_ensemble_endpoint.py`
- Create: `src/api/ensemble_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 创建 `tests/test_ensemble_endpoint.py`**

```python
"""Tests for the /ensemble/run endpoint."""

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.ensemble_endpoints import router as ensemble_router


def _make_ohlc(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(99)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        "open": price,
        "high": price * 1.01,
        "low": price * 0.99,
        "close": price,
    })


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    monkeypatch.setenv("CSQAQ_CACHE_PATH", "/tmp/csqaq_test_cache_ens")
    import src.api.ensemble_endpoints as endpoints
    monkeypatch.setattr(endpoints, "_load_ohlc", lambda sub_index, period, **kw: _make_ohlc())
    app = FastAPI()
    app.include_router(ensemble_router)
    return TestClient(app)


def test_ensemble_returns_three_strategies(client):
    resp = client.get("/ensemble/run", params={"sub_index": "手套", "period": "1day"})
    assert resp.status_code == 200
    data = resp.json()
    for key in ("ensemble_metrics", "pullback_metrics", "trend_metrics"):
        assert key in data
        assert "total_return" in data[key]
        assert "sharpe_ratio" in data[key]
    assert "ensemble_equity" in data
    assert "pullback_equity" in data
    assert "trend_equity" in data
    assert "trades" in data


def test_ensemble_invalid_period(client):
    resp = client.get("/ensemble/run", params={"sub_index": "手套", "period": "2month"})
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_ensemble_endpoint.py -v
```

预期：FAIL，模块不存在。

- [ ] **Step 3: 创建 `src/api/ensemble_endpoints.py`**

```python
"""Ensemble strategy API endpoints.

Exposes the dual-strategy ensemble (pullback + trend-following) over HTTP,
returning metrics for all three strategies and their equity curves.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.analysis.metrics import summarize as _summarize
from src.api.logging import get_logger, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.ensemble import EnsembleParams, generate_ensemble_signals
from src.strategy.signal import SignalParams, generate_signals
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)

LOGGER = get_logger("csqaq.ensemble_api")
router = APIRouter(prefix="/ensemble", tags=["ensemble"])


def _equity_records(equity_curve: pd.Series) -> list[dict[str, Any]]:
    records = []
    for ts, val in equity_curve.items():
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        records.append({"timestamp": ts_iso, "equity": round(float(val), 4)})
    return records


def _trade_records(trades: list) -> list[dict[str, Any]]:
    records = []
    for t in trades:
        records.append({
            "entry_index": t.entry_index,
            "entry_time": t.entry_time.isoformat() if hasattr(t.entry_time, "isoformat") else str(t.entry_time),
            "entry_price": round(float(t.entry_price), 6),
            "exit_time": t.exit_time.isoformat() if hasattr(t.exit_time, "isoformat") else str(t.exit_time),
            "exit_price": round(float(t.exit_price), 6) if t.exit_price else None,
            "exit_reason": t.exit_reason,
            "pnl": round(float(t.pnl), 4),
            "return_pct": round(float(t.return_pct), 6),
        })
    return records


@router.get("/run")
def run_ensemble(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, Any]:
    """Run the ensemble, pullback, and trend-following backtests side by side."""
    period = _normalize_period(period)
    start = time.perf_counter()
    try:
        df = _load_ohlc(sub_index, period)

        # Ensemble
        ens_df = generate_ensemble_signals(df, EnsembleParams())
        ens_result = run_backtest(ens_df, BacktestParams())
        ens_metrics = _summarize(ens_result)

        # Pullback only
        pb_df = generate_signals(df, SignalParams(use_smart_money=True, use_trend_following=False))
        pb_result = run_backtest(pb_df, BacktestParams())
        pb_metrics = _summarize(pb_result)

        # Trend only
        tf_df = generate_trend_following_signals(df, TrendFollowingParams())
        tf_result = run_backtest(tf_df, BacktestParams())
        tf_metrics = _summarize(tf_result)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ensemble backtest failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    log_request(
        LOGGER,
        endpoint="/ensemble/run",
        sub_index=sub_index,
        period=period,
        latency_ms=latency_ms,
    )
    return {
        "sub_index": sub_index,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ensemble_metrics": ens_metrics,
        "pullback_metrics": pb_metrics,
        "trend_metrics": tf_metrics,
        "ensemble_equity": _equity_records(ens_result.equity_curve),
        "pullback_equity": _equity_records(pb_result.equity_curve),
        "trend_equity": _equity_records(tf_result.equity_curve),
        "trades": _trade_records(ens_result.trades),
    }
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册 ensemble router**

在 `app.include_router(backtest_router)` 后添加：

```python
from src.api.ensemble_endpoints import router as ensemble_router
app.include_router(ensemble_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_ensemble_endpoint.py -v
```

预期：2 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add tests/test_ensemble_endpoint.py src/api/ensemble_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加 /ensemble/run 端点返回三策略对比"
```

---

## Task 8: 趋势扫描 API 端点（异步任务）

**Files:**
- Create: `tests/test_trend_scan_endpoint.py`
- Create: `src/api/trend_scan_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 创建 `tests/test_trend_scan_endpoint.py`**

```python
"""Tests for the /trend-scan endpoints."""

import time
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.trend_scan_endpoints import router as trend_scan_router, TASK_QUEUE


def _make_ohlc(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(77)
    price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        "open": price,
        "high": price * 1.01,
        "low": price * 0.99,
        "close": price,
    })


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    monkeypatch.setenv("CSQAQ_CACHE_PATH", "/tmp/csqaq_test_cache_scan")
    import src.api.trend_scan_endpoints as endpoints
    monkeypatch.setattr(endpoints, "_load_ohlc", lambda sub_index, period, **kw: _make_ohlc())
    # Reset task queue between tests
    TASK_QUEUE._tasks.clear()
    TASK_QUEUE._fns.clear()
    app = FastAPI()
    app.include_router(trend_scan_router)
    return TestClient(app)


def test_start_returns_task_id(client):
    resp = client.get("/trend-scan/start", params={"sub_index": "手套", "period": "1day"})
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert len(data["task_id"]) > 0


def test_status_returns_progress(client):
    start_resp = client.get("/trend-scan/start", params={"sub_index": "手套", "period": "1day"})
    task_id = start_resp.json()["task_id"]
    # Wait for task to complete (scan is fast on synthetic data)
    for _ in range(30):
        status_resp = client.get(f"/trend-scan/status/{task_id}")
        data = status_resp.json()
        if data["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    assert data["status"] in ("completed", "failed", "running", "pending")


def test_status_unknown_task_returns_404(client):
    resp = client.get("/trend-scan/status/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_trend_scan_endpoint.py -v
```

预期：FAIL，模块不存在。

- [ ] **Step 3: 创建 `src/api/trend_scan_endpoints.py`**

```python
"""Trend-following parameter scan API endpoints.

Exposes the parameter grid scan as an async task. The frontend polls
/trend-scan/status/{task_id} for progress and results.
"""

from __future__ import annotations

import itertools
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.api.logging import get_logger
from src.api.scenario_endpoints import _load_ohlc, _normalize_period
from src.api.task_queue import TASK_QUEUE, TaskStatus
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)

LOGGER = get_logger("csqaq.trend_scan_api")
router = APIRouter(prefix="/trend-scan", tags=["trend-scan"])


def _param_grid() -> list[dict[str, Any]]:
    """Return trend-following parameter combinations to evaluate."""
    grid: list[dict[str, Any]] = []
    for (
        swing_order,
        confirmations,
        trend_strength_threshold,
        use_di_filter,
        use_volatility_filter,
    ) in itertools.product(
        (1, 2),
        (1, 2),
        (None, 20.0, 25.0, 30.0),
        (False, True),
        (False, True),
    ):
        grid.append({
            "swing_order": swing_order,
            "confirmations": confirmations,
            "trend_strength_threshold": trend_strength_threshold,
            "use_di_filter": use_di_filter,
            "use_volatility_filter": use_volatility_filter,
        })
    return grid


def _run_scan(sub_index: str, period: str, progress_cb) -> list[dict[str, Any]]:
    """Execute the full parameter scan. Returns sorted results."""
    df = _load_ohlc(sub_index, period)
    grid = _param_grid()
    total = len(grid)
    results: list[dict[str, Any]] = []

    from src.analysis.metrics import summarize as _summarize

    for i, params_dict in enumerate(grid):
        params = TrendFollowingParams(**params_dict)
        try:
            signals_df = generate_trend_following_signals(df, params)
            result = run_backtest(signals_df, BacktestParams())
            metrics = _summarize(result)
            results.append({
                "params": params_dict,
                "total_return": metrics["total_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "win_rate": metrics["win_rate"],
                "total_trades": metrics["total_trades"],
            })
        except Exception:
            results.append({
                "params": params_dict,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
            })
        progress_cb((i + 1) / total, f"已扫描 {i + 1}/{total} 组参数")

    results.sort(key=lambda r: r["total_return"], reverse=True)
    return results


@router.get("/start")
def start_scan(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, str]:
    """Start a trend-following parameter scan as a background task."""
    _normalize_period(period)

    def task_fn(progress_cb):
        return _run_scan(sub_index, period, progress_cb)

    task_id = TASK_QUEUE.create(task_fn)
    TASK_QUEUE.run(task_id)
    LOGGER.info("Trend scan started", extra={"task_id": task_id, "sub_index": sub_index})
    return {"task_id": task_id}


@router.get("/status/{task_id}")
def scan_status(task_id: str) -> dict[str, Any]:
    """Return the current status of a scan task."""
    try:
        info = TASK_QUEUE.get_status(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return info.to_dict()
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册 trend_scan router**

在 ensemble router 后添加：

```python
from src.api.trend_scan_endpoints import router as trend_scan_router
app.include_router(trend_scan_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_trend_scan_endpoint.py -v
```

预期：3 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add tests/test_trend_scan_endpoint.py src/api/trend_scan_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加趋势扫描异步任务端点 /trend-scan/start + /status"
```

---

## Task 9: 报告查看 API 端点

**Files:**
- Create: `tests/test_report_endpoint.py`
- Create: `src/api/report_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 创建 `tests/test_report_endpoint.py`**

```python
"""Tests for the /reports endpoints."""

import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.report_endpoints import router as report_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a temp reports dir with sample files."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "phase18_test.json").write_text(json.dumps({"phase": 18, "status": "ok"}))
    (reports_dir / "phase17_perf.json").write_text(json.dumps({"phase": 17}))

    monkeypatch.setattr("src.api.report_endpoints.REPORTS_DIR", reports_dir)
    app = FastAPI()
    app.include_router(report_router)
    return TestClient(app)


def test_list_reports(client):
    resp = client.get("/reports/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "reports" in data
    assert len(data["reports"]) == 2
    names = [r["name"] for r in data["reports"]]
    assert "phase18_test.json" in names
    assert "phase17_perf.json" in names


def test_get_report_content(client):
    resp = client.get("/reports/get", params={"name": "phase18_test.json"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "phase18_test.json"
    assert data["content"]["phase"] == 18


def test_get_nonexistent_report_returns_404(client):
    resp = client.get("/reports/get", params={"name": "nonexistent.json"})
    assert resp.status_code == 404


def test_path_traversal_blocked(client):
    resp = client.get("/reports/get", params={"name": "../../../etc/passwd"})
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_report_endpoint.py -v
```

预期：FAIL，模块不存在。

- [ ] **Step 3: 创建 `src/api/report_endpoints.py`**

```python
"""Report viewing API endpoints.

Lists JSON report files in the reports/ directory and returns their contents.
Path traversal is blocked: only direct filenames in the reports directory are allowed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.logging import get_logger

LOGGER = get_logger("csqaq.report_api")
router = APIRouter(prefix="/reports", tags=["reports"])

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


@router.get("/list")
def list_reports() -> dict[str, Any]:
    """List all JSON report files with metadata."""
    reports: list[dict[str, Any]] = []
    if not REPORTS_DIR.exists():
        return {"reports": []}

    for path in sorted(REPORTS_DIR.glob("*.json")):
        stat = path.stat()
        reports.append({
            "name": path.name,
            "path": str(path.relative_to(REPORTS_DIR)),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return {"reports": reports}


@router.get("/get")
def get_report(name: str = Query(..., description="Report filename (no path separators).")) -> dict[str, Any]:
    """Return the JSON content of a specific report file."""
    # Block path traversal: only allow simple filenames
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid filename: path separators not allowed")

    file_path = REPORTS_DIR / name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Report not found: {name}")

    try:
        content = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in report: {exc}") from exc

    return {"name": name, "content": content}
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册 report router**

```python
from src.api.report_endpoints import router as report_router
app.include_router(report_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_report_endpoint.py -v
```

预期：4 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add tests/test_report_endpoint.py src/api/report_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加报告查看端点 /reports/list + /reports/get"
```

---

## Task 10: 数据管理 API 端点

**Files:**
- Create: `tests/test_data_endpoint.py`
- Create: `src/api/data_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 创建 `tests/test_data_endpoint.py`**

```python
"""Tests for the /data endpoints."""

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.data_endpoints import router as data_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # Create a sample parquet cache file
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC"),
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
    })
    df.to_parquet(cache_dir / "手套_1day.parquet")

    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    monkeypatch.setattr("src.api.data_endpoints._cache_dir", lambda: cache_dir)
    monkeypatch.setattr("src.api.data_endpoints._load_ohlc",
                        lambda sub_index, period, **kw: df)

    app = FastAPI()
    app.include_router(data_router)
    return TestClient(app)


def test_cache_status(client):
    resp = client.get("/data/cache-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert len(data["entries"]) >= 1
    entry = data["entries"][0]
    assert entry["sub_index"] == "手套"
    assert entry["bars"] == 100


def test_refresh_data(client):
    resp = client.get("/data/refresh", params={"sub_index": "手套", "period": "1day"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["bars"] > 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_data_endpoint.py -v
```

预期：FAIL，模块不存在。

- [ ] **Step 3: 创建 `src/api/data_endpoints.py`**

```python
"""Data management API endpoints.

Provides cache status inspection and manual data refresh capabilities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.api.logging import get_logger
from src.api.scenario_endpoints import _load_ohlc, _normalize_period
from src.config import Settings
from src.data.cache import cache_file_path

LOGGER = get_logger("csqaq.data_api")
router = APIRouter(prefix="/data", tags=["data"])


def _cache_dir() -> Path:
    """Return the cache directory path."""
    settings = Settings()
    return Path(settings.cache_path)


@router.get("/cache-status")
def cache_status() -> dict[str, Any]:
    """List all cached OHLC files with bar counts and sizes."""
    cdir = _cache_dir()
    entries: list[dict[str, Any]] = []

    if not cdir.exists():
        return {"cache_dir": str(cdir), "entries": []}

    for path in sorted(cdir.glob("*.parquet")):
        try:
            df = pd.read_parquet(path)
            bars = len(df)
        except Exception:
            bars = 0

        # Parse sub_index and period from filename: <name>_<period>.parquet
        stem = path.stem
        parts = stem.rsplit("_", 1)
        sub_index = parts[0] if len(parts) == 2 else stem
        period = parts[1] if len(parts) == 2 else "unknown"

        stat = path.stat()
        entries.append({
            "sub_index": sub_index,
            "period": period,
            "file": path.name,
            "bars": bars,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    return {"cache_dir": str(cdir), "entries": entries}


@router.get("/refresh")
def refresh_data(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, Any]:
    """Force-refresh cached OHLC data for a sub-index."""
    period = _normalize_period(period)
    try:
        df = _load_ohlc(sub_index, period, force_refresh=True)
        return {"success": True, "bars": len(df), "sub_index": sub_index, "period": period}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Data refresh failed: {exc}") from exc
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册 data router**

```python
from src.api.data_endpoints import router as data_router
app.include_router(data_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_data_endpoint.py -v
```

预期：2 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add tests/test_data_endpoint.py src/api/data_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加数据管理端点 /data/cache-status + /data/refresh"
```

---

## Task 11: 情景分析页面（前端）

**Files:**
- Create: `frontend/src/pages/ScenarioPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/ScenarioPage.tsx`**

情景分析页面：K 线图（ECharts）、情景概率条、交易建议、相似历史、模板匹配、浪形草图、LLM 解释。使用 ECharts 替代 Lightweight Charts。

```tsx
import { useEffect, useState, useCallback } from "react";
import ReactECharts from "echarts-for-react";
import { api } from "../lib/api";
import { formatPercent, formatNumber } from "../lib/format";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ScenarioBar } from "../components/ScenarioBar";
import {
  Scenario, OhlcBar, HistoryMatch, TemplateMatch,
  ScenarioGenerateResponse, OhlcResponse, HistoryResponse, TemplatesResponse,
} from "../types/api";

interface Props {
  subIndex: string;
  period: string;
  refreshKey: number;
}

export function ScenarioPage({ subIndex, period, refreshKey }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ohlc, setOhlc] = useState<OhlcBar[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [history, setHistory] = useState<HistoryMatch[]>([]);
  const [templates, setTemplates] = useState<TemplateMatch[]>([]);
  const [explanation, setExplanation] = useState("");
  const [genTime, setGenTime] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [ohlcRes, genRes, histRes, tmplRes] = await Promise.all([
        api.getOhlc(subIndex, period),
        api.getScenarios(subIndex, period, refreshKey > 0),
        api.getHistory(subIndex, period, "knn", 10),
        api.getTemplates(subIndex, period, 0.5),
      ]);
      setOhlc(ohlcRes.ohlc);
      setScenarios(genRes.scenarios);
      setGenTime(genRes.generation_time_ms);
      setHistory(histRes.matches);
      setTemplates(tmplRes.matches);
      setSelectedIdx(0);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period, refreshKey]);

  useEffect(() => { load(); }, [load]);

  // Fetch explanation when scenario selection changes
  useEffect(() => {
    if (!scenarios.length) return;
    const s = scenarios[selectedIdx];
    api.explainScenario(s, { sub_index: subIndex, period, current_price: ohlc[ohlc.length - 1]?.close })
      .then((res) => setExplanation(res.explanation))
      .catch(() => setExplanation("解释生成失败"));
  }, [selectedIdx, scenarios, subIndex, period, ohlc]);

  const chartOption = {
    animation: false,
    grid: { left: "8%", right: "4%", top: "8%", bottom: "12%" },
    xAxis: {
      type: "category",
      data: ohlc.map((b) => b.timestamp.slice(0, 10)),
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    dataZoom: [
      { type: "inside", start: 60, end: 100 },
      { type: "slider", start: 60, end: 100, height: 20, bottom: 8 },
    ],
    series: [{
      type: "candlestick",
      data: ohlc.map((b) => [b.open, b.close, b.low, b.high]),
      itemStyle: {
        color: "#16a34a", color0: "#dc2626",
        borderColor: "#16a34a", borderColor0: "#dc2626",
      },
    }],
  };

  if (loading) return <div className="grid grid-cols-2 gap-4"><Card title="加载中"><LoadingState rows={4} /></Card><Card title="加载中"><LoadingState rows={4} /></Card></div>;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const selected = scenarios[selectedIdx];

  return (
    <div className="space-y-4">
      <div className="flex gap-3 text-xs text-ink-secondary">
        <span>生成耗时: {genTime.toFixed(0)}ms</span>
        <span>K线数量: {ohlc.length}</span>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* K线图 */}
        <div className="col-span-2">
          <Card title="K 线图">
            <ReactECharts option={chartOption} style={{ height: 400 }} opts={{ renderer: "canvas" }} />
          </Card>
        </div>

        {/* 情景概率 + 交易建议 */}
        <div className="space-y-4">
          <Card title="情景概率">
            <ScenarioBar scenarios={scenarios} selectedIndex={selectedIdx} onSelect={setSelectedIdx} />
          </Card>
          {selected && (
            <Card title="交易建议">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-ink-secondary">方向</span>
                  <span className={selected.direction > 0 ? "text-bull" : selected.direction < 0 ? "text-bear" : "text-neutral"}>
                    {selected.direction > 0 ? "偏多" : selected.direction < 0 ? "偏空" : "中性"}
                  </span>
                </div>
                <div className="flex justify-between"><span className="text-ink-secondary">概率</span><span className="font-medium">{formatPercent(selected.probability)}</span></div>
                <div className="flex justify-between"><span className="text-ink-secondary">支撑</span><span>{formatNumber(selected.support)}</span></div>
                <div className="flex justify-between"><span className="text-ink-secondary">阻力</span><span>{formatNumber(selected.resistance)}</span></div>
                <div className="flex justify-between"><span className="text-ink-secondary">目标</span><span className="text-bull">{formatNumber(selected.target)}</span></div>
                <div className="flex justify-between"><span className="text-ink-secondary">止损</span><span className="text-bear">{formatNumber(selected.stop_loss)}</span></div>
                <div className="flex justify-between"><span className="text-ink-secondary">仓位</span><span className="font-medium">{formatPercent(selected.position_size)}</span></div>
              </div>
            </Card>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* 相似历史 */}
        <Card title="相似历史片段">
          <div className="space-y-1 max-h-64 overflow-auto">
            {history.length === 0 ? <span className="text-sm text-ink-muted">暂无数据</span> : history.map((m, i) => (
              <div key={i} className="flex justify-between items-center py-1.5 px-2 rounded hover:bg-surface-hover text-sm cursor-pointer">
                <span className="text-ink-secondary">{m.neighbor_timestamp?.slice(0, 10) || m.candidate_start_timestamp?.slice(0, 10) || "-"}</span>
                <span className={m.future_return_5 != null ? (m.future_return_5 > 0 ? "text-bull" : "text-bear") : "text-ink-muted"}>
                  {m.future_return_5 != null ? formatPercent(m.future_return_5) : "-"}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* 模板匹配 */}
        <Card title="模板匹配">
          <div className="space-y-2 max-h-64 overflow-auto">
            {templates.length === 0 ? <span className="text-sm text-ink-muted">暂无匹配</span> : templates.map((t, i) => (
              <div key={i} className="p-2 bg-surface-base rounded-lg">
                <div className="text-sm font-medium text-ink-primary">{t.template_name}</div>
                <div className="text-xs text-ink-secondary mt-0.5">
                  置信度 {formatPercent(t.confidence)} | 目标 {t.target || "-"} | 止损 {t.stop_loss || "-"}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* LLM 解释 */}
        <Card title="情景解释">
          <div className="text-sm text-ink-primary leading-relaxed min-h-[200px]">
            {explanation || "加载中..."}
          </div>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 修改 `frontend/src/App.tsx` 接入 ScenarioPage**

将情景分析路由替换为实际组件：

```tsx
import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ScenarioPage } from "./pages/ScenarioPage";

function Placeholder({ name }: { name: string }) {
  return <div className="p-8"><h1 className="text-2xl font-semibold text-ink-primary">{name}</h1><p className="mt-2 text-ink-secondary">页面开发中...</p></div>;
}

export default function App() {
  return (
    <Layout>
      {({ subIndex, period, refreshKey }) => (
        <Routes>
          <Route path="/" element={<Navigate to="/scenario" replace />} />
          <Route path="/scenario" element={<ScenarioPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
          <Route path="/backtest" element={<Placeholder name="MVP 回测" />} />
          <Route path="/ensemble" element={<Placeholder name="集成策略" />} />
          <Route path="/trend-scan" element={<Placeholder name="趋势扫描" />} />
          <Route path="/reports" element={<Placeholder name="报告中心" />} />
          <Route path="/data" element={<Placeholder name="数据管理" />} />
        </Routes>
      )}
    </Layout>
  );
}
```

- [ ] **Step 3: 构建验证**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build
```

预期：构建成功。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/ScenarioPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现情景分析页面（ECharts K线图 + 概率条 + 历史匹配）"
```

---

## Task 12: MVP 回测页面（前端）

**Files:**
- Create: `frontend/src/pages/BacktestPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/BacktestPage.tsx`**

MVP 回测页面：指标卡片网格 + 净值曲线 + 交易记录表。

```tsx
import { useEffect, useState, useCallback } from "react";
import ReactECharts from "echarts-for-react";
import { api } from "../lib/api";
import { formatPercent, formatNumber, formatDateTime } from "../lib/format";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { MvpBacktestResponse } from "../types/api";

interface Props {
  subIndex: string;
  period: string;
  refreshKey: number;
}

export function BacktestPage({ subIndex, period, refreshKey }: Props) {
  const [data, setData] = useState<MvpBacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.runMvpBacktest(subIndex, period);
      setData(res);
    } catch (e: any) {
      setError(e.message || "回测失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period]);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (loading) return <Card title="回测运行中"><LoadingState rows={5} /></Card>;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return null;

  const m = data.metrics;

  const equityOption = {
    animation: false,
    grid: { left: "8%", right: "4%", top: "8%", bottom: "12%" },
    xAxis: {
      type: "category",
      data: data.equity_curve.map((p) => p.timestamp.slice(0, 10)),
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    dataZoom: [{ type: "inside", start: 0, end: 100 }],
    series: [{
      type: "line",
      data: data.equity_curve.map((p) => p.equity),
      smooth: false,
      lineStyle: { color: "#3b82f6", width: 2 },
      areaStyle: { color: "rgba(59, 130, 246, 0.08)" },
    }],
  };

  return (
    <div className="space-y-4">
      {/* 指标卡片 */}
      <div className="grid grid-cols-5 gap-3">
        <MetricCard label="总收益率" value={formatPercent(m.total_return)} color={m.total_return >= 0 ? "bull" : "bear"} />
        <MetricCard label="最终净值" value={formatNumber(m.final_equity)} />
        <MetricCard label="夏普比率" value={formatNumber(m.sharpe_ratio)} />
        <MetricCard label="最大回撤" value={formatPercent(m.max_drawdown)} color="bear" />
        <MetricCard label="交易次数" value={m.total_trades} />
        <MetricCard label="胜率" value={formatPercent(m.win_rate)} color={m.win_rate >= 0.5 ? "bull" : "neutral"} />
        <MetricCard label="盈亏比" value={m.profit_factor === Infinity ? "∞" : formatNumber(m.profit_factor)} />
        <MetricCard label="平均收益" value={formatPercent(m.avg_trade_return)} />
        <MetricCard label="初始资金" value={formatNumber(m.initial_capital)} />
        <MetricCard label="标的/周期" value={`${subIndex} / ${period}`} />
      </div>

      {/* 净值曲线 */}
      <Card title="净值曲线">
        <ReactECharts option={equityOption} style={{ height: 360 }} opts={{ renderer: "canvas" }} />
      </Card>

      {/* 交易记录 */}
      <Card title={`交易记录（共 ${data.trades.length} 笔）`}>
        <div className="overflow-auto max-h-96">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-ink-secondary border-b border-surface-border">
                <th className="text-left py-2 px-3">#</th>
                <th className="text-left py-2 px-3">买入时间</th>
                <th className="text-right py-2 px-3">买入价</th>
                <th className="text-left py-2 px-3">卖出时间</th>
                <th className="text-right py-2 px-3">卖出价</th>
                <th className="text-left py-2 px-3">退出原因</th>
                <th className="text-right py-2 px-3">盈亏</th>
                <th className="text-right py-2 px-3">收益率</th>
              </tr>
            </thead>
            <tbody>
              {data.trades.map((t, i) => (
                <tr key={i} className="border-b border-surface-border hover:bg-surface-hover">
                  <td className="py-2 px-3 text-ink-muted">{t.entry_index}</td>
                  <td className="py-2 px-3 text-ink-secondary">{formatDateTime(t.entry_time)}</td>
                  <td className="py-2 px-3 text-right">{formatNumber(t.entry_price)}</td>
                  <td className="py-2 px-3 text-ink-secondary">{formatDateTime(t.exit_time)}</td>
                  <td className="py-2 px-3 text-right">{t.exit_price ? formatNumber(t.exit_price) : "-"}</td>
                  <td className="py-2 px-3 text-ink-secondary">{t.exit_reason}</td>
                  <td className={`py-2 px-3 text-right font-medium ${t.pnl >= 0 ? "text-bull" : "text-bear"}`}>{formatNumber(t.pnl)}</td>
                  <td className={`py-2 px-3 text-right ${t.return_pct >= 0 ? "text-bull" : "text-bear"}`}>{formatPercent(t.return_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 修改 `frontend/src/App.tsx` 接入 BacktestPage**

```tsx
import { BacktestPage } from "./pages/BacktestPage";
```

将 `<Route path="/backtest" ...>` 替换为：

```tsx
<Route path="/backtest" element={<BacktestPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build && cd ..
git add frontend/src/pages/BacktestPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现 MVP 回测页面（指标卡片 + 净值曲线 + 交易表）"
```

---

## Task 13: 集成策略页面（前端）

**Files:**
- Create: `frontend/src/pages/EnsemblePage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/EnsemblePage.tsx`**

三策略对比页面：三列指标对比表 + 三条净值曲线叠加图。

```tsx
import { useEffect, useState, useCallback } from "react";
import ReactECharts from "echarts-for-react";
import { api } from "../lib/api";
import { formatPercent, formatNumber } from "../lib/format";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EnsembleBacktestResponse, BacktestMetrics } from "../types/api";

interface Props {
  subIndex: string;
  period: string;
  refreshKey: number;
}

const STRATEGIES: Array<{ key: "ensemble" | "pullback" | "trend"; label: string; color: string }> = [
  { key: "ensemble", label: "集成策略", color: "#3b82f6" },
  { key: "pullback", label: "回撤策略", color: "#16a34a" },
  { key: "trend", label: "趋势跟踪", color: "#f59e0b" },
];

export function EnsemblePage({ subIndex, period, refreshKey }: Props) {
  const [data, setData] = useState<EnsembleBacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.runEnsemble(subIndex, period);
      setData(res);
    } catch (e: any) {
      setError(e.message || "集成策略运行失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period]);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (loading) return <Card title="三策略回测运行中"><LoadingState rows={5} /></Card>;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return null;

  const metricsMap: Record<string, BacktestMetrics> = {
    ensemble: data.ensemble_metrics,
    pullback: data.pullback_metrics,
    trend: data.trend_metrics,
  };
  const equityMap: Record<string, { timestamp: string; equity: number }[]> = {
    ensemble: data.ensemble_equity,
    pullback: data.pullback_equity,
    trend: data.trend_equity,
  };

  const chartOption = {
    animation: false,
    legend: { data: STRATEGIES.map((s) => s.label), top: 0, textStyle: { color: "#64748b" } },
    grid: { left: "8%", right: "4%", top: "10%", bottom: "12%" },
    xAxis: {
      type: "category",
      data: equityMap.ensemble.map((p) => p.timestamp.slice(0, 10)),
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    dataZoom: [{ type: "inside", start: 0, end: 100 }],
    series: STRATEGIES.map((s) => ({
      name: s.label,
      type: "line",
      data: equityMap[s.key].map((p) => p.equity),
      smooth: false,
      lineStyle: { color: s.color, width: 2 },
      symbol: "none",
    })),
  };

  const metricRows: Array<{ label: string; key: keyof BacktestMetrics; isPercent?: boolean }> = [
    { label: "总收益率", key: "total_return", isPercent: true },
    { label: "最终净值", key: "final_equity" },
    { label: "夏普比率", key: "sharpe_ratio" },
    { label: "最大回撤", key: "max_drawdown", isPercent: true },
    { label: "交易次数", key: "total_trades" },
    { label: "胜率", key: "win_rate", isPercent: true },
    { label: "盈亏比", key: "profit_factor" },
    { label: "平均收益", key: "avg_trade_return", isPercent: true },
  ];

  return (
    <div className="space-y-4">
      <Card title="三策略净值曲线对比">
        <ReactECharts option={chartOption} style={{ height: 400 }} opts={{ renderer: "canvas" }} />
      </Card>

      <Card title="指标对比">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="text-left py-2 px-3 text-xs text-ink-secondary">指标</th>
              {STRATEGIES.map((s) => (
                <th key={s.key} className="text-right py-2 px-3 text-sm font-medium" style={{ color: s.color }}>{s.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricRows.map((row) => (
              <tr key={row.key} className="border-b border-surface-border hover:bg-surface-hover">
                <td className="py-2 px-3 text-ink-secondary">{row.label}</td>
                {STRATEGIES.map((s) => {
                  const val = metricsMap[s.key][row.key];
                  const display = row.isPercent
                    ? formatPercent(val as number)
                    : val === Infinity ? "∞" : formatNumber(val as number);
                  return <td key={s.key} className="py-2 px-3 text-right font-medium">{display}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 修改 `frontend/src/App.tsx` 接入 EnsemblePage**

```tsx
import { EnsemblePage } from "./pages/EnsemblePage";
```

替换路由：

```tsx
<Route path="/ensemble" element={<EnsemblePage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build && cd ..
git add frontend/src/pages/EnsemblePage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现集成策略页面（三策略净值对比 + 指标对比表）"
```

---

## Task 14: 趋势扫描页面（前端）

**Files:**
- Create: `frontend/src/pages/TrendScanPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/TrendScanPage.tsx`**

趋势扫描页面：启动扫描按钮、进度条、结果排名表、参数详情展开。

```tsx
import { useState, useCallback, useRef } from "react";
import ReactECharts from "echarts-for-react";
import { api } from "../lib/api";
import { formatPercent, formatNumber } from "../lib/format";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { TrendScanResult, TaskStatusResponse } from "../types/api";

interface Props {
  subIndex: string;
  period: string;
  refreshKey: number;
}

export function TrendScanPage({ subIndex, period }: Props) {
  const [taskId, setTaskId] = useState("");
  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<number | null>(null);

  const startScan = useCallback(async () => {
    setLoading(true);
    setError("");
    setStatus(null);
    try {
      const { task_id } = await api.startTrendScan(subIndex, period);
      setTaskId(task_id);
      // Poll for status
      const poll = async () => {
        try {
          const s = await api.getTaskStatus(task_id);
          setStatus(s);
          if (s.status === "running" || s.status === "pending") {
            pollRef.current = window.setTimeout(poll, 1000);
          }
        } catch (e: any) {
          setError(e.message);
        }
      };
      poll();
    } catch (e: any) {
      setError(e.message || "启动扫描失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period]);

  const results = status?.result || [];
  const isRunning = status?.status === "running" || status?.status === "pending";

  // Chart: top 10 results bar chart
  const topResults = results.slice(0, 10);
  const chartOption = topResults.length > 0 ? {
    animation: false,
    grid: { left: "15%", right: "4%", top: "8%", bottom: "12%" },
    xAxis: {
      type: "value",
      axisLabel: { color: "#64748b", fontSize: 11, formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    yAxis: {
      type: "category",
      data: topResults.map((_, i) => `#${i + 1}`).reverse(),
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    series: [{
      type: "bar",
      data: topResults.map((r) => r.total_return).reverse(),
      itemStyle: {
        color: (params: any) => params.value >= 0 ? "#16a34a" : "#dc2626",
      },
    }],
  } : null;

  return (
    <div className="space-y-4">
      <Card title="趋势跟踪参数扫描">
        <div className="flex items-center gap-4">
          <button
            onClick={startScan}
            disabled={isRunning}
            className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? "扫描中..." : "启动扫描"}
          </button>
          <span className="text-sm text-ink-secondary">标的: {subIndex} | 周期: {period}</span>
        </div>

        {status && (
          <div className="mt-4">
            <div className="flex items-center gap-3 mb-2">
              <span className={`text-sm font-medium ${
                status.status === "completed" ? "text-bull" :
                status.status === "failed" ? "text-bear" : "text-brand-500"
              }`}>
                {status.status === "completed" ? "已完成" :
                 status.status === "failed" ? "失败" :
                 status.status === "running" ? "运行中" : "等待中"}
              </span>
              <span className="text-xs text-ink-secondary">{status.message}</span>
            </div>
            <div className="w-full h-2 bg-surface-hover rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-500"
                style={{ width: `${status.progress * 100}%` }}
              />
            </div>
            <span className="text-xs text-ink-muted mt-1 block">{(status.progress * 100).toFixed(0)}%</span>
          </div>
        )}

        {error && <ErrorState message={error} onRetry={startScan} />}
      </Card>

      {chartOption && (
        <Card title="收益率 Top 10">
          <ReactECharts option={chartOption} style={{ height: 320 }} opts={{ renderer: "canvas" }} />
        </Card>
      )}

      {results.length > 0 && (
        <Card title={`扫描结果（共 ${results.length} 组参数，按收益率排序）`}>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-ink-secondary border-b border-surface-border">
                  <th className="text-left py-2 px-3">排名</th>
                  <th className="text-left py-2 px-3">参数</th>
                  <th className="text-right py-2 px-3">总收益</th>
                  <th className="text-right py-2 px-3">夏普</th>
                  <th className="text-right py-2 px-3">最大回撤</th>
                  <th className="text-right py-2 px-3">胜率</th>
                  <th className="text-right py-2 px-3">交易数</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i} className="border-b border-surface-border hover:bg-surface-hover">
                    <td className="py-2 px-3 text-ink-muted">#{i + 1}</td>
                    <td className="py-2 px-3 text-xs text-ink-secondary">
                      {Object.entries(r.params).map(([k, v]) => `${k}=${String(v)}`).join(", ")}
                    </td>
                    <td className={`py-2 px-3 text-right font-medium ${r.total_return >= 0 ? "text-bull" : "text-bear"}`}>
                      {formatPercent(r.total_return)}
                    </td>
                    <td className="py-2 px-3 text-right">{formatNumber(r.sharpe_ratio)}</td>
                    <td className="py-2 px-3 text-right text-bear">{formatPercent(r.max_drawdown)}</td>
                    <td className="py-2 px-3 text-right">{formatPercent(r.win_rate)}</td>
                    <td className="py-2 px-3 text-right">{r.total_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 修改 `frontend/src/App.tsx` 接入 TrendScanPage**

```tsx
import { TrendScanPage } from "./pages/TrendScanPage";
```

替换路由：

```tsx
<Route path="/trend-scan" element={<TrendScanPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build && cd ..
git add frontend/src/pages/TrendScanPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现趋势扫描页面（异步任务 + 进度条 + 结果排名表）"
```

---

## Task 15: 报告中心页面（前端）

**Files:**
- Create: `frontend/src/pages/ReportsPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/ReportsPage.tsx`**

报告中心页面：左侧报告文件列表，右侧选中报告的 JSON 内容可视化展示。

```tsx
import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { formatBytes, formatDateTime } from "../lib/format";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ReportFile } from "../types/api";

export function ReportsPage() {
  const [reports, setReports] = useState<ReportFile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listReports();
      setReports(res.reports);
      if (res.reports.length > 0 && !selected) {
        setSelected(res.reports[0].name);
      }
    } catch (e: any) {
      setError(e.message || "加载报告列表失败");
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => { loadList(); }, [loadList]);

  useEffect(() => {
    if (!selected) return;
    api.getReport(selected)
      .then((res) => setContent(res.content))
      .catch((e) => setError(e.message));
  }, [selected]);

  const renderValue = (value: unknown, depth = 0): string => {
    if (value === null) return "null";
    if (typeof value === "string") return value;
    if (typeof value === "number") return value.toLocaleString("zh-CN");
    if (typeof value === "boolean") return value ? "是" : "否";
    return JSON.stringify(value, null, 2);
  };

  const renderContent = (data: Record<string, unknown>) => {
    const entries = Object.entries(data);
    return (
      <div className="space-y-2">
        {entries.map(([key, value]) => (
          <div key={key} className="flex gap-3 py-1.5 border-b border-surface-border">
            <span className="text-sm text-ink-secondary w-48 shrink-0">{key}</span>
            <span className="text-sm text-ink-primary flex-1 break-all">
              {typeof value === "object" && value !== null
                ? <pre className="text-xs bg-surface-base p-2 rounded overflow-auto">{JSON.stringify(value, null, 2)}</pre>
                : renderValue(value)
              }
            </span>
          </div>
        ))}
      </div>
    );
  };

  if (loading) return <Card title="加载中"><LoadingState rows={4} /></Card>;
  if (error) return <ErrorState message={error} onRetry={loadList} />;

  return (
    <div className="grid grid-cols-4 gap-4">
      {/* 报告列表 */}
      <Card title={`报告文件（${reports.length}）`}>
        <div className="space-y-1 max-h-[600px] overflow-auto">
          {reports.map((r) => (
            <div
              key={r.name}
              onClick={() => setSelected(r.name)}
              className={`cursor-pointer p-2.5 rounded-lg transition-colors ${
                selected === r.name ? "bg-brand-50 ring-1 ring-brand-100" : "hover:bg-surface-hover"
              }`}
            >
              <div className="text-sm text-ink-primary truncate">{r.name}</div>
              <div className="text-xs text-ink-muted mt-0.5">
                {formatBytes(r.size)} · {formatDateTime(r.modified)}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 报告内容 */}
      <div className="col-span-3">
        <Card title={selected || "选择报告"}>
          {content ? renderContent(content) : <span className="text-sm text-ink-muted">请选择左侧报告查看内容</span>}
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 修改 `frontend/src/App.tsx` 接入 ReportsPage**

```tsx
import { ReportsPage } from "./pages/ReportsPage";
```

替换路由：

```tsx
<Route path="/reports" element={<ReportsPage />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build && cd ..
git add frontend/src/pages/ReportsPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现报告中心页面（文件列表 + JSON 可视化展示）"
```

---

## Task 16: 数据管理页面（前端）

**Files:**
- Create: `frontend/src/pages/DataManagementPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/DataManagementPage.tsx`**

数据管理页面：缓存文件表格（子指数、周期、K线数、大小、修改时间）、刷新按钮。

```tsx
import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { formatBytes, formatDateTime } from "../lib/format";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { CacheEntry } from "../types/api";

export function DataManagementPage() {
  const [entries, setEntries] = useState<CacheEntry[]>([]);
  const [cacheDir, setCacheDir] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.getCacheStatus();
      setEntries(res.entries);
      setCacheDir(res.cache_dir);
    } catch (e: any) {
      setError(e.message || "加载缓存状态失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = async (subIndex: string, period: string) => {
    setRefreshing(`${subIndex}_${period}`);
    try {
      await api.refreshData(subIndex, period);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRefreshing(null);
    }
  };

  const totalBars = entries.reduce((sum, e) => sum + e.bars, 0);
  const totalSize = entries.reduce((sum, e) => sum + e.size, 0);

  if (loading) return <Card title="加载中"><LoadingState rows={4} /></Card>;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="缓存文件数" value={entries.length} />
        <MetricCard label="总K线数" value={totalBars.toLocaleString("zh-CN")} />
        <MetricCard label="总大小" value={formatBytes(totalSize)} />
      </div>

      <Card title="缓存文件列表">
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-ink-secondary border-b border-surface-border">
                <th className="text-left py-2 px-3">子指数</th>
                <th className="text-left py-2 px-3">周期</th>
                <th className="text-left py-2 px-3">文件名</th>
                <th className="text-right py-2 px-3">K线数</th>
                <th className="text-right py-2 px-3">大小</th>
                <th className="text-left py-2 px-3">修改时间</th>
                <th className="text-center py-2 px-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} className="border-b border-surface-border hover:bg-surface-hover">
                  <td className="py-2 px-3 font-medium">{e.sub_index}</td>
                  <td className="py-2 px-3 text-ink-secondary">{e.period}</td>
                  <td className="py-2 px-3 text-ink-muted text-xs font-mono">{e.file}</td>
                  <td className="py-2 px-3 text-right">{e.bars.toLocaleString("zh-CN")}</td>
                  <td className="py-2 px-3 text-right text-ink-secondary">{formatBytes(e.size)}</td>
                  <td className="py-2 px-3 text-ink-secondary text-xs">{formatDateTime(e.modified)}</td>
                  <td className="py-2 px-3 text-center">
                    <button
                      onClick={() => handleRefresh(e.sub_index, e.period)}
                      disabled={refreshing === `${e.sub_index}_${e.period}`}
                      className="px-2.5 py-1 text-xs bg-brand-50 text-brand-600 rounded hover:bg-brand-100 disabled:opacity-50 transition-colors"
                    >
                      {refreshing === `${e.sub_index}_${e.period}` ? "刷新中..." : "刷新"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="text-xs text-ink-muted">缓存目录: {cacheDir}</div>
    </div>
  );
}
```

- [ ] **Step 2: 修改 `frontend/src/App.tsx` 接入 DataManagementPage**

```tsx
import { DataManagementPage } from "./pages/DataManagementPage";
```

替换路由：

```tsx
<Route path="/data" element={<DataManagementPage />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build && cd ..
git add frontend/src/pages/DataManagementPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现数据管理页面（缓存列表 + 刷新操作）"
```

---

## Task 17: 端到端集成验证与旧前端清理

**Files:**
- Delete: `frontend/static/app.js`
- Delete: `frontend/static/style.css`
- Modify: `docs/deployment.md`

- [ ] **Step 1: 删除旧前端文件**

```bash
cd /workspace/csqaq-glove-quant
git rm frontend/static/app.js frontend/static/style.css
```

- [ ] **Step 2: 运行全部后端测试**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/ -v --tb=short
```

预期：所有测试 PASS。

- [ ] **Step 3: 构建前端并启动服务验证**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build
cd ..
python -c "
from run_scenario_server import app
from fastapi.testclient import TestClient
client = TestClient(app)

# 前端首页
r1 = client.get('/')
assert r1.status_code == 200
assert 'root' in r1.text, 'Frontend not served'

# API 端点
r2 = client.get('/scenario/meta')
assert r2.status_code == 200

r3 = client.get('/backtest/mvp', params={'sub_index': '手套', 'period': '1day'})
assert r3.status_code == 200
assert 'metrics' in r3.json()

r4 = client.get('/reports/list')
assert r4.status_code == 200

r5 = client.get('/data/cache-status')
assert r5.status_code == 200

print('All integration checks passed!')
"
```

预期：所有断言通过。

- [ ] **Step 4: 更新 `docs/deployment.md` 增加前端构建步骤**

在"第三步：安装依赖"之后增加前端构建步骤：

```markdown
## 第三步半：构建前端

前端使用 React + Vite 构建，需安装 Node.js（>= 18）：

```bash
cd frontend
npm install
npm run build
```

构建产物在 `frontend/dist/`，由后端 `run_scenario_server.py` 自动挂载。
开发时可运行 `npm run dev` 启动热更新开发服务器（端口 5173），API 请求自动代理到 8000 端口。
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat(web): 清理旧前端文件，完成全功能 Web 可视化平台集成"
```

---

## 架构决策说明

### 性能考量

1. **前端构建优化**：Vite 默认进行代码分割和 tree-shaking，首屏只加载当前路由的 chunk。ECharts 按需引入（`echarts-for-react` 支持按需注册组件），避免打包全量图表库。

2. **后端长耗时操作**：趋势扫描通过异步任务队列（`task_queue.py`）在后台线程执行，前端通过轮询获取进度。不阻塞 API 主线程，其他请求正常响应。

3. **数据缓存**：现有 `SCENARIO_CACHE`（5 分钟 TTL 内存缓存）继续工作。回测结果可考虑增加类似的内存缓存，但 MVP 阶段回测耗时在秒级，暂不需要。

4. **前端渲染**：ECharts 使用 Canvas 渲染，对大量 K 线数据（数百根）性能足够。`animation: false` 禁用动画，减少重绘开销。React 的 `useCallback` 和 `useMemo` 避免不必要的重渲染。

### 可维护性考量

1. **组件化拆分**：每个页面是独立组件，修改一个页面不影响其他页面。通用 UI 组件（Card、MetricCard 等）复用率高，修改一处全局生效。

2. **TypeScript 类型安全**：所有 API 响应有类型定义（`types/api.ts`），后端接口变更时前端编译期即可发现不匹配。

3. **后端端点模块化**：每个功能域一个端点文件（`ensemble_endpoints.py`、`trend_scan_endpoints.py` 等），新增功能只需新建文件 + 在 `run_scenario_server.py` 注册路由。

4. **测试覆盖**：每个新端点都有对应的测试文件，遵循 TDD 流程。前端虽无单元测试，但 TypeScript 编译 + 构建验证提供了基本保障。

### 功能增强便利性

1. **新增页面**：在 `pages/` 下新建组件 → 在 `App.tsx` 添加路由 → 完成。不影响现有页面。

2. **新增 API 端点**：在 `src/api/` 下新建端点文件 → 在 `run_scenario_server.py` 注册 → 在 `lib/api.ts` 添加调用方法 → 完成。

3. **新增图表**：ECharts 配置是纯 JS 对象，新增图表只需在页面组件中添加一个 `chartOption` + `<ReactECharts>`。

4. **主题调整**：所有颜色定义在 `tailwind.config.js` 中，修改主题色板一处生效全局。
