/**
 * Tree-shaken ECharts entry point.
 *
 * The default `echarts-for-react` import pulls in the *entire* ECharts
 * runtime (~1 MB minified). This module imports only the ``echarts/core``
 * entry and registers exactly the chart types and components the app
 * actually uses, cutting the ECharts chunk by roughly 70-80 %.
 *
 * Usage: import the wrapper component from ``components/EChart`` instead of
 * importing ``echarts-for-react`` directly — the wrapper binds this
 * configured instance automatically.
 */
import * as echarts from "echarts/core";

const { use } = echarts;

// ── Chart types ──────────────────────────────────────────────
// Found across the codebase via `type:` search in series options.
import { CandlestickChart } from "echarts/charts"; // ForecastChart, ScenarioPage
import { LineChart } from "echarts/charts"; // most pages + WaveSketchChart
import { ScatterChart } from "echarts/charts"; // TrendScanPage
import { BarChart } from "echarts/charts"; // ScenarioPage (volume sub-chart)
import { GraphChart } from "echarts/charts"; // AccumulationPage 团队持仓关系图

// ── Components ────────────────────────────────────────────────
import { TitleComponent } from "echarts/components";
import { TooltipComponent } from "echarts/components";
import { GridComponent } from "echarts/components";
import { LegendComponent } from "echarts/components";
import { DataZoomComponent } from "echarts/components"; // ForecastChart
import { MarkPointComponent } from "echarts/components"; // ForecastChart
import { MarkLineComponent } from "echarts/components"; // ForecastChart, WaveSketchChart, ItemDetailPage

// ── Renderer ─────────────────────────────────────────────────
import { CanvasRenderer } from "echarts/renderers";

// Register everything once at import time. `use` is idempotent.
use([
  // Charts
  LineChart,
  BarChart,
  CandlestickChart,
  ScatterChart,
  GraphChart,
  // Components
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkPointComponent,
  MarkLineComponent,
  // Renderer
  CanvasRenderer,
]);

// Re-export the configured core namespace so the wrapper component can pass
// it to ``echarts-for-react/lib/core``'s ``echarts`` prop. The core module
// has no default export, so we re-export the namespace binding created above.
export { echarts };

