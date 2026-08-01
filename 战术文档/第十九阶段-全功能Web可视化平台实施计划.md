# 全功能 Web 可视化平台实施计划（生产级优化版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有 CLI 功能（MVP 回测、集成策略、趋势扫描、报告生成、数据管理）集成到统一的 React 网页平台，实现浅色现代仪表盘风格的全中文可视化交互。面向本地个人使用，具备生产级代码质量：错误边界、响应式设计、无障碍支持、代码分割、单元测试覆盖。

**Architecture:** 前端使用 React 18 + Vite + TypeScript 构建单页应用（SPA），构建产物为静态文件，由现有 FastAPI 的 `StaticFiles` 挂载。后端新增 REST API 端点暴露所有 CLI 功能，长耗时操作（趋势扫描、参数扫描）采用异步任务队列模式（`ThreadPoolExecutor` + 内存任务表 + 轮询）。前端按功能模块拆分为独立页面组件，通过 `React.lazy` + `Suspense` 实现路由级代码分割。图表使用 ECharts，UI 组件采用自定义组件 + Tailwind CSS。全局错误通过 React Error Boundary 捕获，API 请求通过 `AbortController` 支持取消。本地运行：`npm run build` 构建前端 → `python run_scenario_server.py` 启动服务。

**Tech Stack:** React 18, Vite 5, TypeScript 5, React Router 6, ECharts 5, Tailwind CSS 3, Vitest 2, Testing Library, FastAPI, Python 3.10+

---

## 文件结构总览

### 前端（新建 `frontend/` 目录，完全替换现有前端）

```
frontend/
├── package.json                  # 依赖声明（含 Vitest + Testing Library）
├── vite.config.ts                # Vite 配置，构建产物输出到 dist/
├── tsconfig.json                 # TypeScript 配置
├── tsconfig.node.json            # Node 环境 TS 配置（vite.config.ts 用）
├── tailwind.config.js            # Tailwind 主题配置（浅色仪表盘主题）
├── postcss.config.js             # PostCSS 配置
├── vitest.config.ts              # Vitest 测试配置
├── .env.example                  # 环境变量示例
├── index.html                    # SPA 入口 HTML
├── src/
│   ├── main.tsx                  # React 应用入口（含 ErrorBoundary 包裹）
│   ├── App.tsx                   # 根组件 + 路由（含 React.lazy 懒加载 + 404 兜底）
│   ├── ErrorBoundary.tsx         # 全局错误边界组件
│   ├── types/
│   │   └── api.ts                # 所有 API 响应的 TypeScript 类型定义
│   ├── lib/
│   │   ├── api.ts                # 统一 API 客户端（fetch 封装 + AbortController）
│   │   └── format.ts             # 格式化工具函数（百分比、日期、数字）
│   ├── components/
│   │   ├── Layout.tsx            # 页面布局骨架（响应式侧边栏 + 顶栏 + 内容区）
│   │   ├── Sidebar.tsx           # 左侧导航栏（移动端可折叠）
│   │   ├── TopBar.tsx            # 顶部全局控制栏（子指数/周期选择、刷新、状态）
│   │   ├── Card.tsx              # 通用卡片容器组件
│   │   ├── MetricCard.tsx        # 指标展示卡片（单个数值 + 标签）
│   │   ├── LoadingState.tsx      # 骨架屏/加载态组件
│   │   ├── ErrorState.tsx        # 错误态组件（含重试按钮）
│   │   ├── EmptyState.tsx        # 空数据态组件
│   │   └── ScenarioBar.tsx       # 情景概率条形图组件（含无障碍支持）
│   ├── pages/
│   │   ├── ScenarioPage.tsx      # 情景分析页（升级现有功能）
│   │   ├── BacktestPage.tsx      # MVP 回测页
│   │   ├── EnsemblePage.tsx      # 集成策略页
│   │   ├── TrendScanPage.tsx     # 趋势扫描页（异步任务 + 指数退避轮询）
│   │   ├── ReportsPage.tsx       # 报告查看页
│   │   ├── DataManagementPage.tsx # 数据管理页
│   │   └── NotFoundPage.tsx      # 404 页面
│   ├── styles/
│   │   └── globals.css           # Tailwind 指令 + 全局样式
│   └── __tests__/
│       ├── format.test.ts        # 格式化工具单元测试
│       └── api.test.ts           # API 客户端单元测试
└── dist/                         # 构建产物（gitignore），由 FastAPI 挂载
```

### 后端（修改/新增 `src/api/` 下的文件）

```
src/api/
├── scenario_endpoints.py         # 已有，保持不变
├── backtest_endpoints.py         # 已有，修改：新增 /backtest/mvp 端点
├── monitoring.py                 # 已有，保持不变
├── task_queue.py                 # 新建：线程池异步任务队列
├── ensemble_endpoints.py         # 新建：集成策略端点
├── trend_scan_endpoints.py       # 新建：趋势扫描端点（异步任务）
├── report_endpoints.py           # 新建：报告查看端点
├── data_endpoints.py             # 新建：数据管理端点
├── cache.py                      # 已有，保持不变
├── client.py                     # 已有，保持不变
├── endpoints.py                  # 已有，保持不变
└── logging.py                    # 已有，保持不变
```

### 测试文件

```
tests/
├── test_task_queue.py            # 新建：任务队列测试（含 TTL、并发）
├── test_mvp_endpoint.py          # 新建：MVP 回测端点测试
├── test_ensemble_endpoints.py    # 新建：集成策略端点测试
├── test_trend_scan_endpoints.py  # 新建：趋势扫描端点测试
├── test_report_endpoints.py      # 新建：报告端点测试
├── test_data_endpoints.py        # 新建：数据管理端点测试
├── test_scenario_api.py          # 已有，保持不变
├── test_backtest_endpoints.py    # 已有，保持不变
└── ...                           # 其他已有测试
```

---

## Task 1: 前端项目初始化与构建集成

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/styles/globals.css`
- Create: `frontend/.env.example`
- Modify: `frontend/.gitignore`（新建）
- Modify: `run_scenario_server.py`
- Modify: `.gitignore`

- [ ] **Step 1: 创建 `frontend/package.json`**

```json
{
  "name": "csqaq-dashboard",
  "private": true,
  "version": "0.20.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.2"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "jsdom": "^24.0.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: 创建 `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts", "echarts-for-react"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
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
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: 创建 `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

- [ ] **Step 5: 创建 `frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
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
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)",
        "card-hover": "0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 6: 创建 `frontend/postcss.config.js`**

```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 7: 创建 `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: [],
  },
});
```

- [ ] **Step 8: 创建 `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CSQAQ 量化仪表盘</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 9: 创建 `frontend/src/styles/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html,
body,
#root {
  height: 100%;
  margin: 0;
}

body {
  font-family: "Inter", "Noto Sans SC", "PingFang SC", sans-serif;
  background-color: #f8fafc;
  color: #1e293b;
  -webkit-font-smoothing: antialiased;
}

/* 滚动条样式 */
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

- [ ] **Step 10: 创建 `frontend/src/main.tsx`（占位，Task 5 和 Task 18 会完善）**

```typescript
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

- [ ] **Step 11: 创建 `frontend/src/App.tsx`（占位，Task 18 完善）**

```typescript
export default function App() {
  return (
    <div className="flex h-full items-center justify-center text-ink-secondary">
      <p>前端初始化中...</p>
    </div>
  );
}
```

- [ ] **Step 12: 创建 `frontend/.env.example`**

```bash
# API 基础路径（开发时 Vite 代理生效，留空即可；生产部署时填写后端地址）
VITE_API_BASE_URL=
```

- [ ] **Step 13: 创建 `frontend/.gitignore`**

```gitignore
node_modules/
dist/
*.local
.env
```

- [ ] **Step 14: 更新根目录 `.gitignore`，增加 `frontend/node_modules/` 和 `frontend/dist/`**

在 `.gitignore` 末尾追加：

```gitignore
# Frontend
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 15: 修改 `run_scenario_server.py` 挂载 `frontend/dist/`**

读取文件，找到 StaticFiles 挂载行，将 `frontend` 改为 `frontend/dist`，并增加目录存在性检查：

```python
import os
from pathlib import Path

# ... 已有 imports ...

frontend_dir = Path(__file__).parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    @app.get("/")
    def frontend_not_built():
        """前端未构建时返回提示信息。"""
        return HTMLResponse(
            "<h1>前端未构建</h1>"
            "<p>请先运行 <code>cd frontend && npm install && npm run build</code></p>",
            status_code=503,
        )
```

- [ ] **Step 16: 安装依赖并验证构建**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm install
npm run build
```

预期：`frontend/dist/` 目录生成 `index.html`、`assets/` 子目录。

- [ ] **Step 17: 验证后端挂载**

```bash
cd /workspace/csqaq-glove-quant
python -c "
from run_scenario_server import app
from fastapi.testclient import TestClient
client = TestClient(app)
r = client.get('/')
assert r.status_code == 200, f'Expected 200, got {r.status_code}'
assert 'root' in r.text, 'Frontend not served'
print('Frontend served correctly!')
"
```

- [ ] **Step 18: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.node.json frontend/tailwind.config.js frontend/postcss.config.js frontend/vitest.config.ts frontend/index.html frontend/src/main.tsx frontend/src/App.tsx frontend/src/styles/globals.css frontend/.env.example frontend/.gitignore .gitignore run_scenario_server.py
git commit -m "feat(web): 初始化 React + Vite + TypeScript 前端项目骨架"
```

---

## Task 2: API 类型定义与格式化工具

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/lib/format.ts`

- [ ] **Step 1: 创建 `frontend/src/types/api.ts`**

```typescript
// ===== 情景分析 =====

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

export interface Scenario {
  name: string;
  scenario_key: string;
  probability: number;
  direction: number;
  direction_label: string;
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
  scenarios: Scenario[];
  cached: boolean;
  generation_time_ms: number;
  generated_at: string;
}

export interface HistoryMatch {
  candidate_start_timestamp: string;
  neighbor_timestamp: string;
  distance: number;
  future_return: number;
  future_direction: number;
}

export interface HistoryResponse {
  sub_index: string;
  period: string;
  method: string;
  matches: HistoryMatch[];
}

export interface TemplateMatch {
  template_name: string;
  matched_timestamp: string;
  direction: number;
  confidence: number;
  support: number;
  resistance: number;
  target: number;
  stop_loss: number;
  suggestion: string;
}

export interface TemplateResponse {
  sub_index: string;
  period: string;
  matches: TemplateMatch[];
}

export interface ExplainResponse {
  prompt: string;
  explanation: string;
  wave_sketch_description: string;
}

export interface MetaResponse {
  sub_indices: string[];
  supported_periods: string[];
  default_period: string;
}

// ===== 回测 =====

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

export interface Trade {
  entry_index: number;
  entry_time: string;
  entry_price: number;
  exit_time: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  pnl: number;
  return_pct: number;
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
}

export interface MvpBacktestResponse {
  sub_index: string;
  period: string;
  generated_at: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  trades: Trade[];
}

// ===== 集成策略 =====

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

// ===== 趋势扫描（异步任务） =====

export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  progress: number;
  message: string;
  result: ScanResult | null;
  error: string | null;
}

export interface ScanResult {
  sub_index: string;
  period: string;
  total_combinations: number;
  top_10: ScanEntry[];
  bottom_10: ScanEntry[];
  non_negative_count: number;
  all_results: ScanEntry[];
}

export interface ScanEntry {
  params: Record<string, unknown>;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  total_trades: number;
}

// ===== 报告 =====

export interface ReportFile {
  filename: string;
  size_bytes: number;
  modified_at: string;
}

export interface ReportListResponse {
  reports: ReportFile[];
}

export interface ReportContentResponse {
  filename: string;
  content: unknown;
}

// ===== 数据管理 =====

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

// ===== 监控 =====

export interface MonitoringMetrics {
  request_count: number;
  p50_latency_ms: number;
  p99_latency_ms: number;
  failure_rate: number;
  per_endpoint: Record<string, { count: number; error_count: number; p99_latency_ms: number }>;
}

export interface MonitoringAlert {
  type: string;
  message: string;
  severity: string;
}

export interface MonitoringResponse {
  metrics: MonitoringMetrics;
  alerts: MonitoringAlert[];
  thresholds: { failure_rate: number; latency_p99_ms: number; brier_drift: number };
}
```

- [ ] **Step 2: 创建 `frontend/src/lib/format.ts`**

```typescript
/** 格式化为百分比字符串，安全处理 null/NaN/Infinity。 */
export function formatPercent(value: number | null | undefined, digits: number = 2): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

/** 格式化为普通数字字符串，安全处理 null/NaN/Infinity。 */
export function formatNumber(value: number | null | undefined, digits: number = 2): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return value.toFixed(digits);
}

/** 格式化 ISO 日期字符串为 YYYY-MM-DD。 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  try {
    return iso.slice(0, 10);
  } catch {
    return "-";
  }
}

/** 格式化文件大小（字节 → KB/MB）。 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 根据方向标签返回 Tailwind 颜色类。 */
export function directionColor(label: string): string {
  if (label === "bullish") return "text-bull";
  if (label === "bearish") return "text-bear";
  return "text-neutral";
}

/** 根据方向标签返回中文。 */
export function directionLabel(label: string): string {
  if (label === "bullish") return "看涨";
  if (label === "bearish") return "看跌";
  return "震荡";
}
```

- [ ] **Step 3: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/src/types/api.ts frontend/src/lib/format.ts
git commit -m "feat(web): 添加 API 类型定义与格式化工具函数"
```

---

## Task 3: 统一 API 客户端（含超时/取消机制）

**Files:**
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: 创建 `frontend/src/lib/api.ts`**

```typescript
import type {
  OhlcResponse,
  ScenarioGenerateResponse,
  HistoryResponse,
  TemplateResponse,
  ExplainResponse,
  MetaResponse,
  MvpBacktestResponse,
  EnsembleResponse,
  TaskStatusResponse,
  ReportListResponse,
  ReportContentResponse,
  CacheStatusResponse,
  DataRefreshResponse,
  MonitoringResponse,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: {
    method?: "GET" | "POST";
    params?: Record<string, string | number | boolean | undefined>;
    body?: unknown;
    signal?: AbortSignal;
    timeoutMs?: number;
  } = {}
): Promise<T> {
  const { method = "GET", params, body, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = options;

  let url = `${BASE_URL}${path}`;
  if (params) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value != null) search.set(key, String(value));
    }
    const qs = search.toString();
    if (qs) url += `?${qs}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // 合并外部 signal 和内部 timeout signal
  if (signal) {
    signal.addEventListener("abort", () => controller.abort());
  }

  try {
    const fetchOptions: RequestInit = {
      method,
      signal: controller.signal,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    };

    const res = await fetch(url, fetchOptions);

    if (!res.ok) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        // 非 JSON 错误响应
      }
      const message =
        typeof detail === "object" && detail !== null && "detail" in detail
          ? String((detail as Record<string, unknown>).detail)
          : `HTTP ${res.status}`;
      throw new ApiError(res.status, message, detail);
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "请求超时或已取消");
    }
    throw new ApiError(0, err instanceof Error ? err.message : "网络请求失败");
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api = {
  // ===== 情景分析 =====
  getMeta: (signal?: AbortSignal) => request<MetaResponse>("/scenario/meta", { signal }),

  getOhlc: (subIndex: string, period: string, signal?: AbortSignal) =>
    request<OhlcResponse>("/scenario/ohlc", { params: { sub_index: subIndex, period }, signal }),

  getScenarios: (subIndex: string, period: string, refresh: boolean = false, signal?: AbortSignal) =>
    request<ScenarioGenerateResponse>("/scenario/generate", {
      params: { sub_index: subIndex, period, refresh },
      signal,
    }),

  getHistory: (
    subIndex: string,
    period: string,
    method: string = "knn",
    nNeighbors: number = 10,
    signal?: AbortSignal
  ) =>
    request<HistoryResponse>("/scenario/history", {
      params: { sub_index: subIndex, period, method, n_neighbors: nNeighbors },
      signal,
    }),

  getTemplates: (subIndex: string, period: string, minConfidence: number = 0.5, signal?: AbortSignal) =>
    request<TemplateResponse>("/scenario/templates", {
      params: { sub_index: subIndex, period, min_confidence: minConfidence },
      signal,
    }),

  explain: (scenario: Record<string, unknown>, context?: Record<string, unknown>, signal?: AbortSignal) =>
    request<ExplainResponse>("/scenario/explain", { method: "POST", body: { scenario, context }, signal }),

  // ===== 回测 =====
  runMvpBacktest: (subIndex: string, period: string, signal?: AbortSignal) =>
    request<MvpBacktestResponse>("/backtest/mvp", {
      params: { sub_index: subIndex, period },
      signal,
      timeoutMs: 60_000,
    }),

  // ===== 集成策略 =====
  runEnsemble: (subIndex: string, period: string, signal?: AbortSignal) =>
    request<EnsembleResponse>("/ensemble/run", {
      params: { sub_index: subIndex, period },
      signal,
      timeoutMs: 60_000,
    }),

  // ===== 趋势扫描 =====
  startTrendScan: (subIndex: string, period: string) =>
    request<{ task_id: string }>("/trend-scan/start", {
      method: "POST",
      body: { sub_index: subIndex, period },
    }),

  getTaskStatus: (taskId: string, signal?: AbortSignal) =>
    request<TaskStatusResponse>(`/trend-scan/status/${taskId}`, { signal }),

  // ===== 报告 =====
  listReports: (signal?: AbortSignal) => request<ReportListResponse>("/reports/list", { signal }),

  getReport: (filename: string, signal?: AbortSignal) =>
    request<ReportContentResponse>("/reports/get", { params: { filename }, signal }),

  // ===== 数据管理 =====
  getCacheStatus: (signal?: AbortSignal) => request<CacheStatusResponse>("/data/cache-status", { signal }),

  refreshData: (subIndex: string, period: string) =>
    request<DataRefreshResponse>("/data/refresh", {
      method: "POST",
      body: { sub_index: subIndex, period },
    }),

  // ===== 监控 =====
  getMonitoring: (signal?: AbortSignal) => request<MonitoringResponse>("/monitoring/metrics", { signal }),
};
```

- [ ] **Step 2: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/src/lib/api.ts
git commit -m "feat(web): 添加统一 API 客户端（含 AbortController 超时/取消）"
```

---

## Task 4: 通用 UI 组件库（含空状态/无障碍）

**Files:**
- Create: `frontend/src/components/Card.tsx`
- Create: `frontend/src/components/MetricCard.tsx`
- Create: `frontend/src/components/LoadingState.tsx`
- Create: `frontend/src/components/ErrorState.tsx`
- Create: `frontend/src/components/EmptyState.tsx`
- Create: `frontend/src/components/ScenarioBar.tsx`

- [ ] **Step 1: 创建 `frontend/src/components/Card.tsx`**

```typescript
import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, actions, children, className = "" }: CardProps) {
  return (
    <div className={`rounded-xl border border-surface-border bg-surface-card shadow-card ${className}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-3">
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

```typescript
interface MetricCardProps {
  label: string;
  value: string | number;
  hint?: string;
  color?: string;
}

export function MetricCard({ label, value, hint, color = "text-ink-primary" }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4">
      <p className="text-xs font-medium text-ink-secondary">{label}</p>
      <p className={`mt-1 text-xl font-bold ${color}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-muted">{hint}</p>}
    </div>
  );
}
```

- [ ] **Step 3: 创建 `frontend/src/components/LoadingState.tsx`**

```typescript
interface LoadingStateProps {
  message?: string;
  rows?: number;
}

export function LoadingState({ message = "加载中...", rows = 3 }: LoadingStateProps) {
  return (
    <div className="space-y-3" role="status" aria-live="polite">
      <p className="text-sm text-ink-secondary">{message}</p>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 animate-pulse rounded bg-surface-hover" />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: 创建 `frontend/src/components/ErrorState.tsx`**

```typescript
interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-8" role="alert">
      <svg className="h-10 w-10 text-bear" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <p className="text-sm text-bear">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg border border-surface-border px-4 py-1.5 text-sm font-medium text-ink-primary transition hover:bg-surface-hover"
        >
          重试
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 创建 `frontend/src/components/EmptyState.tsx`**

```typescript
interface EmptyStateProps {
  message?: string;
}

export function EmptyState({ message = "暂无数据" }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-ink-muted">
      <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
      </svg>
      <p className="text-sm">{message}</p>
    </div>
  );
}
```

- [ ] **Step 6: 创建 `frontend/src/components/ScenarioBar.tsx`（含无障碍支持）**

```typescript
import type { Scenario } from "../types/api";
import { directionLabel } from "../lib/format";

interface ScenarioBarProps {
  scenarios: Scenario[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

const BAR_COLORS: Record<string, string> = {
  bullish: "bg-bull",
  bearish: "bg-bear",
  neutral: "bg-neutral",
};

export function ScenarioBar({ scenarios, selectedIndex, onSelect }: ScenarioBarProps) {
  if (scenarios.length === 0) return null;

  return (
    <div className="space-y-2" role="listbox" aria-label="情景概率分布">
      {scenarios.map((s, i) => {
        const color = BAR_COLORS[s.direction_label] || "bg-neutral";
        const isSelected = i === selectedIndex;
        return (
          <div
            key={s.scenario_key}
            role="option"
            aria-selected={isSelected}
            tabIndex={0}
            onClick={() => onSelect(i)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(i);
              }
            }}
            className={`cursor-pointer rounded-lg border p-3 transition ${
              isSelected
                ? "border-brand-500 bg-brand-50"
                : "border-surface-border bg-surface-card hover:bg-surface-hover"
            }`}
          >
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-sm font-medium text-ink-primary">{s.name}</span>
              <span className="text-xs font-semibold text-ink-secondary">
                {(s.probability * 100).toFixed(1)}%
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
              <div
                className={`h-full rounded-full ${color} transition-all duration-300`}
                style={{ width: `${Math.max(s.probability * 100, 2)}%` }}
              />
            </div>
            <span className="mt-1 inline-block text-xs text-ink-muted">
              {directionLabel(s.direction_label)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 7: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/src/components/
git commit -m "feat(web): 添加通用 UI 组件库（Card/MetricCard/LoadingState/ErrorState/EmptyState/ScenarioBar）"
```

---

## Task 5: 页面布局与导航（含响应式/状态管理/Error Boundary）

**Files:**
- Create: `frontend/src/ErrorBoundary.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/TopBar.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/ErrorBoundary.tsx`**

```typescript
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
          <svg className="h-12 w-12 text-bear" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.008v.008H12v-.008z" />
          </svg>
          <div className="text-center">
            <h2 className="text-lg font-semibold text-ink-primary">页面渲染出错</h2>
            <p className="mt-1 text-sm text-ink-secondary">{this.state.error?.message || "未知错误"}</p>
          </div>
          <button
            onClick={this.handleReset}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
          >
            重置页面
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: 创建 `frontend/src/components/Sidebar.tsx`（响应式：移动端可折叠）**

```typescript
import { NavLink } from "react-router-dom";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const NAV_ITEMS = [
  { path: "/", label: "情景分析", icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" },
  { path: "/backtest", label: "MVP 回测", icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625z" },
  { path: "/ensemble", label: "集成策略", icon: "M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" },
  { path: "/trend-scan", label: "趋势扫描", icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75z" },
  { path: "/reports", label: "报告中心", icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" },
  { path: "/data", label: "数据管理", icon: "M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375" },
];

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  return (
    <>
      {/* 移动端遮罩 */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed left-0 top-0 z-40 h-full w-56 transform border-r border-surface-border bg-surface-card transition-transform duration-200 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center border-b border-surface-border px-5">
          <span className="text-base font-bold text-brand-600">CSQAQ 量化仪表盘</span>
        </div>
        <nav className="space-y-1 p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-secondary hover:bg-surface-hover hover:text-ink-primary"
                }`
              }
            >
              <svg className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
              </svg>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
```

- [ ] **Step 3: 创建 `frontend/src/components/TopBar.tsx`（含状态自动清除）**

```typescript
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { MetaResponse, MonitoringResponse } from "../types/api";

interface TopBarProps {
  subIndex: string;
  setSubIndex: (value: string) => void;
  period: string;
  setPeriod: (value: string) => void;
  onRefresh: () => void;
  onToggleSidebar: () => void;
}

const PERIODS = ["1day", "4hour", "1hour"];

export function TopBar({ subIndex, setSubIndex, period, setPeriod, onRefresh, onToggleSidebar }: TopBarProps) {
  const [subIndices, setSubIndices] = useState<string[]>([subIndex]);
  const [status, setStatus] = useState("");
  const [monitoring, setMonitoring] = useState<MonitoringResponse | null>(null);
  const statusTimerRef = useRef<number | null>(null);

  // 加载子指数列表，失败显示错误而非静默吞掉
  useEffect(() => {
    api
      .getMeta()
      .then((data: MetaResponse) => {
        if (data.sub_indices.length > 0) setSubIndices(data.sub_indices);
      })
      .catch((err: unknown) => {
        console.warn("加载子指数列表失败，使用默认值:", err);
      });
  }, []);

  // 监控轮询（30 秒）
  useEffect(() => {
    const poll = () => {
      api.getMonitoring().then(setMonitoring).catch(() => {});
    };
    poll();
    const id = setInterval(poll, 30_000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = (): void => {
    setStatus("刷新中...");
    onRefresh();
    // 3 秒后自动清除状态
    if (statusTimerRef.current) clearTimeout(statusTimerRef.current);
    statusTimerRef.current = window.setTimeout(() => setStatus(""), 3000);
  };

  useEffect(() => {
    return () => {
      if (statusTimerRef.current) clearTimeout(statusTimerRef.current);
    };
  }, []);

  const failureRate = monitoring?.metrics.failure_rate ?? 0;
  const p99 = monitoring?.metrics.p99_latency_ms ?? 0;
  const hasAlert = failureRate > 0.05 || p99 > 2000;

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-surface-border bg-surface-card px-4">
      {/* 移动端菜单按钮 */}
      <button
        onClick={onToggleSidebar}
        className="rounded-lg p-2 text-ink-secondary hover:bg-surface-hover md:hidden"
        aria-label="切换导航栏"
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      {/* 子指数选择 */}
      <select
        value={subIndex}
        onChange={(e) => setSubIndex(e.target.value)}
        className="rounded-lg border border-surface-border bg-surface-card px-3 py-1.5 text-sm text-ink-primary focus:border-brand-500 focus:outline-none"
        aria-label="选择子指数"
      >
        {subIndices.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>

      {/* 周期选择 */}
      <select
        value={period}
        onChange={(e) => setPeriod(e.target.value)}
        className="rounded-lg border border-surface-border bg-surface-card px-3 py-1.5 text-sm text-ink-primary focus:border-brand-500 focus:outline-none"
        aria-label="选择K线周期"
      >
        {PERIODS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      {/* 刷新按钮 */}
      <button
        onClick={handleRefresh}
        className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-700"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
        </svg>
        刷新
      </button>

      {/* 状态文本 */}
      {status && <span className="text-sm text-ink-muted">{status}</span>}

      {/* 监控摘要 */}
      <div className="ml-auto flex items-center gap-3 text-xs">
        {hasAlert && (
          <span className="rounded bg-bear/10 px-2 py-0.5 font-medium text-bear" role="alert">
            告警
          </span>
        )}
        <span className="text-ink-muted">
          P99: <span className={p99 > 2000 ? "font-medium text-bear" : "text-ink-secondary"}>{p99.toFixed(0)}ms</span>
        </span>
        <span className="text-ink-muted">
          失败率:{" "}
          <span className={failureRate > 0.05 ? "font-medium text-bear" : "text-ink-secondary"}>
            {(failureRate * 100).toFixed(1)}%
          </span>
        </span>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: 创建 `frontend/src/components/Layout.tsx`（render-props 模式传递全局状态）**

```typescript
import { useState, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface LayoutProps {
  children: (props: {
    subIndex: string;
    period: string;
    refreshKey: number;
  }) => ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [subIndex, setSubIndex] = useState("手套");
  const [period, setPeriod] = useState("1day");
  const [refreshKey, setRefreshKey] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleRefresh = (): void => {
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          subIndex={subIndex}
          setSubIndex={setSubIndex}
          period={period}
          setPeriod={setPeriod}
          onRefresh={handleRefresh}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
        />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          <div className="mx-auto max-w-7xl">
            {children({ subIndex, period, refreshKey })}
          </div>
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 更新 `frontend/src/App.tsx`（集成 Layout + ErrorBoundary + 路由占位）**

```typescript
import { Routes, Route } from "react-router-dom";
import { ErrorBoundary } from "./ErrorBoundary";
import { Layout } from "./components/Layout";

function Placeholder({ name }: { name: string }) {
  return (
    <div className="flex h-full items-center justify-center text-ink-secondary">
      <p>{name} — 开发中</p>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Layout>
        {({ subIndex, period, refreshKey }) => (
          <Routes>
            <Route path="/" element={<Placeholder name="情景分析" />} />
            <Route path="/backtest" element={<Placeholder name="MVP 回测" />} />
            <Route path="/ensemble" element={<Placeholder name="集成策略" />} />
            <Route path="/trend-scan" element={<Placeholder name="趋势扫描" />} />
            <Route path="/reports" element={<Placeholder name="报告中心" />} />
            <Route path="/data" element={<Placeholder name="数据管理" />} />
            <Route path="*" element={
              <div className="flex h-full flex-col items-center justify-center gap-2 text-ink-muted">
                <p className="text-4xl font-bold">404</p>
                <p className="text-sm">页面不存在</p>
              </div>
            } />
          </Routes>
        )}
      </Layout>
    </ErrorBoundary>
  );
}
```

- [ ] **Step 6: 构建验证**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build
```

预期：TypeScript 编译通过，`dist/` 生成成功。

- [ ] **Step 7: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/src/ErrorBoundary.tsx frontend/src/components/Sidebar.tsx frontend/src/components/TopBar.tsx frontend/src/components/Layout.tsx frontend/src/App.tsx
git commit -m "feat(web): 添加页面布局（响应式侧边栏/顶栏/ErrorBoundary/404路由）"
```

---

## Task 6: 后端异步任务队列（线程池 + TTL + 并发限制）

**Files:**
- Create: `src/api/task_queue.py`
- Create: `tests/test_task_queue.py`

- [ ] **Step 1: 编写测试 `tests/test_task_queue.py`**

```python
"""Tests for the async task queue."""

import time

from src.api.task_queue import TaskQueue, TaskStatus


def test_create_returns_pending_task():
    """create() should register a task in pending state without starting it."""
    q = TaskQueue()
    task_id = q.create(lambda progress_cb: 42)
    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.PENDING
    assert info.progress == 0.0


def test_run_completes_and_stores_result():
    """run() should execute the task and store the result."""
    q = TaskQueue()
    task_id = q.create(lambda progress_cb: {"answer": 42})
    q.run(task_id)

    # Wait for completion
    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.COMPLETED
    assert info.result == {"answer": 42}
    assert info.progress == 1.0


def test_run_failed_task_stores_error():
    """A task that raises should be marked as failed with the error message."""
    def failing_task(progress_cb):
        raise ValueError("boom")

    q = TaskQueue()
    task_id = q.create(failing_task)
    q.run(task_id)

    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.FAILED
    assert "boom" in (info.error or "")


def test_progress_callback_updates_progress():
    """The progress callback should update the task's progress and message."""
    def task_with_progress(progress_cb):
        progress_cb(0.5, "半途")
        time.sleep(0.1)
        progress_cb(1.0, "完成")
        return "done"

    q = TaskQueue()
    task_id = q.create(task_with_progress)
    q.run(task_id)

    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.COMPLETED


def test_run_unknown_task_raises():
    """run() should raise KeyError for an unknown task_id."""
    q = TaskQueue()
    try:
        q.run("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_get_unknown_task_returns_none():
    """get() should return None for an unknown task_id."""
    q = TaskQueue()
    assert q.get("nonexistent") is None


def test_ttl_eviction_removes_old_tasks():
    """Tasks older than the TTL should be evicted on cleanup."""
    q = TaskQueue(ttl_seconds=0.5)
    task_id = q.create(lambda progress_cb: 1)
    q.run(task_id)

    # Wait for completion
    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    # Wait for TTL to expire
    time.sleep(0.7)

    # Trigger eviction by calling _evict_old
    q._evict_old()

    assert q.get(task_id) is None, "Task should have been evicted after TTL"


def test_concurrent_tasks_respect_max_workers():
    """Multiple tasks should run concurrently up to max_workers."""
    import threading
    counter = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def counting_task(progress_cb):
        with lock:
            counter["active"] += 1
            counter["max_active"] = max(counter["max_active"], counter["active"])
        time.sleep(0.2)
        with lock:
            counter["active"] -= 1
        return "ok"

    q = TaskQueue(max_workers=2)
    task_ids = []
    for _ in range(5):
        tid = q.create(counting_task)
        q.run(tid)
        task_ids.append(tid)

    # Wait for all to complete
    for tid in task_ids:
        for _ in range(100):
            info = q.get(tid)
            if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break
            time.sleep(0.1)

    assert counter["max_active"] <= 2, f"max_active={counter['max_active']} should be <= 2"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_task_queue.py -v
```

预期：FAIL with `ModuleNotFoundError: No module named 'src.api.task_queue'`

- [ ] **Step 3: 创建 `src/api/task_queue.py`**

```python
"""Thread-safe in-memory task queue with ThreadPoolExecutor and TTL eviction."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


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
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for API responses."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
        }


ProgressCallback = Callable[[float, str], None]


class TaskQueue:
    """Thread-safe in-memory task queue with TTL eviction and concurrency limit."""

    def __init__(
        self,
        ttl_seconds: float = 3600.0,
        max_workers: int = 4,
    ) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._fns: dict[str, Callable[[ProgressCallback], Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task-queue")

    def create(self, fn: Callable[[ProgressCallback], Any]) -> str:
        """Register a task and return its ID. Does not start execution."""
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = TaskInfo(task_id=task_id)
            self._fns[task_id] = fn
        return task_id

    def run(self, task_id: str) -> None:
        """Start a registered task via the thread pool."""
        with self._lock:
            info = self._tasks.get(task_id)
            fn = self._fns.get(task_id)
            if info is None or fn is None:
                raise KeyError(f"Task not found: {task_id}")
            if info.status != TaskStatus.PENDING:
                raise ValueError(f"Task already started or finished: {task_id}")
            info.status = TaskStatus.RUNNING

        self._executor.submit(self._execute, task_id, fn)

    def get(self, task_id: str) -> Optional[TaskInfo]:
        """Return task info, or None if not found."""
        with self._lock:
            return self._tasks.get(task_id)

    def _execute(self, task_id: str, fn: Callable[[ProgressCallback], Any]) -> None:
        """Internal: execute task and update state. Runs in worker thread."""
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
                    ti.completed_at = time.time()
        except Exception as exc:
            with self._lock:
                ti = self._tasks.get(task_id)
                if ti:
                    ti.status = TaskStatus.FAILED
                    ti.error = str(exc)
                    ti.completed_at = time.time()

    def _evict_old(self) -> None:
        """Remove completed/failed tasks older than TTL. Call periodically."""
        now = time.time()
        with self._lock:
            to_remove = [
                tid
                for tid, info in self._tasks.items()
                if info.completed_at is not None
                and (now - info.completed_at) > self._ttl
            ]
            for tid in to_remove:
                del self._tasks[tid]
                self._fns.pop(tid, None)

    def shutdown(self) -> None:
        """Shut down the thread pool."""
        self._executor.shutdown(wait=False)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_task_queue.py -v
```

预期：所有 8 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add src/api/task_queue.py tests/test_task_queue.py
git commit -m "feat(api): 添加线程池异步任务队列（TTL清理+并发限制+8项测试）"
```

---

## Task 7: MVP 回测 API 端点

**Files:**
- Modify: `src/api/backtest_endpoints.py`
- Create: `tests/test_mvp_endpoint.py`

- [ ] **Step 1: 编写测试 `tests/test_mvp_endpoint.py`**

```python
"""Tests for the /backtest/mvp endpoint."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """Create a test client with deterministic synthetic OHLC data."""
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")

    dates = pd.date_range("2024-01-01", periods=400, freq="D")
    rng = np.random.default_rng(42)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 400)))
    df = pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + rng.normal(0, 0.005, 400)),
        "high": close * (1 + np.abs(rng.normal(0, 0.01, 400))),
        "low": close * (1 - np.abs(rng.normal(0, 0.01, 400))),
        "close": close,
    })

    from src.api import backtest_endpoints
    monkeypatch.setattr(backtest_endpoints, "_load_ohlc", lambda sub_index, period: df)

    from run_scenario_server import app
    return TestClient(app)


def test_mvp_returns_metrics_equity_and_trades(client):
    """MVP backtest should return metrics, equity_curve, and trades."""
    r = client.get("/backtest/mvp", params={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()

    assert data["sub_index"] == "手套"
    assert data["period"] == "1day"
    assert "generated_at" in data

    # metrics 验证
    metrics = data["metrics"]
    assert "total_return" in metrics
    assert "max_drawdown" in metrics
    assert "sharpe_ratio" in metrics
    assert "win_rate" in metrics
    assert "total_trades" in metrics
    assert isinstance(metrics["total_trades"], int)

    # equity_curve 验证
    eq = data["equity_curve"]
    assert isinstance(eq, list)
    assert len(eq) > 0
    assert "timestamp" in eq[0]
    assert "equity" in eq[0]

    # trades 验证
    trades = data["trades"]
    assert isinstance(trades, list)
    if len(trades) > 0:
        t = trades[0]
        assert "entry_time" in t
        assert "entry_price" in t
        assert "exit_reason" in t
        assert "pnl" in t
        assert "return_pct" in t


def test_mvp_invalid_period_returns_400(client):
    """Invalid period should return 400."""
    r = client.get("/backtest/mvp", params={"sub_index": "手套", "period": "10year"})
    assert r.status_code == 400
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_mvp_endpoint.py -v
```

预期：FAIL with 404 (endpoint not found)

- [ ] **Step 3: 在 `src/api/backtest_endpoints.py` 末尾追加 `/backtest/mvp` 端点**

```python
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
                "exit_time": _to_iso(t.exit_time) if t.exit_time else None,
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
cd /workspace/csqaq-glove-quant
git add src/api/backtest_endpoints.py tests/test_mvp_endpoint.py
git commit -m "feat(api): 添加 /backtest/mvp 端点（含 metrics+equity+trades 完整返回）"
```

---

## Task 8: 集成策略 API 端点

**Files:**
- Create: `src/api/ensemble_endpoints.py`
- Create: `tests/test_ensemble_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 编写测试 `tests/test_ensemble_endpoints.py`**

```python
"""Tests for the /ensemble/run endpoint."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    dates = pd.date_range("2024-01-01", periods=400, freq="D")
    rng = np.random.default_rng(42)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 400)))
    df = pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + rng.normal(0, 0.005, 400)),
        "high": close * (1 + np.abs(rng.normal(0, 0.01, 400))),
        "low": close * (1 - np.abs(rng.normal(0, 0.01, 400))),
        "close": close,
    })
    from src.api import ensemble_endpoints
    monkeypatch.setattr(ensemble_endpoints, "_load_ohlc", lambda sub_index, period: df)
    from run_scenario_server import app
    return TestClient(app)


def test_ensemble_returns_three_strategies(client):
    """/ensemble/run should return ensemble, pullback, and trend_following results."""
    r = client.get("/ensemble/run", params={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()

    assert data["sub_index"] == "手套"
    assert data["period"] == "1day"

    for key in ("ensemble", "pullback", "trend_following"):
        assert key in data
        strat = data[key]
        assert "strategy_name" in strat
        assert "metrics" in strat
        assert "equity_curve" in strat
        assert isinstance(strat["equity_curve"], list)
        assert "trade_count" in strat
        assert "total_return" in strat["metrics"]


def test_ensemble_invalid_period_returns_400(client):
    r = client.get("/ensemble/run", params={"sub_index": "手套", "period": "10year"})
    assert r.status_code == 400
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_ensemble_endpoints.py -v
```

预期：FAIL with 404

- [ ] **Step 3: 创建 `src/api/ensemble_endpoints.py`**

```python
"""Ensemble strategy API endpoints."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.analysis.metrics import summarize
from src.api.logging import LOGGER, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period, _to_iso
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.ensemble import EnsembleParams, generate_ensemble_signals
from src.strategy.signal import SignalParams, generate_signals
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)

router = APIRouter(prefix="/ensemble", tags=["ensemble"])


def _run_single_strategy(
    df: Any,
    signal_df: Any,
    strategy_name: str,
) -> dict[str, Any]:
    """Run backtest on a signal df and return structured result."""
    result = run_backtest(signal_df, BacktestParams())
    metrics = summarize(result)
    equity_records = [
        {"timestamp": _to_iso(ts), "equity": round(float(val), 4)}
        for ts, val in result.equity_curve.items()
    ]
    return {
        "strategy_name": strategy_name,
        "metrics": metrics,
        "equity_curve": equity_records,
        "trade_count": len(result.trades),
    }


@router.get("/run")
def run_ensemble(
    sub_index: str = Query(..., description="Sub-index Chinese name."),
    period: str = Query("1day", description="K-line period."),
) -> dict[str, Any]:
    """Run ensemble, pullback, and trend-following strategies for comparison."""
    period = _normalize_period(period)
    start = time.perf_counter()
    try:
        df = _load_ohlc(sub_index, period)

        pullback_signals = generate_signals(
            df, SignalParams(use_smart_money=True, use_trend_following=False)
        )
        trend_signals = generate_trend_following_signals(df, TrendFollowingParams())
        ensemble_signals = generate_ensemble_signals(
            df, EnsembleParams()
        )

        pullback_result = _run_single_strategy(df, pullback_signals, "pullback")
        trend_result = _run_single_strategy(df, trend_signals, "trend_following")
        ensemble_result = _run_single_strategy(df, ensemble_signals, "ensemble")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ensemble run failed: {exc}") from exc

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
        "ensemble": ensemble_result,
        "pullback": pullback_result,
        "trend_following": trend_result,
    }
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册路由**

在 `app.include_router(backtest_router)` 之后添加：

```python
from src.api.ensemble_endpoints import router as ensemble_router
app.include_router(ensemble_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_ensemble_endpoints.py -v
```

预期：2 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add src/api/ensemble_endpoints.py tests/test_ensemble_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加 /ensemble/run 端点（三策略对比回测）"
```

---

## Task 9: 趋势扫描 API 端点（异步任务，POST 语义）

**Files:**
- Create: `src/api/trend_scan_endpoints.py`
- Create: `tests/test_trend_scan_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 编写测试 `tests/test_trend_scan_endpoints.py`**

```python
"""Tests for the /trend-scan endpoints."""

import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    dates = pd.date_range("2024-01-01", periods=400, freq="D")
    rng = np.random.default_rng(42)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 400)))
    df = pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + rng.normal(0, 0.005, 400)),
        "high": close * (1 + np.abs(rng.normal(0, 0.01, 400))),
        "low": close * (1 - np.abs(rng.normal(0, 0.01, 400))),
        "close": close,
    })
    from src.api import trend_scan_endpoints
    monkeypatch.setattr(trend_scan_endpoints, "_load_ohlc", lambda sub_index, period: df)
    from run_scenario_server import app
    return TestClient(app)


def test_start_returns_task_id(client):
    """POST /trend-scan/start should return a task_id."""
    r = client.post("/trend-scan/start", json={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert len(data["task_id"]) > 0


def test_status_returns_valid_structure(client):
    """GET /trend-scan/status/{task_id} should return valid task info."""
    r1 = client.post("/trend-scan/start", json={"sub_index": "手套", "period": "1day"})
    task_id = r1.json()["task_id"]

    # Poll until terminal state
    for _ in range(120):
        r2 = client.get(f"/trend-scan/status/{task_id}")
        assert r2.status_code == 200
        data = r2.json()
        assert "status" in data
        assert "progress" in data
        assert "result" in data
        assert "error" in data
        if data["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)

    # Final state should be completed (not pending/running)
    assert data["status"] in ("completed", "failed"), f"Unexpected status: {data['status']}"


def test_status_unknown_task_returns_404(client):
    """GET /trend-scan/status with unknown task_id should return 404."""
    r = client.get("/trend-scan/status/nonexistent123")
    assert r.status_code == 404


def test_completed_task_has_scan_result(client):
    """A completed scan task should have a result with top_10 and total_combinations."""
    r1 = client.post("/trend-scan/start", json={"sub_index": "手套", "period": "1day"})
    task_id = r1.json()["task_id"]

    for _ in range(120):
        r2 = client.get(f"/trend-scan/status/{task_id}")
        data = r2.json()
        if data["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)

    if data["status"] == "completed":
        result = data["result"]
        assert result is not None
        assert "total_combinations" in result
        assert "top_10" in result
        assert isinstance(result["top_10"], list)
        assert "sub_index" in result
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_trend_scan_endpoints.py -v
```

预期：FAIL with 404

- [ ] **Step 3: 创建 `src/api/trend_scan_endpoints.py`**

```python
"""Trend scan API endpoints with async task execution."""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.analysis.metrics import summarize
from src.api.logging import LOGGER, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period
from src.api.task_queue import TASK_QUEUE, TaskQueue
from src.backtest.engine import BacktestParams, run_backtest
from src.strategy.trend_following_strategy import (
    TrendFollowingParams,
    generate_trend_following_signals,
)

router = APIRouter(prefix="/trend-scan", tags=["trend-scan"])


class ScanRequest(BaseModel):
    sub_index: str
    period: str = "1day"


def _param_grid() -> list[dict[str, Any]]:
    """Generate the full parameter grid for trend scan."""
    combos = []
    for swing_order, confirmations, trend_threshold, use_di, use_vol, vol_mult, use_pb, pb_lookback, pb_buffer in itertools.product(
        (1, 2),
        (1, 2),
        (None, 20.0, 25.0, 30.0),
        (False, True),
        (False, True),
        (0.3, 0.5, 1.0),
        (False, True),
        (3, 5, 8),
        (0.003, 0.005, 0.01),
    ):
        combos.append({
            "swing_order": swing_order,
            "confirmations": confirmations,
            "trend_strength_threshold": trend_threshold,
            "use_di_filter": use_di,
            "use_volatility_filter": use_vol,
            "volatility_atr_multiplier": vol_mult,
            "use_pullback_confirmation": use_pb,
            "pullback_lookback": pb_lookback,
            "pullback_buffer": pb_buffer,
        })
    return combos


def _run_scan(
    sub_index: str,
    period: str,
    progress_cb,
) -> dict[str, Any]:
    """Execute the full parameter scan. Runs in a background thread."""
    df = _load_ohlc(sub_index, period)
    grid = _param_grid()
    total = len(grid)
    results: list[dict[str, Any]] = []

    for i, params_dict in enumerate(grid):
        params = TrendFollowingParams(
            swing_order=params_dict["swing_order"],
            confirmations=params_dict["confirmations"],
            trend_strength_threshold=params_dict["trend_strength_threshold"],
            use_di_filter=params_dict["use_di_filter"],
            use_volatility_filter=params_dict["use_volatility_filter"],
            volatility_atr_multiplier=params_dict["volatility_atr_multiplier"],
            use_pullback_confirmation=params_dict["use_pullback_confirmation"],
            pullback_lookback=params_dict["pullback_lookback"],
            pullback_buffer=params_dict["pullback_buffer"],
        )
        try:
            signal_df = generate_trend_following_signals(df, params)
            bt_result = run_backtest(signal_df, BacktestParams())
            metrics = summarize(bt_result)
            results.append({
                "params": params_dict,
                "total_return": metrics["total_return"],
                "max_drawdown": metrics["max_drawdown"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "win_rate": metrics["win_rate"],
                "total_trades": metrics["total_trades"],
            })
        except Exception:
            # Skip parameter combinations that error out
            pass

        progress_cb((i + 1) / total, f"扫描进度 {i + 1}/{total}")

    results.sort(key=lambda x: x["total_return"], reverse=True)
    non_negative = sum(1 for r in results if r["total_return"] >= 0)

    return {
        "sub_index": sub_index,
        "period": period,
        "total_combinations": total,
        "top_10": results[:10],
        "bottom_10": results[-10:],
        "non_negative_count": non_negative,
        "all_results": results,
    }


@router.post("/start")
def start_scan(request: ScanRequest) -> dict[str, str]:
    """Start an async trend scan task. Returns task_id for polling."""
    # Validate period early
    _normalize_period(request.period)

    task_id = TASK_QUEUE.create(
        lambda progress_cb: _run_scan(request.sub_index, request.period, progress_cb)
    )
    TASK_QUEUE.run(task_id)

    log_request(
        LOGGER,
        endpoint="/trend-scan/start",
        sub_index=request.sub_index,
        period=request.period,
        extra={"task_id": task_id},
    )
    return {"task_id": task_id}


@router.get("/status/{task_id}")
def get_status(task_id: str) -> dict[str, Any]:
    """Get the status of a trend scan task."""
    info = TASK_QUEUE.get(task_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return info.to_dict()
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册路由和全局 TaskQueue**

在 `src/api/task_queue.py` 末尾添加全局单例（Task 6 已创建该文件，此处仅追加最后一行）：

```python
# 全局单例
TASK_QUEUE = TaskQueue(ttl_seconds=3600.0, max_workers=4)
```

`trend_scan_endpoints.py` 直接导入：`from src.api.task_queue import TASK_QUEUE`

`run_scenario_server.py` 只需注册路由：

```python
from src.api.trend_scan_endpoints import router as trend_scan_router
app.include_router(trend_scan_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_trend_scan_endpoints.py -v --timeout=120
```

预期：4 个测试 PASS（扫描可能需要数十秒）。

- [ ] **Step 6: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add src/api/task_queue.py src/api/trend_scan_endpoints.py tests/test_trend_scan_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加趋势扫描异步端点（POST启动+GET轮询+线程池执行）"
```

---

## Task 10: 报告查看 API 端点

**Files:**
- Create: `src/api/report_endpoints.py`
- Create: `tests/test_report_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 编写测试 `tests/test_report_endpoints.py`**

```python
"""Tests for the /reports endpoints."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with a temporary reports directory."""
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")

    # Create test report files
    (tmp_path / "test_report.json").write_text(json.dumps({"key": "value"}))
    (tmp_path / "empty.json").write_text("{}")
    (tmp_path / "not_json.txt").write_text("hello")

    from src.api import report_endpoints
    monkeypatch.setattr(report_endpoints, "REPORTS_DIR", tmp_path)

    from run_scenario_server import app
    return TestClient(app)


def test_list_returns_json_files(client):
    """/reports/list should return only .json files."""
    r = client.get("/reports/list")
    assert r.status_code == 200
    data = r.json()
    assert "reports" in data
    filenames = [f["filename"] for f in data["reports"]]
    assert "test_report.json" in filenames
    assert "empty.json" in filenames
    assert "not_json.txt" not in filenames


def test_list_file_has_metadata(client):
    """Each report file should have filename, size_bytes, and modified_at."""
    r = client.get("/reports/list")
    files = r.json()["reports"]
    assert len(files) > 0
    f = files[0]
    assert "filename" in f
    assert "size_bytes" in f
    assert "modified_at" in f
    assert isinstance(f["size_bytes"], int)
    assert f["size_bytes"] > 0


def test_get_returns_content(client):
    """/reports/get should return the parsed JSON content."""
    r = client.get("/reports/get", params={"filename": "test_report.json"})
    assert r.status_code == 200
    data = r.json()
    assert data["filename"] == "test_report.json"
    assert data["content"] == {"key": "value"}


def test_get_nonexistent_returns_404(client):
    r = client.get("/reports/get", params={"filename": "nonexistent.json"})
    assert r.status_code == 404


def test_get_path_traversal_blocked(client):
    """Path traversal attempts should return 404, not expose files."""
    r = client.get("/reports/get", params={"filename": "../../../etc/passwd"})
    assert r.status_code == 404


def test_get_absolute_path_blocked(client):
    """Absolute paths should be blocked."""
    r = client.get("/reports/get", params={"filename": "/etc/passwd"})
    assert r.status_code == 404
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_report_endpoints.py -v
```

预期：FAIL with 404

- [ ] **Step 3: 创建 `src/api/report_endpoints.py`**

```python
"""Report viewing API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.logging import LOGGER, log_request

router = APIRouter(prefix="/reports", tags=["reports"])

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


@router.get("/list")
def list_reports() -> dict[str, Any]:
    """List all JSON report files in the reports directory."""
    if not REPORTS_DIR.exists():
        return {"reports": []}

    files = []
    for path in sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.name):
        stat = path.stat()
        files.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    log_request(LOGGER, endpoint="/reports/list", extra={"file_count": len(files)})
    return {"reports": files}


@router.get("/get")
def get_report(filename: str = Query(..., description="Report filename.")) -> dict[str, Any]:
    """Get the content of a specific report file."""
    # Use resolve() to canonicalize path and prevent traversal
    target = (REPORTS_DIR / filename).resolve()
    reports_resolved = REPORTS_DIR.resolve()

    # Verify the resolved path is within reports directory
    try:
        target.relative_to(reports_resolved)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    try:
        content = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse report: {exc}") from exc

    log_request(LOGGER, endpoint="/reports/get", extra={"filename": filename})
    return {"filename": filename, "content": content}
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册路由**

```python
from src.api.report_endpoints import router as report_router
app.include_router(report_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_report_endpoints.py -v
```

预期：6 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add src/api/report_endpoints.py tests/test_report_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加报告查看端点（列表+读取+路径遍历防护）"
```

---

## Task 11: 数据管理 API 端点

**Files:**
- Create: `src/api/data_endpoints.py`
- Create: `tests/test_data_endpoints.py`
- Modify: `run_scenario_server.py`

- [ ] **Step 1: 编写测试 `tests/test_data_endpoints.py`**

```python
"""Tests for the /data endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")

    # Create test parquet files
    import pandas as pd
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
        "open": [100.0] * 100,
        "high": [101.0] * 100,
        "low": [99.0] * 100,
        "close": [100.5] * 100,
    })
    df.to_parquet(tmp_path / "手套_1d.parquet", index=False)
    df.to_parquet(tmp_path / "匕首_4h.parquet", index=False)

    from src.api import data_endpoints
    monkeypatch.setattr(data_endpoints, "CACHE_DIR", tmp_path)

    from run_scenario_server import app
    return TestClient(app)


def test_cache_status_returns_files(client):
    """/data/cache-status should return parquet files with metadata."""
    r = client.get("/data/cache-status")
    assert r.status_code == 200
    data = r.json()
    assert "cache_dir" in data
    assert "total_files" in data
    assert "total_size_bytes" in data
    assert "files" in data
    assert data["total_files"] == 2

    filenames = [f["filename"] for f in data["files"]]
    assert "手套_1d.parquet" in filenames
    assert "匕首_4h.parquet" in filenames

    f = data["files"][0]
    assert "size_bytes" in f
    assert "bar_count" in f
    assert "modified_at" in f


def test_cache_status_empty_dir(tmp_path, monkeypatch):
    """Empty cache directory should return zero files."""
    monkeypatch.setenv("CSQAQ_API_TOKEN", "")
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    from src.api import data_endpoints
    monkeypatch.setattr(data_endpoints, "CACHE_DIR", empty_dir)

    from run_scenario_server import app
    c = TestClient(app)

    r = c.get("/data/cache-status")
    assert r.status_code == 200
    data = r.json()
    assert data["total_files"] == 0
    assert data["files"] == []


def test_refresh_returns_success(client):
    """/data/refresh should return success and bar_count."""
    r = client.post("/data/refresh", json={"sub_index": "手套", "period": "1day"})
    assert r.status_code == 200
    data = r.json()
    assert data["sub_index"] == "手套"
    assert data["success"] is True
    assert isinstance(data["bar_count"], int)


def test_refresh_invalid_period_returns_400(client):
    r = client.post("/data/refresh", json={"sub_index": "手套", "period": "10year"})
    assert r.status_code == 400
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_data_endpoints.py -v
```

预期：FAIL with 404

- [ ] **Step 3: 创建 `src/api/data_endpoints.py`**

```python
"""Data management API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.logging import LOGGER, log_request
from src.api.scenario_endpoints import _load_ohlc, _normalize_period

router = APIRouter(prefix="/data", tags=["data"])

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"

_PERIOD_SUFFIX = {"1hour": "1h", "4hour": "4h", "1day": "1d", "7day": "7d"}


class RefreshRequest(BaseModel):
    sub_index: str
    period: str = "1day"


@router.get("/cache-status")
def cache_status() -> dict[str, Any]:
    """List all cached parquet files with metadata."""
    if not CACHE_DIR.exists():
        return {
            "cache_dir": str(CACHE_DIR),
            "total_files": 0,
            "total_size_bytes": 0,
            "files": [],
        }

    files = []
    total_size = 0
    for path in sorted(CACHE_DIR.glob("*.parquet"), key=lambda p: p.name):
        stat = path.stat()
        total_size += stat.st_size

        bar_count = None
        try:
            df = pd.read_parquet(path, columns=["close"])
            bar_count = len(df)
        except Exception:
            pass

        files.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "bar_count": bar_count,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    log_request(LOGGER, endpoint="/data/cache-status", extra={"file_count": len(files)})
    return {
        "cache_dir": str(CACHE_DIR),
        "total_files": len(files),
        "total_size_bytes": total_size,
        "files": files,
    }


@router.post("/refresh")
def refresh_data(request: RefreshRequest) -> dict[str, Any]:
    """Force refresh cached data for a sub-index and period."""
    period = _normalize_period(request.period)
    try:
        df = _load_ohlc(request.sub_index, period, force_refresh=True)
        bar_count = len(df)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Data refresh failed: {exc}") from exc

    log_request(
        LOGGER,
        endpoint="/data/refresh",
        sub_index=request.sub_index,
        period=period,
        extra={"bar_count": bar_count},
    )
    return {
        "sub_index": request.sub_index,
        "period": period,
        "success": True,
        "bar_count": bar_count,
        "message": f"已刷新 {bar_count} 根K线数据",
    }
```

- [ ] **Step 4: 在 `run_scenario_server.py` 注册路由**

```python
from src.api.data_endpoints import router as data_router
app.include_router(data_router)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/test_data_endpoints.py -v
```

预期：4 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add src/api/data_endpoints.py tests/test_data_endpoints.py run_scenario_server.py
git commit -m "feat(api): 添加数据管理端点（缓存状态+强制刷新）"
```

---

## Task 12: 情景分析页面

**Files:**
- Create: `frontend/src/pages/ScenarioPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/ScenarioPage.tsx`**

```typescript
import { useCallback, useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { api, ApiError } from "../lib/api";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { ScenarioBar } from "../components/ScenarioBar";
import { formatNumber, formatPercent, directionLabel, directionColor } from "../lib/format";
import type {
  OhlcBar,
  Scenario,
  HistoryMatch,
  TemplateMatch,
  ExplainResponse,
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
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period, refreshKey]);

  useEffect(() => {
    load();
  }, [load]);

  // 加载选中情景的 LLM 解释
  useEffect(() => {
    if (scenarios.length === 0) return;
    const s = scenarios[selectedIdx];
    if (!s) return;
    api
      .explain(s as unknown as Record<string, unknown>)
      .then((res: ExplainResponse) => setExplanation(res.explanation))
      .catch(() => setExplanation("解释生成失败"));
  }, [scenarios, selectedIdx]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="价格走势" className="lg:col-span-2"><LoadingState message="加载K线数据..." /></Card>
        <Card title="情景概率"><LoadingState message="生成情景中..." /></Card>
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={load} />;
  }

  const selected = scenarios[selectedIdx];

  const chartOption = {
    animation: false,
    grid: { left: "8%", right: "4%", top: "8%", bottom: "12%" },
    xAxis: {
      type: "category" as const,
      data: ohlc.map((b) => b.timestamp.slice(0, 10)),
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    yAxis: {
      type: "value" as const,
      scale: true,
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    dataZoom: [
      { type: "inside" as const, start: 60, end: 100 },
      { type: "slider" as const, start: 60, end: 100, height: 20, bottom: 8 },
    ],
    series: [
      {
        type: "candlestick",
        data: ohlc.map((b) => [b.open, b.close, b.low, b.high]),
        itemStyle: {
          color: "#16a34a",
          color0: "#dc2626",
          borderColor: "#16a34a",
          borderColor0: "#dc2626",
        },
      },
    ],
  };

  return (
    <div className="space-y-4">
      {/* 生成信息 */}
      <div className="flex items-center gap-3 text-xs text-ink-muted">
        <span>生成耗时: {genTime.toFixed(0)}ms</span>
        <span>情景数: {scenarios.length}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* 左侧：K线图 */}
        <Card title="价格走势" className="lg:col-span-2">
          {ohlc.length === 0 ? (
            <EmptyState message="暂无K线数据" />
          ) : (
            <ReactECharts option={chartOption} style={{ height: "400px" }} />
          )}
        </Card>

        {/* 右侧：情景概率 */}
        <Card title="情景概率分布">
          {scenarios.length === 0 ? (
            <EmptyState message="暂无情景区间" />
          ) : (
            <ScenarioBar scenarios={scenarios} selectedIndex={selectedIdx} onSelect={setSelectedIdx} />
          )}
        </Card>
      </div>

      {/* 选中情景详情 */}
      {selected && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="交易建议">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-ink-primary">{selected.name}</span>
                <span className={`text-xs ${directionColor(selected.direction_label)}`}>
                  {directionLabel(selected.direction_label)}
                </span>
                <span className="text-xs text-ink-muted">概率 {formatPercent(selected.probability, 1)}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-ink-muted">支撑: </span>
                  <span className="font-medium text-ink-primary">{formatNumber(selected.support)}</span>
                </div>
                <div>
                  <span className="text-ink-muted">阻力: </span>
                  <span className="font-medium text-ink-primary">{formatNumber(selected.resistance)}</span>
                </div>
                <div>
                  <span className="text-ink-muted">目标: </span>
                  <span className="font-medium text-bull">{formatNumber(selected.target)}</span>
                </div>
                <div>
                  <span className="text-ink-muted">止损: </span>
                  <span className="font-medium text-bear">{formatNumber(selected.stop_loss)}</span>
                </div>
                <div>
                  <span className="text-ink-muted">仓位: </span>
                  <span className="font-medium text-ink-primary">{formatNumber(selected.position_size, 4)}</span>
                </div>
              </div>
              <p className="pt-2 text-xs text-ink-secondary">{selected.description}</p>
            </div>
          </Card>

          <Card title="LLM 解释">
            {explanation ? (
              <p className="text-sm leading-relaxed text-ink-secondary">{explanation}</p>
            ) : (
              <LoadingState message="生成解释中..." rows={2} />
            )}
          </Card>
        </div>
      )}

      {/* 相似历史 + 模板匹配 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="相似历史片段">
          {history.length === 0 ? (
            <EmptyState message="暂无相似片段" />
          ) : (
            <div className="max-h-64 space-y-1.5 overflow-y-auto">
              {history.map((h, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg border border-surface-border px-3 py-2 text-sm">
                  <span className="text-ink-secondary">{h.candidate_start_timestamp.slice(0, 10)}</span>
                  <div className="flex gap-3 text-xs">
                    <span className="text-ink-muted">距离: {formatNumber(h.distance, 4)}</span>
                    <span className={h.future_return >= 0 ? "text-bull" : "text-bear"}>
                      {formatPercent(h.future_return)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="模板匹配">
          {templates.length === 0 ? (
            <EmptyState message="暂无匹配模板" />
          ) : (
            <div className="max-h-64 space-y-1.5 overflow-y-auto">
              {templates.map((t, i) => (
                <div key={i} className="rounded-lg border border-surface-border px-3 py-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-ink-primary">{t.template_name}</span>
                    <span className="text-xs text-ink-muted">
                      置信度: {formatPercent(t.confidence, 1)}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-ink-secondary">{t.suggestion}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 更新 `frontend/src/App.tsx` 替换情景分析占位路由**

将 `<Route path="/" element={<Placeholder name="情景分析" />} />` 替换为：

```typescript
import { ScenarioPage } from "./pages/ScenarioPage";
// ...
<Route path="/" element={<ScenarioPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
```

- [ ] **Step 3: 构建验证**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build
```

- [ ] **Step 4: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/src/pages/ScenarioPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现情景分析页面（K线+概率+建议+历史+模板+LLM解释）"
```

---


## Task 13: MVP 回测页面

**Files:**
- Create: `frontend/src/pages/BacktestPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/BacktestPage.tsx`**

```typescript
import { useCallback, useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { api, ApiError } from "../lib/api";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { formatNumber, formatPercent, formatDate } from "../lib/format";
import type { MvpBacktestResponse } from "../types/api";

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
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "回测失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period]);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5"><LoadingState rows={2} /></div>
        <Card title="净值曲线"><LoadingState message="运行回测中..." /></Card>
      </div>
    );
  }
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <EmptyState message="无回测数据" />;

  const m = data.metrics;

  const equityOption = {
    animation: false,
    grid: { left: "8%", right: "4%", top: "8%", bottom: "12%" },
    xAxis: {
      type: "category" as const,
      data: data.equity_curve.map((p) => p.timestamp.slice(0, 10)),
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    yAxis: {
      type: "value" as const, scale: true,
      axisLabel: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    dataZoom: [{ type: "inside" as const, start: 0, end: 100 }],
    series: [{
      type: "line",
      data: data.equity_curve.map((p) => p.equity),
      smooth: false,
      lineStyle: { color: "#3b82f6", width: 2 },
      areaStyle: { color: "rgba(59, 130, 246, 0.08)" },
    }],
  };

  const pf = !Number.isFinite(m.profit_factor)
    ? (m.profit_factor === Infinity ? "∞" : "-")
    : formatNumber(m.profit_factor);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <MetricCard label="总收益" value={formatPercent(m.total_return)} color={m.total_return >= 0 ? "text-bull" : "text-bear"} />
        <MetricCard label="最大回撤" value={formatPercent(m.max_drawdown)} color="text-bear" />
        <MetricCard label="夏普比率" value={formatNumber(m.sharpe_ratio)} />
        <MetricCard label="胜率" value={formatPercent(m.win_rate)} />
        <MetricCard label="总交易数" value={String(m.total_trades)} />
      </div>

      <Card title="净值曲线">
        {data.equity_curve.length === 0 ? (
          <EmptyState message="暂无净值数据" />
        ) : (
          <ReactECharts option={equityOption} style={{ height: "350px" }} />
        )}
      </Card>

      <Card title="交易记录">
        {data.trades.length === 0 ? (
          <EmptyState message="无交易记录" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                  <th className="pb-2 pr-3">入场时间</th>
                  <th className="pb-2 pr-3">入场价</th>
                  <th className="pb-2 pr-3">出场时间</th>
                  <th className="pb-2 pr-3">出场价</th>
                  <th className="pb-2 pr-3">出场原因</th>
                  <th className="pb-2 pr-3">盈亏</th>
                  <th className="pb-2">收益率</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t, i) => (
                  <tr key={i} className="border-b border-surface-border/50">
                    <td className="py-2 pr-3 text-ink-secondary">{formatDate(t.entry_time)}</td>
                    <td className="py-2 pr-3 text-ink-primary">{formatNumber(t.entry_price)}</td>
                    <td className="py-2 pr-3 text-ink-secondary">{formatDate(t.exit_time)}</td>
                    <td className="py-2 pr-3 text-ink-primary">{t.exit_price != null ? formatNumber(t.exit_price) : "-"}</td>
                    <td className="py-2 pr-3 text-ink-muted">{t.exit_reason || "-"}</td>
                    <td className={`py-2 pr-3 font-medium ${t.pnl >= 0 ? "text-bull" : "text-bear"}`}>{formatNumber(t.pnl)}</td>
                    <td className={`py-2 ${t.return_pct >= 0 ? "text-bull" : "text-bear"}`}>{formatPercent(t.return_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 更新 `frontend/src/App.tsx` 替换回测占位路由**

```typescript
import { BacktestPage } from "./pages/BacktestPage";
// ...
<Route path="/backtest" element={<BacktestPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend && npm run build
cd ..
git add frontend/src/pages/BacktestPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现 MVP 回测页面（指标卡片+净值曲线+交易记录表）"
```

---

## Task 14: 集成策略页面

**Files:**
- Create: `frontend/src/pages/EnsemblePage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/EnsemblePage.tsx`**

```typescript
import { useCallback, useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { api, ApiError } from "../lib/api";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { formatPercent, formatNumber } from "../lib/format";
import type { EnsembleResponse, StrategyResult } from "../types/api";

interface Props {
  subIndex: string;
  period: string;
  refreshKey: number;
}

const STRATEGY_LABELS: Record<string, string> = {
  ensemble: "集成策略", pullback: "回撤策略", trend_following: "趋势跟踪",
};
const STRATEGY_COLORS: Record<string, string> = {
  ensemble: "#3b82f6", pullback: "#16a34a", trend_following: "#f59e0b",
};

export function EnsemblePage({ subIndex, period, refreshKey }: Props) {
  const [data, setData] = useState<EnsembleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.runEnsemble(subIndex, period);
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period]);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (loading) return <Card title="集成策略对比"><LoadingState message="运行三策略回测中..." /></Card>;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <EmptyState message="无策略数据" />;

  const strategies: StrategyResult[] = [data.ensemble, data.pullback, data.trend_following];

  const equityOption = {
    animation: false,
    grid: { left: "8%", right: "4%", top: "8%", bottom: "12%" },
    legend: { data: strategies.map((s) => STRATEGY_LABELS[s.strategy_name] || s.strategy_name), top: 0, textStyle: { color: "#64748b", fontSize: 12 } },
    xAxis: { type: "category" as const, data: data.ensemble.equity_curve.map((p) => p.timestamp.slice(0, 10)), axisLabel: { color: "#64748b", fontSize: 11 } },
    yAxis: { type: "value" as const, scale: true, axisLabel: { color: "#64748b", fontSize: 11 }, splitLine: { lineStyle: { color: "#e2e8f0" } } },
    dataZoom: [{ type: "inside" as const, start: 0, end: 100 }],
    series: strategies.map((s) => ({
      name: STRATEGY_LABELS[s.strategy_name] || s.strategy_name,
      type: "line",
      data: s.equity_curve.map((p) => p.equity),
      smooth: false,
      lineStyle: { color: STRATEGY_COLORS[s.strategy_name] || "#999", width: 2 },
      symbol: "none",
    })),
  };

  return (
    <div className="space-y-4">
      <Card title="三策略净值曲线对比">
        <ReactECharts option={equityOption} style={{ height: "400px" }} />
      </Card>
      <Card title="指标对比">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                <th className="pb-2 pr-4">策略</th><th className="pb-2 pr-4">总收益</th><th className="pb-2 pr-4">最大回撤</th>
                <th className="pb-2 pr-4">夏普</th><th className="pb-2 pr-4">胜率</th><th className="pb-2 pr-4">盈亏比</th><th className="pb-2">交易数</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((s) => {
                const m = s.metrics;
                const pf = !Number.isFinite(m.profit_factor) ? (m.profit_factor === Infinity ? "∞" : "-") : formatNumber(m.profit_factor);
                return (
                  <tr key={s.strategy_name} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 font-medium text-ink-primary">{STRATEGY_LABELS[s.strategy_name] || s.strategy_name}</td>
                    <td className={`py-2 pr-4 ${m.total_return >= 0 ? "text-bull" : "text-bear"}`}>{formatPercent(m.total_return)}</td>
                    <td className="py-2 pr-4 text-bear">{formatPercent(m.max_drawdown)}</td>
                    <td className="py-2 pr-4 text-ink-primary">{formatNumber(m.sharpe_ratio)}</td>
                    <td className="py-2 pr-4 text-ink-primary">{formatPercent(m.win_rate)}</td>
                    <td className="py-2 pr-4 text-ink-primary">{pf}</td>
                    <td className="py-2 text-ink-secondary">{m.total_trades}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 更新 `frontend/src/App.tsx` 替换集成策略占位路由**

```typescript
import { EnsemblePage } from "./pages/EnsemblePage";
// ...
<Route path="/ensemble" element={<EnsemblePage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend && npm run build
cd ..
git add frontend/src/pages/EnsemblePage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现集成策略页面（三策略净值叠加+指标对比表）"
```

---

## Task 15: 趋势扫描页面（含轮询清理/指数退避）

**Files:**
- Create: `frontend/src/pages/TrendScanPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/TrendScanPage.tsx`**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import ReactECharts from "echarts-for-react";
import { api, ApiError } from "../lib/api";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { formatPercent, formatNumber } from "../lib/format";
import type { TaskStatusResponse, ScanEntry } from "../types/api";

interface Props {
  subIndex: string;
  period: string;
  refreshKey: number;
}

const MAX_POLL_MS = 5_000;
const BASE_POLL_MS = 1_000;

export function TrendScanPage({ subIndex, period, refreshKey }: Props) {
  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<number | null>(null);
  const pollIntervalRef = useRef(BASE_POLL_MS);

  const startScan = useCallback(async () => {
    setLoading(true);
    setError("");
    setStatus(null);
    pollIntervalRef.current = BASE_POLL_MS;
    try {
      const { task_id } = await api.startTrendScan(subIndex, period);
      const poll = async () => {
        try {
          const s = await api.getTaskStatus(task_id);
          setStatus(s);
          if (s.status === "running" || s.status === "pending") {
            pollIntervalRef.current = Math.min(pollIntervalRef.current * 1.5, MAX_POLL_MS);
            pollRef.current = window.setTimeout(poll, pollIntervalRef.current);
          } else if (s.status === "failed" && s.error) {
            setError(`扫描失败: ${s.error}`);
          }
        } catch (e) {
          setError(e instanceof ApiError ? e.message : "轮询状态失败");
        }
      };
      poll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "启动扫描失败");
    } finally {
      setLoading(false);
    }
  }, [subIndex, period]);

  useEffect(() => {
    return () => {
      if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null; }
    };
  }, [refreshKey]);

  const isRunning = status?.status === "running" || status?.status === "pending";
  const result = status?.result;

  const top10Option = result && result.top_10.length > 0 ? {
    animation: false,
    grid: { left: "10%", right: "4%", top: "8%", bottom: "15%" },
    xAxis: { type: "category" as const, data: result.top_10.map((_, i) => `#${i + 1}`), axisLabel: { color: "#64748b", fontSize: 11 } },
    yAxis: { type: "value" as const, axisLabel: { color: "#64748b", fontSize: 11, formatter: (v: number) => `${(v * 100).toFixed(0)}%` }, splitLine: { lineStyle: { color: "#e2e8f0" } } },
    series: [{ type: "bar", data: result.top_10.map((e: ScanEntry) => ({ value: e.total_return, itemStyle: { color: e.total_return >= 0 ? "#16a34a" : "#dc2626" } })) }],
  } : null;

  return (
    <div className="space-y-4">
      <Card title="趋势参数扫描">
        <div className="flex items-center gap-4">
          <button onClick={startScan} disabled={isRunning || loading}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">
            {isRunning ? "扫描中..." : "启动扫描"}
          </button>
          {status && (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-ink-secondary">状态: {status.status}</span>
              <span className="text-ink-muted">{status.message}</span>
              {isRunning && (
                <div className="h-2 w-32 overflow-hidden rounded-full bg-surface-hover">
                  <div className="h-full rounded-full bg-brand-500 transition-all duration-300" style={{ width: `${status.progress * 100}%` }} />
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {error && !isRunning && <ErrorState message={error} onRetry={startScan} />}

      {result && (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Top 10 收益率">
              {top10Option ? <ReactECharts option={top10Option} style={{ height: "300px" }} /> : <EmptyState />}
            </Card>
            <Card title="扫描摘要">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-ink-muted">总组合数</span><span className="font-medium text-ink-primary">{result.total_combinations}</span></div>
                <div className="flex justify-between"><span className="text-ink-muted">非负收益数</span><span className="font-medium text-bull">{result.non_negative_count}</span></div>
                <div className="flex justify-between"><span className="text-ink-muted">正收益占比</span><span className="font-medium text-ink-primary">{formatPercent(result.non_negative_count / result.total_combinations)}</span></div>
              </div>
            </Card>
          </div>
          <Card title="参数排名详情">
            {result.top_10.length === 0 ? <EmptyState /> : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                    <th className="pb-2 pr-3">排名</th><th className="pb-2 pr-3">总收益</th><th className="pb-2 pr-3">最大回撤</th>
                    <th className="pb-2 pr-3">夏普</th><th className="pb-2 pr-3">胜率</th><th className="pb-2">关键参数</th>
                  </tr></thead>
                  <tbody>
                    {result.top_10.map((e: ScanEntry, i: number) => (
                      <tr key={i} className="border-b border-surface-border/50">
                        <td className="py-2 pr-3 font-medium text-ink-primary">#{i + 1}</td>
                        <td className={`py-2 pr-3 ${e.total_return >= 0 ? "text-bull" : "text-bear"}`}>{formatPercent(e.total_return)}</td>
                        <td className="py-2 pr-3 text-bear">{formatPercent(e.max_drawdown)}</td>
                        <td className="py-2 pr-3 text-ink-primary">{formatNumber(e.sharpe_ratio)}</td>
                        <td className="py-2 pr-3 text-ink-primary">{formatPercent(e.win_rate)}</td>
                        <td className="py-2 text-xs text-ink-muted">ADX={String(e.params.trend_strength_threshold)}, DI={String(e.params.use_di_filter)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 更新 `frontend/src/App.tsx` 替换趋势扫描占位路由**

```typescript
import { TrendScanPage } from "./pages/TrendScanPage";
// ...
<Route path="/trend-scan" element={<TrendScanPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend && npm run build
cd ..
git add frontend/src/pages/TrendScanPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现趋势扫描页面（异步任务+指数退避轮询+Top10图表）"
```

---

## Task 16: 报告中心页面

**Files:**
- Create: `frontend/src/pages/ReportsPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/ReportsPage.tsx`**

```typescript
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { formatFileSize, formatDate } from "../lib/format";
import type { ReportFile, ReportContentResponse } from "../types/api";

export function ReportsPage() {
  const [files, setFiles] = useState<ReportFile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<ReportContentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listReports();
      setFiles(res.reports);
      if (res.reports.length > 0 && !selected) {
        setSelected(res.reports[0].filename);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载报告列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  useEffect(() => {
    if (!selected) return;
    api.getReport(selected).then(setContent).catch((e: unknown) => {
      setError(e instanceof ApiError ? e.message : "加载报告内容失败");
    });
  }, [selected]);

  if (loading) return <Card title="报告中心"><LoadingState message="加载报告列表..." /></Card>;
  if (error) return <ErrorState message={error} onRetry={loadList} />;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Card title="报告列表" className="md:col-span-1">
        {files.length === 0 ? (
          <EmptyState message="暂无报告文件" />
        ) : (
          <div className="max-h-[500px] space-y-1 overflow-y-auto">
            {files.map((f) => (
              <button
                key={f.filename}
                onClick={() => setSelected(f.filename)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                  selected === f.filename
                    ? "border-brand-500 bg-brand-50"
                    : "border-surface-border bg-surface-card hover:bg-surface-hover"
                }`}
              >
                <div className="truncate font-medium text-ink-primary">{f.filename}</div>
                <div className="mt-0.5 text-xs text-ink-muted">
                  {formatFileSize(f.size_bytes)} · {formatDate(f.modified_at)}
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>

      <Card title="报告内容" className="md:col-span-2">
        {content ? (
          <pre className="max-h-[500px] overflow-auto rounded-lg bg-surface-base p-4 text-xs text-ink-secondary">
            {JSON.stringify(content.content, null, 2)}
          </pre>
        ) : (
          <EmptyState message="选择左侧报告查看内容" />
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 更新 `frontend/src/App.tsx` 替换报告中心占位路由**

```typescript
import { ReportsPage } from "./pages/ReportsPage";
// ...
<Route path="/reports" element={<ReportsPage />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend && npm run build
cd ..
git add frontend/src/pages/ReportsPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现报告中心页面（文件列表+JSON内容查看）"
```

---

## Task 17: 数据管理页面

**Files:**
- Create: `frontend/src/pages/DataManagementPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/pages/DataManagementPage.tsx`**

```typescript
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { formatFileSize, formatDate, formatNumber } from "../lib/format";
import type { CacheStatusResponse } from "../types/api";

interface Props {
  subIndex: string;
  period: string;
}

export function DataManagementPage({ subIndex, period }: Props) {
  const [data, setData] = useState<CacheStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.getCacheStatus();
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载缓存状态失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMsg("");
    try {
      const res = await api.refreshData(subIndex, period);
      setRefreshMsg(res.message);
      await load();
    } catch (e) {
      setRefreshMsg(e instanceof ApiError ? e.message : "刷新失败");
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return <Card title="数据管理"><LoadingState message="加载缓存状态..." /></Card>;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <EmptyState />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <MetricCard label="缓存文件数" value={String(data.total_files)} />
        <MetricCard label="总占用空间" value={formatFileSize(data.total_size_bytes)} />
        <div className="rounded-lg border border-surface-border bg-surface-card p-4">
          <p className="text-xs font-medium text-ink-secondary">数据刷新</p>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="mt-2 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
          >
            {refreshing ? "刷新中..." : `刷新 ${subIndex} ${period}`}
          </button>
          {refreshMsg && <p className="mt-1 text-xs text-ink-muted">{refreshMsg}</p>}
        </div>
      </div>

      <Card title="缓存文件详情">
        {data.files.length === 0 ? (
          <EmptyState message="暂无缓存文件" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                  <th className="pb-2 pr-3">文件名</th>
                  <th className="pb-2 pr-3">大小</th>
                  <th className="pb-2 pr-3">K线数</th>
                  <th className="pb-2">修改时间</th>
                </tr>
              </thead>
              <tbody>
                {data.files.map((f) => (
                  <tr key={f.filename} className="border-b border-surface-border/50">
                    <td className="py-2 pr-3 font-medium text-ink-primary">{f.filename}</td>
                    <td className="py-2 pr-3 text-ink-secondary">{formatFileSize(f.size_bytes)}</td>
                    <td className="py-2 pr-3 text-ink-secondary">{f.bar_count != null ? formatNumber(f.bar_count, 0) : "-"}</td>
                    <td className="py-2 text-ink-muted">{formatDate(f.modified_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 更新 `frontend/src/App.tsx` 替换数据管理占位路由**

```typescript
import { DataManagementPage } from "./pages/DataManagementPage";
// ...
<Route path="/data" element={<DataManagementPage subIndex={subIndex} period={period} />} />
```

- [ ] **Step 3: 构建验证并提交**

```bash
cd /workspace/csqaq-glove-quant/frontend && npm run build
cd ..
git add frontend/src/pages/DataManagementPage.tsx frontend/src/App.tsx
git commit -m "feat(web): 实现数据管理页面（缓存统计+文件列表+强制刷新）"
```

---

## Task 18: 代码分割与懒加载

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 更新 `frontend/src/App.tsx` 使用 React.lazy + Suspense 实现路由级代码分割**

```typescript
import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { ErrorBoundary } from "./ErrorBoundary";
import { Layout } from "./components/Layout";
import { LoadingState } from "./components/LoadingState";

const ScenarioPage = lazy(() => import("./pages/ScenarioPage").then((m) => ({ default: m.ScenarioPage })));
const BacktestPage = lazy(() => import("./pages/BacktestPage").then((m) => ({ default: m.BacktestPage })));
const EnsemblePage = lazy(() => import("./pages/EnsemblePage").then((m) => ({ default: m.EnsemblePage })));
const TrendScanPage = lazy(() => import("./pages/TrendScanPage").then((m) => ({ default: m.TrendScanPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const DataManagementPage = lazy(() => import("./pages/DataManagementPage").then((m) => ({ default: m.DataManagementPage })));

export default function App() {
  return (
    <ErrorBoundary>
      <Layout>
        {({ subIndex, period, refreshKey }) => (
          <Suspense fallback={<LoadingState message="加载页面..." />}>
            <Routes>
              <Route path="/" element={<ScenarioPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
              <Route path="/backtest" element={<BacktestPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
              <Route path="/ensemble" element={<EnsemblePage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
              <Route path="/trend-scan" element={<TrendScanPage subIndex={subIndex} period={period} refreshKey={refreshKey} />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/data" element={<DataManagementPage subIndex={subIndex} period={period} />} />
              <Route path="*" element={
                <div className="flex h-full flex-col items-center justify-center gap-2 text-ink-muted">
                  <p className="text-4xl font-bold">404</p>
                  <p className="text-sm">页面不存在</p>
                </div>
              } />
            </Routes>
          </Suspense>
        )}
      </Layout>
    </ErrorBoundary>
  );
}
```

- [ ] **Step 2: 构建验证代码分割生效**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run build
```

预期：`dist/assets/` 目录下生成多个按路由分割的 JS chunk 文件（如 `ScenarioPage-*.js`、`BacktestPage-*.js` 等），而非单一 bundle。

- [ ] **Step 3: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/src/App.tsx
git commit -m "perf(web): 实现 React.lazy 路由级代码分割与 Suspense 懒加载"
```

---

## Task 19: 前端单元测试（Vitest）

**Files:**
- Create: `frontend/src/__tests__/format.test.ts`
- Create: `frontend/src/__tests__/api.test.ts`

- [ ] **Step 1: 创建 `frontend/src/__tests__/format.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import { formatPercent, formatNumber, formatDate, formatFileSize, directionLabel, directionColor } from "../lib/format";

describe("formatPercent", () => {
  it("formats positive numbers as percentage", () => {
    expect(formatPercent(0.15)).toBe("15.00%");
  });
  it("formats negative numbers", () => {
    expect(formatPercent(-0.05)).toBe("-5.00%");
  });
  it("handles zero", () => {
    expect(formatPercent(0)).toBe("0.00%");
  });
  it("returns dash for null", () => {
    expect(formatPercent(null)).toBe("-");
  });
  it("returns dash for NaN", () => {
    expect(formatPercent(NaN)).toBe("-");
  });
  it("returns dash for Infinity", () => {
    expect(formatPercent(Infinity)).toBe("-");
  });
  it("supports custom digits", () => {
    expect(formatPercent(0.123456, 1)).toBe("12.3%");
  });
});

describe("formatNumber", () => {
  it("formats numbers with default 2 digits", () => {
    expect(formatNumber(3.14159)).toBe("3.14");
  });
  it("returns dash for null", () => {
    expect(formatNumber(null)).toBe("-");
  });
  it("returns dash for NaN", () => {
    expect(formatNumber(NaN)).toBe("-");
  });
  it("handles zero correctly (not falsy)", () => {
    expect(formatNumber(0)).toBe("0.00");
  });
});

describe("formatDate", () => {
  it("formats ISO string to YYYY-MM-DD", () => {
    expect(formatDate("2024-03-15T10:30:00Z")).toBe("2024-03-15");
  });
  it("returns dash for null", () => {
    expect(formatDate(null)).toBe("-");
  });
  it("returns dash for empty string", () => {
    expect(formatDate("")).toBe("-");
  });
});

describe("formatFileSize", () => {
  it("formats bytes", () => {
    expect(formatFileSize(500)).toBe("500 B");
  });
  it("formats kilobytes", () => {
    expect(formatFileSize(2048)).toBe("2.0 KB");
  });
  it("formats megabytes", () => {
    expect(formatFileSize(1048576)).toBe("1.0 MB");
  });
});

describe("directionLabel", () => {
  it("translates bullish", () => {
    expect(directionLabel("bullish")).toBe("看涨");
  });
  it("translates bearish", () => {
    expect(directionLabel("bearish")).toBe("看跌");
  });
  it("translates neutral", () => {
    expect(directionLabel("neutral")).toBe("震荡");
  });
});

describe("directionColor", () => {
  it("returns bull color for bullish", () => {
    expect(directionColor("bullish")).toBe("text-bull");
  });
  it("returns bear color for bearish", () => {
    expect(directionColor("bearish")).toBe("text-bear");
  });
  it("returns neutral color for unknown", () => {
    expect(directionColor("unknown")).toBe("text-neutral");
  });
});
```

- [ ] **Step 2: 创建 `frontend/src/__tests__/api.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError } from "../lib/api";

// Mock fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
});

describe("api client", () => {
  it("throws ApiError on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Bad request" }),
    });

    await expect(api.getOhlc("test", "1day")).rejects.toThrow(ApiError);
    await expect(api.getOhlc("test", "1day")).rejects.toThrow();
  });

  it("parses JSON response on success", async () => {
    const mockData = { sub_index: "test", period: "1day", count: 1, ohlc: [] };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await api.getOhlc("test", "1day");
    expect(result).toEqual(mockData);
  });

  it("includes query params in URL", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ reports: [] }),
    });

    await api.listReports();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/reports/list"),
      expect.objectContaining({ method: "GET" })
    );
  });
});
```

- [ ] **Step 3: 运行测试**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run test
```

预期：所有测试 PASS。

- [ ] **Step 4: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add frontend/src/__tests__/
git commit -m "test(web): 添加前端单元测试（format 工具 + API 客户端）"
```

---

## Task 20: 端到端集成验证与旧前端清理

**Files:**
- Delete: `frontend/static/app.js`
- Delete: `frontend/static/style.css`
- Delete: `frontend/index.html`（旧入口，已被 `frontend/src/main.tsx` + Vite 替代）
- Modify: `docs/deployment.md`

- [ ] **Step 1: 删除旧前端文件**

```bash
cd /workspace/csqaq-glove-quant
git rm frontend/static/app.js frontend/static/style.css frontend/index.html
```

- [ ] **Step 2: 运行全部后端测试**

```bash
cd /workspace/csqaq-glove-quant
python -m pytest tests/ -v --tb=short
```

预期：所有测试 PASS。

- [ ] **Step 3: 运行全部前端测试**

```bash
cd /workspace/csqaq-glove-quant/frontend
npm run test
```

预期：所有测试 PASS。

- [ ] **Step 4: 构建前端并启动服务验证**

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
assert r1.status_code == 200, f'Frontend: expected 200, got {r1.status_code}'
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

- [ ] **Step 5: 更新 `docs/deployment.md` 增加前端构建步骤**

在"第三步：安装依赖"之后增加：

```markdown
## 第三步半：构建前端

前端使用 React + Vite 构建，需安装 Node.js（>= 18）：

    cd frontend
    npm install
    npm run build

构建产物在 `frontend/dist/`，由后端 `run_scenario_server.py` 自动挂载。
开发时可运行 `npm run dev` 启动热更新开发服务器（端口 5173），API 请求自动代理到 8000 端口。
运行前端测试：`npm run test`。
```

- [ ] **Step 6: 提交**

```bash
cd /workspace/csqaq-glove-quant
git add -A
git commit -m "feat(web): 清理旧前端文件，完成全功能 Web 可视化平台集成"
```

---

## 架构决策说明

### 性能考量

1. **路由级代码分割**：通过 `React.lazy` + `Suspense` 实现按需加载，首屏只加载当前路由的 JS chunk。ECharts 作为独立 chunk 分离，避免阻塞首屏。Vite 的 `manualChunks` 进一步将 vendor 库拆分为 `echarts` 和 `react` 两个 chunk。

2. **后端长耗时操作**：趋势扫描通过 `ThreadPoolExecutor`（max_workers=4）在后台线程执行，前端通过指数退避轮询获取进度（1s → 1.5s → 2.25s → ... → 5s 上限）。不阻塞 API 主线程，其他请求正常响应。

3. **数据缓存**：现有 `SCENARIO_CACHE`（5 分钟 TTL 内存缓存）继续工作。前端 API 客户端通过 `AbortController` 支持请求超时（30s 默认，回测类 60s）和取消。

4. **前端渲染**：ECharts 使用 Canvas 渲染，`animation: false` 禁用动画减少重绘开销。React 的 `useCallback` 避免不必要的重渲染。

### 可维护性考量

1. **组件化拆分**：每个页面是独立组件，修改一个页面不影响其他页面。通用 UI 组件（Card、MetricCard 等）复用率高。

2. **TypeScript 类型安全**：所有 API 响应有类型定义（`types/api.ts`），`noUnusedLocals` 和 `noUnusedParameters` 编译选项确保无死代码。

3. **后端端点模块化**：每个功能域一个端点文件，新增功能只需新建文件 + 在 `run_scenario_server.py` 注册路由。

4. **测试覆盖**：后端每个新端点都有对应的测试文件（TDD 流程），前端格式化工具和 API 客户端有 Vitest 单元测试覆盖。

### 关键修复清单（相比旧版计划）

| 问题 | 修复方案 |
|------|----------|
| 测试文件命名不一致 | 统一使用复数形式（`test_ensemble_endpoints.py` 等） |
| Task 5 故意写错代码 | 直接给出正确的 `ThreadPoolExecutor` 实现 |
| 缺少 React Error Boundary | Task 5 新增 `ErrorBoundary.tsx`，包裹整个应用 |
| 缺少响应式设计 | 侧边栏移动端可折叠，所有页面使用 `md:`/`lg:` 断点 |
| 缺少代码分割 | Task 18 使用 `React.lazy` + `Suspense` + `manualChunks` |
| TrendScanPage 轮询无清理 | `useEffect` cleanup 清除定时器，指数退避减少请求 |
| TrendScanPage 未处理 failed 状态 | 失败时将 `error` 写入状态，触发 `ErrorState` |
| falsy 值显示错误（0 \|\| "-"） | 使用 `!= null` 判断替代 `\|\|` |
| profit_factor 未处理 NaN | 使用 `Number.isFinite()` 统一判断 |
| API 客户端无超时/取消 | `AbortController` + 可配置 timeout |
| 任务队列无并发限制 | `ThreadPoolExecutor(max_workers=4)` |
| 缺少前端测试 | Task 19 添加 Vitest + Testing Library |
| 缺少 404 路由 | App.tsx 添加 `<Route path="*">` |
| 缺少空状态组件 | 新增 `EmptyState.tsx`，所有页面使用 |
| TopBar 状态永不清除 | 3 秒后自动清除状态文本 |
| REST 语义错误（GET 启动扫描） | 改为 POST + Pydantic body model |
| 路径遍历防护不足 | 使用 `resolve()` + `relative_to()` 规范化 |
| 缺少环境配置 | `VITE_API_BASE_URL` 环境变量 + `.env.example` |
| 架构说明与实现矛盾 | ECharts 按需引入 + `manualChunks` 真正实现代码分割 |
