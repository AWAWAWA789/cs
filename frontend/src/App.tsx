import { lazy, Suspense } from "react";
import { HashRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui/misc";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Code splitting: each page is loaded on demand
const Dashboard = lazy(() => import("./pages/Dashboard"));
const ScenarioPage = lazy(() => import("./pages/ScenarioPage"));
const BacktestPage = lazy(() => import("./pages/BacktestPage"));
const EnsemblePage = lazy(() => import("./pages/EnsemblePage"));
const TrendScanPage = lazy(() => import("./pages/TrendScanPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));
const DataPage = lazy(() => import("./pages/DataPage"));
const MonitoringPage = lazy(() => import("./pages/MonitoringPage"));

function PageLoader() {
  return (
    <div className="flex h-96 items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <HashRouter>
        <Layout>
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
              <Route path="*" element={<Dashboard />} />
            </Routes>
          </Suspense>
        </Layout>
      </HashRouter>
    </ErrorBoundary>
  );
}
