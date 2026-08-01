import { lazy, Suspense, useEffect } from "react";
import { HashRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui/misc";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useGlobalStore } from "./store/globalStore";

// Code splitting: each page is loaded on demand
const Dashboard = lazy(() => import("./pages/Dashboard"));
const ScenarioPage = lazy(() => import("./pages/ScenarioPage"));
const BacktestPage = lazy(() => import("./pages/BacktestPage"));
const EnsemblePage = lazy(() => import("./pages/EnsemblePage"));
const TrendScanPage = lazy(() => import("./pages/TrendScanPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));
const DataPage = lazy(() => import("./pages/DataPage"));
const MonitoringPage = lazy(() => import("./pages/MonitoringPage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const ItemDetailPage = lazy(() => import("./pages/ItemDetailPage"));
const RankingPage = lazy(() => import("./pages/RankingPage"));
const NotFound = lazy(() => import("./pages/NotFound"));

function PageLoader() {
  return (
    <div className="flex h-96 items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
}

/**
 * 路由切换时播放淡入动画的容器。
 *
 * 用 location.pathname 作为 key，路由变化时 React 会卸载旧子树、挂载新子树，
 * 新挂载的 div 重新触发 ``animate-fade-in`` CSS 动画，给页面切换增加平滑过渡，
 * 在功能演示场景下观感更连贯。
 */
function AnimatedRoutes() {
  const location = useLocation();
  return (
    <div key={location.pathname} className="animate-fade-in">
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scenario" element={<ScenarioPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/ensemble" element={<EnsemblePage />} />
          <Route path="/trend-scan" element={<TrendScanPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/monitoring" element={<MonitoringPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/ranking" element={<RankingPage />} />
          <Route path="/item/:goodId" element={<ItemDetailPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </div>
  );
}

/**
 * URL 状态同步组件：
 * 1. 挂载时从 URL hash query 读取 sub/period 等参数，覆盖全局 store。
 * 2. 全局 store 变化时将参数写回 URL hash（支持分享链接与刷新保持）。
 */
function UrlStateSync() {
  const location = useLocation();
  const navigate = useNavigate();
  const hydrateFromUrl = useGlobalStore((s) => s.hydrateFromUrl);
  const serializeToUrl = useGlobalStore((s) => s.serializeToUrl);
  const subIndex = useGlobalStore((s) => s.subIndex);
  const period = useGlobalStore((s) => s.period);
  const itemGoodId = useGlobalStore((s) => s.itemGoodId);
  const platform = useGlobalStore((s) => s.platform);
  const chartKey = useGlobalStore((s) => s.chartKey);
  const chartPeriod = useGlobalStore((s) => s.chartPeriod);

  // 挂载时从 URL 读取参数（仅执行一次）
  useEffect(() => {
    const hash = location.hash;
    const queryIndex = hash.indexOf("?");
    const search = queryIndex >= 0 ? hash.slice(queryIndex + 1) : "";
    hydrateFromUrl(search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 全局 store 变化时同步到 URL
  useEffect(() => {
    const query = serializeToUrl();
    const currentHash = location.hash;
    const pathPart = currentHash.split("?")[0] || "#/";
    const newHash = `${pathPart}?${query}`;

    // 避免不必要的导航（URL 已包含相同参数时跳过）
    if (currentHash !== newHash) {
      navigate(newHash, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subIndex, period, itemGoodId, platform, chartKey, chartPeriod]);

  return null;
}

export default function App() {
  return (
    <ErrorBoundary>
      <HashRouter>
        <UrlStateSync />
        <Layout>
          <AnimatedRoutes />
        </Layout>
      </HashRouter>
    </ErrorBoundary>
  );
}
