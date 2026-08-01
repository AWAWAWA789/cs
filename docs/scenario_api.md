# Phase 13 Scenario API 文档

本模块将 Phase 10-12 的算法能力封装为 HTTP API，并提供前端可视化界面。
所有端点均不硬编码具体板块，通过 `sub_index` 与 `period` 参数动态加载数据。

## 启动服务

```bash
python run_scenario_server.py
```

服务监听 `0.0.0.0:8000`，API 路由前缀为 `/scenario`，`frontend/` 目录挂载为静态站点根目录。

## 数据加载策略

端点按以下优先级加载 OHLC 数据：

1. 本地 Parquet 缓存（`CSQAQ_CACHE_PATH`，默认 `./data/cache`）。
2. 若配置了 `CSQAQ_API_TOKEN`，则调用 CSQAQ API 并写入缓存。
3. 否则生成确定性合成数据（仅用于演示 / 测试）。

## 通用参数

| 字段       | 类型   | 必填 | 说明                                            |
|------------|--------|------|-------------------------------------------------|
| sub_index  | string | 是   | 子指数中文名称，例如 `手套`、`匕首`。           |
| period     | string | 否   | 周期，支持 `1day`、`4hour`、`1hour`、`7day` 及别名 `1d`、`4h` 等，默认 `1day`。 |
| refresh    | bool   | 否   | 仅 `/generate` 支持，为 `true` 时清除缓存并重新生成。 |

> **中文参数传递方式**：所有接收 `sub_index` 的端点同时支持 GET（Query 参数）和 POST（JSON Body）两种方式。
> 推荐使用 POST 避免 URL 编码问题，前端已全部切换为 POST 调用。

## 端点列表

### GET /scenario/generate
### POST /scenario/generate

返回当前最新情景集合（调用 Phase 12 `scenario_generator`）。

**GET 示例**

```bash
curl "http://localhost:8000/scenario/generate?sub_index=手套&period=1day"
```

**POST 示例（推荐）**

```bash
curl -X POST http://localhost:8000/scenario/generate \
  -H "Content-Type: application/json" \
  -d '{"sub_index":"手套","period":"1day","refresh":false}'
```

**响应字段**

| 字段               | 类型   | 说明                                  |
|--------------------|--------|---------------------------------------|
| sub_index          | string | 子指数名称。                          |
| period             | string | 周期。                                |
| generated_at       | string | ISO 8601 生成时间。                   |
| generation_time_ms | float  | 算法耗时（毫秒）。                    |
| cached             | bool   | 是否命中内存缓存。                    |
| scenarios          | array  | 标准情景列表，2-4 条，概率之和为 1。  |
| per_period         | object | 各周期原始候选统计。                  |

**scenario 对象字段**

| 字段            | 类型    | 说明                                            |
|-----------------|---------|-------------------------------------------------|
| name            | string  | 情景中文名称，如 `上涨延续`。                   |
| scenario_key    | string  | 标准情景键。                                    |
| probability     | float   | 归一化概率。                                    |
| direction       | int     | `1` 看多，`-1` 看空，`0` 中性。                 |
| direction_label | string  | `bullish` / `bearish` / `neutral`。             |
| support         | float   | 支撑位。                                        |
| resistance      | float   | 阻力位。                                        |
| target          | float   | 目标位。                                        |
| stop_loss       | float   | 止损位。                                        |
| position_size   | float   | 建议仓位比例（0-1）。                           |
| wave_sketch     | array   | 浪形草图点位，用于 SVG 绘制。                   |
| description     | string  | 情景描述。                                      |
| source          | string  | 来源标识。                                      |

---

### GET /scenario/history
### POST /scenario/history

返回历史相似片段（调用 Phase 10 `similarity_search`）。

**GET 示例**

```bash
curl "http://localhost:8000/scenario/history?sub_index=手套&period=1day&method=knn&n_neighbors=10"
```

**POST 示例（推荐）**

```bash
curl -X POST http://localhost:8000/scenario/history \
  -H "Content-Type: application/json" \
  -d '{"sub_index":"手套","period":"1day","method":"knn","n_neighbors":10}'
```

**参数**

| 字段        | 类型   | 必填 | 说明                                       |
|-------------|--------|------|--------------------------------------------|
| method      | string | 否   | `knn` / `dtw` / `cluster`，默认 `knn`。    |
| n_neighbors | int    | 否   | 返回数量，默认 10，范围 1-100。            |

**响应字段**

| 字段    | 类型   | 说明                  |
|---------|--------|-----------------------|
| matches | array  | 相似片段列表。        |

`knn` 匹配包含 `neighbor_index`、`neighbor_timestamp`、`distance`、`future_return_5` 等；
`dtw` 匹配包含 `candidate_start`、`candidate_end`、`candidate_start_timestamp` 等。

---

### GET /scenario/templates
### POST /scenario/templates

返回当前匹配的模板列表（调用 Phase 11 `template_matcher`）。

**GET 示例**

```bash
curl "http://localhost:8000/scenario/templates?sub_index=手套&period=1day&min_confidence=0.5"
```

**POST 示例（推荐）**

```bash
curl -X POST http://localhost:8000/scenario/templates \
  -H "Content-Type: application/json" \
  -d '{"sub_index":"手套","period":"1day","min_confidence":0.5}'
```

**参数**

| 字段           | 类型  | 必填 | 说明                            |
|----------------|-------|------|---------------------------------|
| min_confidence | float | 否   | 最小置信度，默认 0.5，范围 0-1。 |

**响应字段**

| 字段    | 类型   | 说明             |
|---------|--------|------------------|
| matches | array  | 模板匹配结果。   |

每个匹配项包含 `template_name`、`confidence`、`direction`、`support`、`resistance`、`target`、`stop_loss`。

---

### GET /scenario/ohlc
### POST /scenario/ohlc

返回当前分析使用的原始 OHLC 序列，供前端 K 线图绘制。

**GET 示例**

```bash
curl "http://localhost:8000/scenario/ohlc?sub_index=手套&period=1day"
```

**POST 示例（推荐）**

```bash
curl -X POST http://localhost:8000/scenario/ohlc \
  -H "Content-Type: application/json" \
  -d '{"sub_index":"手套","period":"1day"}'
```

**响应字段**

| 字段   | 类型   | 说明                        |
|--------|--------|-----------------------------|
| count  | int    | K 线数量。                  |
| ohlc   | array  | 每条包含 timestamp / ohlc。 |

---

### GET /scenario/meta

返回从本地缓存和报告中发现的可用子指数列表，不硬编码板块。

**示例请求**

```bash
curl "http://localhost:8000/scenario/meta"
```

**响应字段**

| 字段                  | 类型   | 说明                     |
|-----------------------|--------|--------------------------|
| available_sub_indices | array  | 可用子指数名称。         |
| supported_periods     | array  | 支持的周期列表。         |
| default_period        | string | 默认周期，固定 `1day`。  |

---

### POST /scenario/explain

接收算法生成的情景 JSON，返回约束 LLM 的 prompt、模板解释与浪形草图描述。

**请求体**

```json
{
  "scenario": {
    "name": "上涨延续",
    "direction_label": "bullish",
    "probability": 0.42,
    "support": 120.5,
    "resistance": 135.2,
    "target": 140.0,
    "stop_loss": 118.0,
    "position_size": 0.015,
    "wave_sketch": [...]
  },
  "context": {
    "sub_index": "手套",
    "period": "1day",
    "current_price": 128.0
  }
}
```

**响应字段**

| 字段                    | 类型   | 说明                                              |
|-------------------------|--------|---------------------------------------------------|
| prompt                  | string | 发送给 LLM 的约束 prompt，明确要求仅解释不判断。  |
| explanation             | string | 自然语言解释。                                    |
| wave_sketch_description | string | 浪形草图描述。                                    |

**LLM 约束**

Prompt 中明确包含以下约束：

1. 仅解释，不得重新判断方向、概率或价位。
2. 不得引入算法未给出的外部信息。
3. 保持客观，不给出投资建议。

本端点默认不调用外部 LLM API，直接返回模板拼接结果，保证离线可用。

## 缓存说明

`/scenario/generate` 结果在进程内存中缓存 5 分钟（TTL 300 秒）。
传入 `refresh=true` 或调用 `SCENARIO_CACHE.invalidate(...)` 可立即清除。

## 前端界面

前端采用 React + Vite + Tailwind CSS + ECharts 构建的单页应用（SPA），包含：

- 仪表盘：系统概览与快速入口
- 情景分析：K 线图、情景概率条、浪形草图 SVG、LLM 解释
- 回测可视化：权益曲线、交易标记、绩效指标
- 集成策略：多策略对比（Pullback / Trend Following / Ensemble）
- 趋势扫描：异步任务队列，实时进度展示
- 报告管理：历史报告列表与查看
- 数据管理：缓存状态与刷新
- 系统监控：请求指标与健康检查

**构建前端**

```bash
cd frontend && npm install && npm run build
```

构建产物在 `frontend/dist/`，服务启动时自动挂载。
