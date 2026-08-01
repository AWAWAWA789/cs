/**
 * Phase 16 scenario dashboard frontend.
 *
 * Uses Lightweight Charts for OHLC and equity visualization and fetches all
 * data from the local FastAPI scenario / backtest / monitoring endpoints.
 */

const DEFAULT_SUB_INDICES = ["手套", "匕首", "百元主战", "贴纸"];
const AUTO_REFRESH_MS = 5 * 60 * 1000;
const MONITORING_REFRESH_MS = 30 * 1000;
const PANELS = [
  "scenarioBars",
  "tradeAdvice",
  "historyList",
  "templateCards",
  "waveSketch",
  "llmExplanation",
];

const state = {
  subIndex: "手套",
  period: "1day",
  method: "knn",
  nNeighbors: 10,
  minConfidence: 0.5,
  chart: null,
  candlestickSeries: null,
  equityChart: null,
  equitySeries: null,
  activeChart: "price",
  autoRefreshId: null,
  scenarios: [],
  ohlc: [],
};

const els = {
  subIndexSelect: document.getElementById("subIndexSelect"),
  periodSelect: document.getElementById("periodSelect"),
  methodSelect: document.getElementById("methodSelect"),
  nNeighborsInput: document.getElementById("nNeighborsInput"),
  minConfidenceInput: document.getElementById("minConfidenceInput"),
  refreshBtn: document.getElementById("refreshBtn"),
  autoRefreshToggle: document.getElementById("autoRefreshToggle"),
  statusText: document.getElementById("statusText"),
  chartContainer: document.getElementById("chartContainer"),
  equityChartContainer: document.getElementById("equityChartContainer"),
  highlightInfo: document.getElementById("highlightInfo"),
  scenarioBars: document.getElementById("scenarioBars"),
  tradeAdvice: document.getElementById("tradeAdvice"),
  historyList: document.getElementById("historyList"),
  templateCards: document.getElementById("templateCards"),
  waveSketch: document.getElementById("waveSketch"),
  llmExplanation: document.getElementById("llmExplanation"),
  tradeSummary: document.getElementById("tradeSummary"),
  monitoringSummary: document.getElementById("monitoringSummary"),
};

function setStatus(message) {
  els.statusText.textContent = message;
}

function isoToTimestamp(iso) {
  return Math.floor(new Date(iso).getTime() / 1000);
}

function setPanelLoading(id, loading) {
  const content = document.getElementById(id);
  const skeleton = document.getElementById(id + "Skeleton");
  if (!content || !skeleton) return;
  content.classList.toggle("ready", !loading);
  skeleton.classList.toggle("active", loading);
}

function setGlobalError(message, retryCallback) {
  let overlay = document.getElementById("globalErrorOverlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "globalErrorOverlay";
    overlay.className = "error-overlay";
    overlay.innerHTML = `
      <h2>加载失败</h2>
      <p id="globalErrorMessage"></p>
      <button id="globalErrorRetry" class="btn primary">重试</button>
    `;
    document.body.appendChild(overlay);
  }
  document.getElementById("globalErrorMessage").textContent = message;
  const retryBtn = document.getElementById("globalErrorRetry");
  retryBtn.onclick = () => {
    overlay.classList.remove("active");
    if (retryCallback) retryCallback();
  };
  overlay.classList.add("active");
}

function clearGlobalError() {
  const overlay = document.getElementById("globalErrorOverlay");
  if (overlay) overlay.classList.remove("active");
}

window.addEventListener("error", (event) => {
  setGlobalError(`运行时错误：${event.message}`, () => window.location.reload());
});

function initChart() {
  if (state.chart) {
    state.chart.remove();
  }

  state.chart = LightweightCharts.createChart(els.chartContainer, {
    layout: {
      background: { color: "#121826" },
      textColor: "#e5e7eb",
    },
    grid: {
      vertLines: { color: "#1f2937" },
      horzLines: { color: "#1f2937" },
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#1f2937" },
    timeScale: { borderColor: "#1f2937" },
  });

  state.candlestickSeries = state.chart.addCandlestickSeries({
    upColor: "#22c55e",
    downColor: "#ef4444",
    borderUpColor: "#22c55e",
    borderDownColor: "#ef4444",
    wickUpColor: "#22c55e",
    wickDownColor: "#ef4444",
  });

  window.addEventListener("resize", () => {
    if (state.chart) {
      state.chart.applyOptions({
        width: els.chartContainer.clientWidth,
        height: els.chartContainer.clientHeight,
      });
    }
    if (state.equityChart) {
      state.equityChart.applyOptions({
        width: els.equityChartContainer.clientWidth,
        height: els.equityChartContainer.clientHeight,
      });
    }
  });
}

function initEquityChart() {
  if (state.equityChart) state.equityChart.remove();
  state.equityChart = LightweightCharts.createChart(els.equityChartContainer, {
    layout: {
      background: { color: "#121826" },
      textColor: "#e5e7eb",
    },
    grid: {
      vertLines: { color: "#1f2937" },
      horzLines: { color: "#1f2937" },
    },
    rightPriceScale: { borderColor: "#1f2937" },
    timeScale: { borderColor: "#1f2937" },
  });
  state.equitySeries = state.equityChart.addLineSeries({
    color: "#3b82f6",
    lineWidth: 2,
  });
}

function renderChart(ohlc) {
  state.ohlc = ohlc;
  const candleData = ohlc.map((bar) => ({
    time: isoToTimestamp(bar.timestamp),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
  }));
  state.candlestickSeries.setData(candleData);
  state.chart.timeScale().fitContent();
}

function renderEquity(equityCurve, trades) {
  if (!state.equitySeries) initEquityChart();
  const data = equityCurve.map((pt) => ({
    time: isoToTimestamp(pt.timestamp),
    value: pt.equity,
  }));
  state.equitySeries.setData(data);

  const markers = trades.flatMap((t) => [
    {
      time: isoToTimestamp(t.entry_time),
      position: "belowBar",
      color: "#22c55e",
      shape: "arrowUp",
      text: "买",
    },
    {
      time: isoToTimestamp(t.exit_time),
      position: "aboveBar",
      color: "#ef4444",
      shape: "arrowDown",
      text: "卖",
    },
  ]);
  state.equitySeries.setMarkers(markers);
  state.equityChart.timeScale().fitContent();

  const wins = trades.filter((t) => t.pnl > 0).length;
  const finalEquity = equityCurve.length ? equityCurve[equityCurve.length - 1].equity : "-";
  els.tradeSummary.innerHTML = `
    <span>交易数：<span class="value">${trades.length}</span></span>
    <span>胜率：<span class="value">${trades.length ? ((wins / trades.length) * 100).toFixed(1) : 0}%</span></span>
    <span>最终净值：<span class="value">${finalEquity}</span></span>
  `;
}

function clearHighlights() {
  state.candlestickSeries.setMarkers([]);
  els.highlightInfo.textContent = "";
}

function highlightMatch(match) {
  clearHighlights();
  const timeKeys = ["neighbor_timestamp", "candidate_start_timestamp"];
  const times = [];
  for (const key of timeKeys) {
    if (match[key]) times.push(isoToTimestamp(match[key]));
  }
  if (!times.length) return;

  const markers = times.map((t) => ({
    time: t,
    position: "aboveBar",
    color: "#3b82f6",
    shape: "circle",
    text: "H",
  }));
  state.candlestickSeries.setMarkers(markers);

  const info = [
    `dist: ${(match.distance || 0).toFixed(4)}`,
    match.future_return_5 !== undefined ? `ret5: ${(match.future_return_5 * 100).toFixed(2)}%` : "",
    match.future_return_7 !== undefined ? `ret7: ${(match.future_return_7 * 100).toFixed(2)}%` : "",
  ]
    .filter(Boolean)
    .join("  |  ");
  els.highlightInfo.textContent = `高亮历史片段：${info}`;
}

function scenarioColor(directionLabel) {
  if (directionLabel === "bullish") return "#22c55e";
  if (directionLabel === "bearish") return "#ef4444";
  return "#f59e0b";
}

function renderScenarios(scenarios) {
  state.scenarios = scenarios;
  els.scenarioBars.innerHTML = "";

  scenarios.forEach((scenario, idx) => {
    const bar = document.createElement("div");
    bar.className = "scenario-bar";
    bar.innerHTML = `
      <div class="name">${scenario.name}</div>
      <div class="track">
        <div class="fill" style="width: ${(scenario.probability * 100).toFixed(1)}%; background: ${scenarioColor(scenario.direction_label)}"></div>
      </div>
      <div class="prob">${(scenario.probability * 100).toFixed(1)}%</div>
    `;
    bar.addEventListener("click", () => selectScenario(idx));
    els.scenarioBars.appendChild(bar);
  });

  if (scenarios.length) {
    selectScenario(0);
  }
}

function selectScenario(idx) {
  const scenario = state.scenarios[idx];
  renderTradeAdvice(scenario);
  renderWaveSketch(scenario.wave_sketch);
  fetchExplanation(scenario);
}

function renderTradeAdvice(scenario) {
  const dirText = scenario.direction > 0 ? "偏多" : scenario.direction < 0 ? "偏空" : "中性";
  els.tradeAdvice.innerHTML = `
    <strong>${scenario.name}</strong>（${dirText}）<br>
    概率：${(scenario.probability * 100).toFixed(1)}%<br>
    支撑：${scenario.support} &nbsp;|&nbsp; 阻力：${scenario.resistance}<br>
    目标：${scenario.target} &nbsp;|&nbsp; 止损：${scenario.stop_loss}<br>
    仓位：${(scenario.position_size * 100).toFixed(2)}%
  `;
}

function renderWaveSketch(sketch) {
  const svg = els.waveSketch;
  svg.innerHTML = "";
  if (!sketch || sketch.length < 2) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", "300");
    text.setAttribute("y", "100");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#9ca3af");
    text.textContent = "暂无浪形草图";
    svg.appendChild(text);
    return;
  }

  // Remove points that would cause the polyline to backtrack within the same
  // directional swing, preserving turning points (waves).
  const cleaned = [];
  for (const pt of sketch) {
    if (cleaned.length < 2) {
      cleaned.push(pt);
      continue;
    }
    const prev = cleaned[cleaned.length - 1];
    const prev2 = cleaned[cleaned.length - 2];
    const prevDir = Math.sign(prev.price - prev2.price);
    const curDir = Math.sign(pt.price - prev.price);
    if (curDir !== 0 && curDir === prevDir && pt.price * curDir <= prev.price * curDir) {
      continue;
    }
    cleaned.push(pt);
  }

  const prices = cleaned.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const pad = (max - min) * 0.15 || 1;
  const y0 = max + pad;
  const y1 = min - pad;
  const n = cleaned.length;
  const width = 600;
  const height = 200;
  const margin = 40;

  const xFor = (i) => margin + (i / (n - 1)) * (width - margin * 2);
  const yFor = (price) => height - margin - ((price - y1) / (y0 - y1)) * (height - margin * 2);

  const points = cleaned
    .map((pt, i) => `${xFor(i)},${yFor(pt.price)}`)
    .join(" ");

  const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  polyline.setAttribute("points", points);
  polyline.setAttribute("fill", "none");
  polyline.setAttribute("stroke", "#3b82f6");
  polyline.setAttribute("stroke-width", "2");
  svg.appendChild(polyline);

  cleaned.forEach((pt, i) => {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", xFor(i));
    circle.setAttribute("cy", yFor(pt.price));
    circle.setAttribute("r", "4");
    circle.setAttribute("fill", "#e5e7eb");
    svg.appendChild(circle);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", xFor(i));
    label.setAttribute("y", yFor(pt.price) - 10);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("fill", "#9ca3af");
    label.setAttribute("font-size", "10");
    label.textContent = `${pt.label}`;
    svg.appendChild(label);
  });
}

async function fetchExplanation(scenario) {
  const current = state.ohlc[state.ohlc.length - 1] || {};
  const payload = {
    scenario,
    context: {
      sub_index: state.subIndex,
      period: state.period,
      current_price: current.close,
    },
  };
  try {
    const res = await fetch("/scenario/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    els.llmExplanation.innerHTML = `
      <p>${data.explanation}</p>
      <p><strong>浪形描述：</strong>${data.wave_sketch_description}</p>
      <div class="prompt-box">${escapeHtml(data.prompt)}</div>
    `;
  } catch (err) {
    els.llmExplanation.textContent = `解释生成失败：${err.message}`;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderHistory(matches) {
  els.historyList.innerHTML = "";
  if (!matches || !matches.length) {
    els.historyList.innerHTML = "<li>暂无相似片段</li>";
    return;
  }

  matches.forEach((match) => {
    const ts = match.neighbor_timestamp || match.candidate_start_timestamp || "";
    const ret5 = match.future_return_5;
    const retClass = ret5 > 0 ? "ret-positive" : ret5 < 0 ? "ret-negative" : "";
    const retText = ret5 !== undefined && ret5 !== null ? `${(ret5 * 100).toFixed(2)}%` : "-";
    const li = document.createElement("li");
    li.innerHTML = `<span>${ts}</span><span class="${retClass}">${retText}</span>`;
    li.addEventListener("click", () => highlightMatch(match));
    els.historyList.appendChild(li);
  });
}

function renderTemplates(matches) {
  els.templateCards.innerHTML = "";
  if (!matches || !matches.length) {
    els.templateCards.innerHTML = "<div class=\"template-card\">暂无匹配模板</div>";
    return;
  }

  matches.forEach((match) => {
    const dir = match.direction || "both";
    const div = document.createElement("div");
    div.className = "template-card";
    div.innerHTML = `
      <div class="title">${match.template_name} <span style="color:var(--muted)">(${dir})</span></div>
      <div class="meta">
        置信度：${(match.confidence * 100).toFixed(1)}% &nbsp;|&nbsp;
        支撑：${match.support || "-"} &nbsp;|&nbsp;
        阻力：${match.resistance || "-"} &nbsp;|&nbsp;
        目标：${match.target || "-"} &nbsp;|&nbsp;
        止损：${match.stop_loss || "-"}
      </div>
    `;
    els.templateCards.appendChild(div);
  });
}

async function apiGet(path, params = {}) {
  const query = new URLSearchParams(params).toString();
  const url = query ? `${path}?${query}` : path;
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

async function loadAll({ refresh = false } = {}) {
  clearGlobalError();
  clearHighlights();
  setStatus("加载中...");
  PANELS.forEach((id) => setPanelLoading(id, true));

  try {
    const [ohlcRes, genRes, histRes, tmplRes] = await Promise.all([
      apiGet("/scenario/ohlc", { sub_index: state.subIndex, period: state.period }),
      apiGet("/scenario/generate", { sub_index: state.subIndex, period: state.period, refresh: refresh ? "1" : "0" }),
      apiGet("/scenario/history", { sub_index: state.subIndex, period: state.period, method: state.method, n_neighbors: state.nNeighbors }),
      apiGet("/scenario/templates", { sub_index: state.subIndex, period: state.period, min_confidence: state.minConfidence }),
    ]);

    renderChart(ohlcRes.ohlc);
    renderScenarios(genRes.scenarios);
    renderHistory(histRes.matches);
    renderTemplates(tmplRes.matches);

    const cached = genRes.cached ? "（缓存）" : "（已生成）";
    setStatus(`${cached} 耗时 ${genRes.generation_time_ms || 0} ms`);

    try {
      const equityRes = await apiGet("/backtest/equity", { sub_index: state.subIndex, period: state.period });
      renderEquity(equityRes.equity_curve, equityRes.trades);
    } catch (equityErr) {
      els.tradeSummary.innerHTML = `<span>净值加载失败：${equityErr.message}</span>`;
    }
  } catch (err) {
    setStatus(`错误：${err.message}`);
    setGlobalError(`无法加载 ${state.subIndex} ${state.period} 数据：${err.message}`, () => loadAll({ refresh: true }));
  } finally {
    PANELS.forEach((id) => setPanelLoading(id, false));
  }
}

function populateSubIndices() {
  fetch("/scenario/meta")
    .then((res) => res.json())
    .then((data) => {
      const indices = data.available_sub_indices.length
        ? data.available_sub_indices
        : DEFAULT_SUB_INDICES;
      renderSubIndexOptions(indices);
    })
    .catch(() => renderSubIndexOptions(DEFAULT_SUB_INDICES));
}

function renderSubIndexOptions(indices) {
  els.subIndexSelect.innerHTML = "";
  indices.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    els.subIndexSelect.appendChild(opt);
  });
  if (indices.includes(state.subIndex)) {
    els.subIndexSelect.value = state.subIndex;
  } else {
    state.subIndex = indices[0];
  }
}

function setupAutoRefresh(enabled) {
  if (state.autoRefreshId) {
    clearInterval(state.autoRefreshId);
    state.autoRefreshId = null;
  }
  if (enabled) {
    state.autoRefreshId = setInterval(() => loadAll({ refresh: true }), AUTO_REFRESH_MS);
  }
}

function bindChartTabs() {
  document.querySelectorAll(".chart-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".chart-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.activeChart = tab.dataset.chart;
      document.getElementById("chartContainer").classList.toggle("active", state.activeChart === "price");
      document.getElementById("equityChartContainer").classList.toggle("active", state.activeChart === "equity");
      if (state.activeChart === "equity" && state.equityChart) {
        state.equityChart.applyOptions({
          width: els.equityChartContainer.clientWidth,
          height: els.equityChartContainer.clientHeight,
        });
        state.equityChart.timeScale().fitContent();
      }
    });
  });
}

async function loadMonitoring() {
  try {
    const data = await apiGet("/monitoring/metrics");
    const m = data.metrics;
    const alerts = data.alerts || [];
    const alertText = alerts.length
      ? `<span class="alert">告警：${alerts.map((a) => `${a.metric}=${a.value}`).join(", ")}</span>`
      : `<span class="ok">运行正常</span>`;
    els.monitoringSummary.innerHTML = `
      <span>P99: ${m.latency_p99_ms.toFixed(1)}ms</span>
      <span>失败率: ${(m.failure_rate * 100).toFixed(2)}%</span>
      <span>请求数: ${m.request_count}</span>
      ${alertText}
    `;
  } catch (err) {
    els.monitoringSummary.innerHTML = `<span class="alert">监控不可用</span>`;
  }
}

function initMonitoring() {
  loadMonitoring();
  setInterval(loadMonitoring, MONITORING_REFRESH_MS);
}

function bindEvents() {
  els.subIndexSelect.addEventListener("change", (e) => {
    state.subIndex = e.target.value;
    loadAll({ refresh: false });
  });
  els.periodSelect.addEventListener("change", (e) => {
    state.period = e.target.value;
    loadAll({ refresh: false });
  });
  els.methodSelect.addEventListener("change", (e) => {
    state.method = e.target.value;
    loadAll({ refresh: false });
  });
  els.nNeighborsInput.addEventListener("change", (e) => {
    const v = parseInt(e.target.value, 10);
    state.nNeighbors = Number.isFinite(v) ? Math.max(1, Math.min(100, v)) : 10;
    e.target.value = state.nNeighbors;
    loadAll({ refresh: false });
  });
  els.minConfidenceInput.addEventListener("change", (e) => {
    const v = parseFloat(e.target.value);
    state.minConfidence = Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0.5;
    e.target.value = state.minConfidence;
    loadAll({ refresh: false });
  });
  els.refreshBtn.addEventListener("click", () => loadAll({ refresh: true }));
  els.autoRefreshToggle.addEventListener("change", (e) => setupAutoRefresh(e.target.checked));
}

function init() {
  initChart();
  initEquityChart();
  bindEvents();
  bindChartTabs();
  populateSubIndices();
  initMonitoring();
  loadAll();
}

init();
