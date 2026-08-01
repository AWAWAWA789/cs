# 主力吸货侦察兵 · CSQAQ 饰品市场量化分析平台

> **一句话定义**：通过 **K线行为 + 库存行为** 双轨交叉验证，识别 CS:GO/CS2 饰品市场主力资金的隐蔽建仓痕迹，并从两年步枪千百战单品历史中训练案例库与规则权重，让识别越用越准。

基于 CSQAQ API 的饰品市场量化分析平台。核心产品是「主力吸货侦察」，辅以情景预判引擎、回测验证、可视化看板。

---

## 一、核心产品定义

### 产品定位

**主力吸货侦察兵**（Main Force Accumulation Scout）—— 判断主力资金是否在隐蔽吸货的智能分析工具。

**核心信念**：
- **K线会骗人**（主力可以做线、画图、对倒）
- **库存不会骗人**（货真在谁手里，谁在买卖，一目了然）
- **两者交叉验证**，才有可信判断

### 双轨融合架构

```
输入：单品 good_id + 周期
  │
  ├── K线行为轨 ──► accumulation_detector
  │     特征：量价背离 / 价格位置 / 横盘 / 底部抬高 / 波动率收缩 / 量能趋势
  │     输出：kline_score (0-1) + 6 项子分
  │
  ├── 库存行为轨 ──► inventory_signals
  │     特征：TOP3集中度 / 近7日净流入 / 主力活跃度 / 跨品团队协同
  │     输出：inventory_score (0-1) + 4 项子分
  │
  └── 融合层 ──► fuse_scores
        规则：双轨同向加分，单轨触发减分
        输出：fused_score (0-1) + 阶段判定 + 证据链
```

### 四种融合模式

| K线 | 库存 | 模式 | 含义 |
|---|---|---|---|
| 高 | 高 | `strong` 明牌吸货 | 主力明牌建仓，最强信号 |
| 低 | 高 | `hidden` 隐蔽吸货 | K线不动但库存加仓，最稀缺信号 |
| 高 | 低 | `weak` 疑似误判 | 可能是下跌中继，需警惕 |
| 低 | 低 | `none` 无信号 | 双低，无明显吸货迹象 |

阈值：`≥0.6` 吸货 / `≤0.3` 出货 / 中间中性。

### 核心功能矩阵

| 功能 | 模块 | 端点 | 状态 |
|------|------|------|------|
| 单品吸货分析 | `accumulation_detector` | `POST /accumulation/analyze` | ✅ |
| 双轨融合分析 | `accumulation_detector.detect_accumulation_fused` | `POST /accumulation/analyze-fused` | ✅ |
| 跨品团队识别 | `team_analyzer` | `GET /accumulation/team-analysis` | ✅ |
| LLM 归因解释 | `llm_explainer` | `GET /accumulation/explain-fused` | ✅ |
| 库存监控数据 | `item_endpoints` | `GET /accumulation/item-inventory` | ✅ |
| 历史训练流水线 | `backfill / case_store / labeling / trainer` | `/training/*` | ✅ |
| 相似案例检索 | `case_retriever` | `GET /training/similar-cases` | ✅ |
| 指数吸货扫描 | `accumulation_detector` | `POST /accumulation/scan` | ✅ |

---

## 二、历史训练体系（产品护城河）

> **案例库 + 训练权重 = 别人复制不了的资产。**

### 训练流水线（5 步）

```
Step 1 采集候选池    → /rank/items type=步枪 + /item/batch-price 筛 300-2500 元
Step 2 回填两年日线  → /info/chart period=730 落盘 Parquet（1req/s 限速）
Step 3 构建案例库    → 滑动窗口切片（步长7天）+ detect_accumulation 计算特征
Step 4 事后回看标注  → 30天涨幅 >15% = positive / 跌幅 >10% = negative
Step 5 训练权重      → LogisticRegression 拟合特征权重 + 构建 KNN 案例索引
```

### 数据落盘结构

```
data/
├── cache/                          # 指数级 K线缓存（Parquet）
├── candidates/                     # 候选池
│   └── rifle_candidates.json
├── item_cache/                     # 单品 OHLC 落盘
│   └── rifle/
│       └── {good_id}_1day.parquet
├── cases/                          # 案例库
│   ├── rifle_cases.jsonl           # 全量案例（append-only）
│   └── rifle_cases_labeled.parquet # 已标注案例（训练用）
└── trained/                        # 训练产物
    ├── rifle_rule_weights.json    # 拟合后的规则权重
    └── rifle_case_index.parquet   # KNN 案例索引
```

### 在线推理流程

```
当前饰品特征向量
  → z-score 标准化
  → KNN 检索 top-K 历史相似案例
  → 返回它们的标签与事后走势（"上次类似情况后涨了 X%"）
  → 喂给 LLM 生成人话归因
```

---

## 三、LLM 归因体系

`llm_explainer.py` 提供 provider 无关的大模型归因：

- **支持 OpenAI 兼容 API**（DeepSeek / 通义 / Kimi 等）
- **降级机制**：LLM 不可用时自动降级为模板拼接（复用证据链）
- **缓存**：相同输入 10 分钟缓存
- **token 控制**：prompt 严格约束输出格式与长度（≤150 字）

**环境变量配置**：
```bash
LLM_API_KEY=sk-xxx           # 必需
LLM_BASE_URL=https://api.deepseek.com/v1  # 默认 DeepSeek
LLM_MODEL=deepseek-chat      # 默认 deepseek-chat
```

---

## 四、项目架构

### 后端模块（Python ≥3.10）

```
src/
├── api/                           # FastAPI 端点层
│   ├── accumulation_endpoints.py  # 吸货分析 API（含融合/团队/LLM归因）
│   ├── training_endpoints.py      # 历史训练流水线 API
│   ├── item_endpoints.py          # 饰品详情 7 平台接口
│   ├── rank_endpoints.py          # 涨跌排行与饰品列表
│   ├── scenario_endpoints.py      # 双轨情景预判引擎 API
│   ├── backtest_endpoints.py      # 回测 API
│   ├── ensemble_endpoints.py      # 集成策略 API
│   ├── monitor_endpoints.py       # 库存监控 API
│   ├── volume_endpoints.py        # 量能分析 API
│   ├── data_endpoints.py          # 数据缓存管理 API
│   ├── report_endpoints.py        # 报告查询 API
│   ├── trend_scan_endpoints.py   # 趋势扫描 API
│   ├── client.py                  # CSQAQ API 客户端（1req/s 限流）
│   ├── cache.py                   # TTL 缓存层
│   ├── monitoring.py              # 运行时监控
│   └── task_queue.py              # 异步任务队列
├── scenario_engine/               # 情景引擎与吸货识别
│   ├── accumulation_detector.py   # 吸货识别（规则引擎 + 双轨融合）
│   ├── inventory_signals.py       # 库存行为特征提取
│   ├── team_analyzer.py           # 跨品主力团队识别
│   ├── llm_explainer.py           # LLM 归因解释
│   ├── case_store.py              # 案例库存储（JSONL + Parquet）
│   ├── labeling.py                # 事后回看标注
│   ├── trainer.py                 # 规则权重训练 + 案例索引构建
│   ├── case_retriever.py          # 在线相似案例检索
│   ├── fusion.py                  # 双轨情景融合
│   ├── scenario_generator.py      # 情景生成（2-4条高概率情景）
│   ├── knn_search.py / dtw_search.py  # 相似性搜索内核
│   ├── index_builder.py           # 预计算历史状态索引
│   ├── adaptive_calibration.py    # 子指数级温度自适应校准
│   ├── bayesian_calibration.py    # 贝叶斯概率校准
│   └── state_vector.py            # 市场状态向量定义
├── data/                          # 数据管道
│   ├── cache.py                   # 指数级 Parquet 缓存
│   ├── item_cache.py              # 单品 OHLC 落盘
│   └── backfill.py                # 批量回填编排器
├── features/                      # 价格行为特征库
├── strategy/                      # 信号生成与风控
├── backtest/                      # 回测引擎
├── analysis/                      # 绩效指标
└── optimization/                  # 参数寻优
```

### 前端（React 18 + TypeScript + Vite + Tailwind）

```
frontend/src/
├── pages/
│   ├── AccumulationPage.tsx       # 库存吸货分析（核心页面）
│   ├── Dashboard.tsx              # 仪表盘
│   ├── ScenarioPage.tsx           # 情景预判
│   ├── BacktestPage.tsx           # 回测可视化
│   ├── EnsemblePage.tsx           # 集成策略
│   ├── TrendScanPage.tsx          # 趋势扫描
│   ├── RankingPage.tsx            # 涨跌排行
│   ├── SearchPage.tsx             # 饰品搜索
│   ├── ItemDetailPage.tsx         # 单品详情
│   ├── DataPage.tsx               # 数据管理
│   ├── MonitoringPage.tsx         # 运行监控
│   └── ReportsPage.tsx            # 报告归档
├── components/                    # UI 组件（Card/Button/EChart 等）
├── lib/api.ts                     # 统一 API 客户端
├── store/globalStore.ts           # Zustand 全局状态
└── types/api.ts                   # TypeScript 类型定义
```

---

## 五、快速开始

### 1. 环境配置

```bash
cp .env.example .env
# 编辑 .env，填入 CSQAQ_API_TOKEN
# 可选：配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 启用大模型归因
```

### 2. 安装依赖

```bash
# 后端
pip install -e . --break-system-packages

# 前端
cd frontend && npm install
```

### 3. 启动服务

```bash
# 构建前端
cd frontend && npm run build

# 启动后端（含前端静态服务）
cd .. && python run_scenario_server.py
# 访问 http://localhost:8000
```

### 4. 执行历史训练（一次性）

在「库存吸货分析」页面底部的「训练中心」面板，依次点击：

1. **采集候选池** — 拉步枪千百战单品（300-2500元）
2. **回填两年日线** — 落盘 Parquet（约 100 品需 200s）
3. **构建案例库** — 滑动切片计算特征
4. **标注案例** — 事后回看 30 天走势
5. **训练权重** — 拟合 LogisticRegression + 构建 KNN 索引

或通过 API 直接调用：

```bash
curl -X POST http://localhost:8000/training/backfill-candidates \
  -H "Content-Type: application/json" \
  -d '{"category":"rifle","price_min":300,"price_max":2500}'
```

---

## 六、API 端点总览

### 吸货分析（核心）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/accumulation/analyze` | 单品/指数吸货分析 |
| POST | `/accumulation/analyze-fused` | 双轨融合分析（K线×库存×团队） |
| GET | `/accumulation/explain-fused` | LLM 归因 + 历史相似案例 |
| GET | `/accumulation/team-analysis` | 跨品主力团队识别 |
| GET | `/accumulation/item-inventory` | 库存监控数据 |
| POST | `/accumulation/scan` | 批量吸货评分扫描 |
| POST | `/accumulation/init` | 数据预热初始化 |
| GET | `/accumulation/status` | 初始化状态 |

### 历史训练

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/training/backfill-candidates` | 采集候选池 + 价格筛选 |
| POST | `/training/backfill-ohlc` | 批量回填两年日线 |
| GET | `/training/backfill-status` | 回填状态查询 |
| POST | `/training/build-cases` | 构建案例库（滑动切片） |
| POST | `/training/label-cases` | 事后回看标注 |
| POST | `/training/train` | 训练权重 + 构建索引 |
| GET | `/training/similar-cases` | 在线相似案例检索 |
| GET | `/training/stats` | 训练统计 |

### 饰品数据

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/item/search` | 饰品名称搜索 |
| GET | `/item/detail` | 单品详情（7平台50+字段） |
| POST | `/item/chart` | 单品多平台多周期图表 |
| POST | `/item/batch-price` | 批量价格查询 |
| POST | `/rank/items` | 饰品列表（带筛选分页） |
| POST | `/rank/list` | 涨跌排行榜 |

### 情景预判与回测

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/scenario/generate` | 双轨情景预判（2-4条高概率） |
| POST | `/scenario/history` | 历史相似片段检索 |
| POST | `/scenario/templates` | 模板匹配 |
| POST | `/backtest/equity` | 净值曲线 |
| POST | `/backtest/mvp` | MVP 回测 |

---

## 七、核心约束

| 约束 | 级别 | 说明 |
|------|------|------|
| 不依赖成交量 | 红线 | K线信号仅基于 OHLC 与时间（库存数据另算） |
| 数据时间范围 | 红线 | 仅使用 2024-01-01 UTC 之后的 K线 |
| 框架通用性 | 红线 | 不硬编码任何子指数或单品信息 |
| API 限流 | 底线 | CSQAQ 1 req/s，必须本地缓存 |
| LLM 边界 | 红线 | 核心判断由算法输出，LLM 仅做解释 |
| 价格区间 | 默认 | 训练候选品 300-2500 元（核心 500-2000） |

---

## 八、测试与质量

```bash
# 运行全部测试
python -m pytest -q

# 运行吸货识别相关测试
python -m pytest tests/scenario_engine/test_training.py -v
python -m pytest tests/scenario_engine/test_inventory_signals.py -v
python -m pytest tests/scenario_engine/test_team_analyzer.py -v
```

测试覆盖：
- `case_store` / `labeling` / `trainer` / `case_retriever` / `llm_explainer` — 25 个测试
- `inventory_signals` — 库存特征提取
- `team_analyzer` — 跨品团队识别
- `fusion` / `scenario_generator` — 双轨融合与情景质量
- 回测 / 缓存 / API 客户端 / 配置等基础模块

---

## 九、文档索引

### 战术文档（`战术文档/`）

- [战略文档](战术文档/战略文档.md) — 框架愿景、核心目标、成功指标
- [第二十一阶段-双轨融合吸货识别方案](战术文档/第二十一阶段-双轨融合吸货识别方案.md)
- [第二十二阶段-历史训练与案例库方案](战术文档/第二十二阶段-历史训练与案例库方案.md)
- [第二十阶段-前端全面重构与API深度集成实施计划](战术文档/第二十阶段-前端全面重构与API深度集成实施计划.md)
- [第十九阶段-全功能Web可视化平台实施计划](战术文档/第十九阶段-全功能Web可视化平台实施计划.md)
- 第七~十八阶段战略战术对齐报告（见目录）

### 其他文档

- [部署指南](docs/deployment.md)
- [情景 API 文档](docs/scenario_api.md)

---

## 十、技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ / FastAPI / pandas / numpy / scikit-learn / pyarrow |
| 前端 | React 18 / TypeScript / Vite / Tailwind CSS / ECharts / Zustand |
| 数据 | Parquet（OHLC 缓存）/ JSONL（案例库）/ TTL 内存缓存 |
| LLM | OpenAI 兼容 API（DeepSeek / 通义 / Kimi） |
| 部署 | Dockerfile + systemd service / uvicorn 双 worker |

---

## 十一、项目当前状态（截至 2026-08）

### 已完成

- ✅ 双轨融合吸货识别（K线行为 × 库存行为 × 团队协同）
- ✅ 跨品主力团队识别（关联品分析 + 持仓关系网络图）
- ✅ 历史训练流水线（候选池采集 → OHLC 回填 → 案例库 → 标注 → 训练）
- ✅ LLM 归因解释（provider 无关 + 降级模板）
- ✅ 前端可视化平台（12 个页面，含吸货分析核心页）
- ✅ 单元测试 25+ 项（覆盖训练全链路与 LLM 归因）

### 进行中 / 待完善

- 🔄 历史训练数据实际回填（需配置 API token 后执行 5 步流水线）
- 🔄 训练权重接入在线推理（当前规则权重仍用经验值，训练后可切换）
- 📋 更多品类扩展（当前聚焦步枪，可迁移到匕首/手套等）

---

## 修订记录

| 版本 | 日期 | 内容 |
|------|------|------|
| v0.1 | 2026-07 | 初始量化策略框架（纯价格行为） |
| v0.2 | 2026-07 | 双轨情景预判引擎 + 前端可视化 |
| v0.3 | 2026-08 | 核心产品聚焦：主力吸货侦察 + 历史训练 + LLM 归因 |
