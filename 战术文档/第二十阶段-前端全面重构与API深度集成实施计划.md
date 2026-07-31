# 第二十阶段：前端全面重构与 CSQAQ API 深度集成实施计划

> **目标：** 将平台从"草皮房"升级为生产级全功能可视化终端——全部操作在前端完成，零命令行依赖，集成 CSQAQ 全部 25+ API 端点，覆盖饰品指数、单品详情、排行榜、挂刀行情、库存监控、热门系列等完整数据维度。

---

## 一、现状诊断

### 1.1 核心 Bug（阻塞性）

| 编号 | Bug | 根因 | 影响范围 |
|------|-----|------|----------|
| B1 | 切换页面后标的/周期重置 | 各页面独立 `useState`，无全局状态 | 全部8个页面 |
| B2 | 切换时全屏闪烁 | `useAsync.ts:27` 切换时立即置 `data=null` | 除 MonitoringPage 外全部 |
| B3 | 扫描中切换选择器导致标签错位 | `TrendScanPage` 用实时 state 显示标题，但任务跑的是旧值 | TrendScanPage |
| B4 | Select 值与选项不匹配 | 初值硬编码 `"手套"`，meta 可能不含此值 | 全部含选择器的页面 |
| B5 | 请求无法取消 | 无 AbortController，快速切换产生并发废请求 | 全部 |
| B6 | URL 不持久化状态 | sub_index/period 未同步到 URL，刷新丢失 | 全部 |

### 1.2 功能缺失（严重）

| 编号 | 缺失 | 现状 |
|------|------|------|
| F1 | 无单品搜索 | 仅子指数下拉选择，无搜索框 |
| F2 | 无未来走势图 | K线图仅显示历史，无当前位置标注、无预测曲线 |
| F3 | 三个后端 API 未接入 UI | `scenario.history`、`scenario.templates`、`scenario.explain` 从未被前端调用 |
| F4 | K线图无成交量、无价位标注 | 单条 candlestick series，支撑/阻力/目标/止损仅在文字卡片 |
| F5 | wave_sketch 仅文字展示 | 未绘制为波形图 |
| F6 | 无排行榜 | CSQAQ 排行榜 API 未集成 |
| F7 | 无单品详情页 | 无法查看单个饰品的K线、多平台价格 |
| F8 | 无挂刀行情页 | CSQAQ 挂刀套利数据未集成 |
| F9 | 无库存监控页 | CSQAQ 库存监控 7 个 API 全未集成 |
| F10 | 无热门系列页 | CSQAQ 热门系列 API 未集成 |
| F11 | 无饰品列表筛选页 | CSQAQ 饰品列表筛选功能未集成 |
| F12 | 无存世量走势 | CSQAQ 存世量 API 未集成 |
| F13 | 无批量价格查询 | CSQAQ 批量价格 API 未集成 |
| F14 | 无导出功能 | 交易记录、扫描结果、报告均不可导出 |
| F15 | 无设置页 | API Token 等配置需改 .env 文件，未在前端管理 |
| F16 | 无 404 页面 | 兜底路由直接渲染 Dashboard |

### 1.3 后端 API 覆盖不足

当前仅封装了 CSQAQ 的 **3 个** API 端点（`bind_local_ip`、`current_data`、`sub/kline`），而 CSQAQ 提供了 **25+** 个可用端点，大量数据源未被利用。

---

## 二、CSQAQ 完整 API 目录

> 以下为本次计划需要集成的全部 CSQAQ API 端点，按功能模块分类，共 **25 个端点**，覆盖 7 大数据域。

### 2.1 饰品指数模块（3 个端点）

| # | API文档 | 方法 | CSQAQ路径 | 用途 | 认证 |
|---|---------|------|-----------|------|------|
| 1 | api-187131779 | GET | `/api/v1/current_data?type=init` | 首页指数数据：子指数列表、涨跌分布（按类型/价格区间）、在线人数、今日指数走势 | 需要 |
| 2 | api-230764015 | GET | `/api/v1/current_data?type=hours\|kline\|lease` | 指数扩展数据：时线数据、K线数据、租赁数据 | 需要 |
| 3 | api-278085071 | GET | `/api/v1/sub/kline?id={sub_id}&type={period}` | 子指数K线图（OHLCV），支持 1hour/4hour/1day/7day | 需要 |

**响应数据结构：**
- `current_data?type=init` 返回：`sub_index_data`（子指数列表含 id/name/name_key/market_index/chg_num/chg_rate/open/close/high/low）、`chg_type_data`（按类型涨跌分布，含1/7/15/30/90/180日涨跌）、`chg_price_data`（按价格区间涨跌分布）、`rate_data`（涨跌分布数量统计）、`online_number`（在线人数：当前/今日峰值/本月峰值/月活/涨跌幅）
- `sub/kline` 返回：OHLCV 数组，每条含 `t`(时间戳)/`o`(开盘)/`c`(收盘)/`h`(最高)/`l`(最低)/`v`(成交量)

### 2.2 饰品详情模块（7 个端点）

| # | API文档 | 方法 | CSQAQ路径 | 用途 | 认证 |
|---|---------|------|-----------|------|------|
| 4 | api-187131777 | GET | `/api/v1/goods/get_all_goods_id` | 全量饰品 ID 映射表（id→名称→market_hash_name） | 需要 |
| 5 | api-189290586 | GET | `/api/v1/search/suggest?text={keyword}` | 饰品名称联想搜索，返回 good_id + 中文名，支持皮肤/武器/职业哥/战队等特殊关键词 | 需要 |
| 6 | api-187131780 | GET | `/api/v1/info/good?id={good_id}` | 单件饰品详情：7 平台数据（BUFF/YYYP/Steam/C5/IGXE/ECO/R8），含价格/在售/求购/租赁/磨损/存世量/挂刀比例/热度排名等 50+ 字段 | 需要 |
| 7 | api-366480669 | GET | `/api/v1/info/good/statistic?id={good_id}` | 单件饰品存世量走势（近 180 天），返回日期+存世量数组 | 需要 |
| 8 | api-283470032 | POST | `/api/v1/goods/getPriceByMarketHashName` | 批量获取饰品价格和在售数据（通过 marketHashName，单次 ≤50 个） | 需要 |
| 9 | api-187131781 | POST | `/api/v1/info/chart` | 单品多平台多周期图表数据：11 种指标（出售价/求购价/短租/长租/收益率/在售量/求购量/在租量/日成交量/过户价）× 4 平台 × 7 周期 | 需要 |
| 10 | api-187131782 | POST | `/api/v1/info/simple/chartAll` | 单品全量图表（仅售价+在售量），需 good_id | 需要 |

**单品详情 (api-187131780) 核心字段：**
- **7 平台数据**：BUFF / 悠悠有品 / Steam / C5GAME / IGXE / ECOSteam / R8GAME
- **价格数据**：各平台在售价、求购价、在售数量、求购数量
- **租赁数据**：短租价格、长租价格、短租年收益率、长租年收益率、在租数量、过户底价
- **涨跌数据**：1/7/30/180 日涨跌量和涨跌率
- **挂刀比例**：Steam求购挂刀比例、Steam在售挂刀比例、BUFF求购套现比例、BUFF售价套现比例
- **基础信息**：名称、图片、磨损范围(min_float/max_float)、品质、类别、大类、存世量、热度排名及变化
- **Steam成交**：成交量、成交均价($)

**单品图表 (api-187131781) 参数：**
- `good_id`: 饰品 ID
- `key`: 数据类型（sell_price/buy_price/short_lease_price/long_lease_price/lease_annual/long_lease_annual/sell_num/buy_num/lease_num/turnover_number/transfer_price）
- `platform`: 1-BUFF / 2-悠悠有品 / 3-Steam / 4-C5GAME
- `period`: 7/15/30/90/180/365/1095 天
- `style`: 多普勒系列款式（all_style/Phase1-4/Sapphire/Ruby/Black Pearl/Emerald）

### 2.3 涨跌/热门排行模块（4 个端点）

| # | API文档 | 方法 | CSQAQ路径 | 用途 | 认证 |
|---|---------|------|-----------|------|------|
| 11 | api-187131776 | POST | `/api/v1/info/get_rank_list` | 全站排行榜：价格/租赁/挂刀套现/成交量/存世量/总市值/在售量/求购量/在租量等维度排序，支持搜索和筛选，可返回近30天价格走势 | 需要 |
| 12 | api-187131775 | POST | `/api/v1/info/get_page_list` | 饰品列表：支持按类型/品质/类别/磨损筛选，模糊搜索，分页 | 需要 |
| 13 | api-187131803 | POST | `/api/v1/info/get_series_list` | 热门系列列表：含系列名称、涨跌幅(1/7/15/30/90/180日)、饰品数量、底价总值、近15天价格走势 | 需要 |
| 14 | api-187131804 | POST | `/api/v1/info/get_series_detail` | 热门系列详情：需 series_id，返回系列内全部饰品列表 | 需要 |

**排行榜 (api-187131776) 参数：**
- `page_index` / `page_size`（最大500）
- `search`: 模糊搜索
- `filter`: 排序筛选对象，支持如 `{"排序": ["价格_售价减求购价(百分比)_升序(BUFF)"]}` 等 30+ 排序维度
- `show_recently_price`: 是否返回近30天价格走势

**饰品列表 (api-187131775) 筛选 filter：**
- 类型：不限_匕首/手套/步枪/手枪/微型冲锋枪/武器箱/探员 等（含具体型号如蝴蝶刀、M9刺刀、AK-47等）
- 品质：违禁/隐秘/保密/受限/军规级/工业级/消费级/非凡/卓越/奇异/高级/普通级/大师
- 类别：普通/纪念品/StatTrak™/★/★ StatTrak™
- 磨损：崭新出厂/略有磨损/久经沙场/破损不堪/战痕累累/无涂装

### 2.4 挂刀行情模块（1 个端点）

| # | API文档 | 方法 | CSQAQ路径 | 用途 | 认证 |
|---|---------|------|-----------|------|------|
| 15 | api-187131823 | POST | `/api/v1/info/exchange_detail` | 挂刀行情：平台购买饰品→Steam卖出获取余额（挂刀），或反向操作（反向挂刀），支持多平台/价格区间/成交量筛选 | 需要 |

**挂刀行情 (api-187131823) 参数：**
- `res`: 0-Steam余额(挂刀) / 1-平台余额(反向挂刀)
- `platforms`: BUFF-YYYP / BUFF / YYYP
- `sort_by`: 0-Steam挂底价出售 / 1-Steam丢求购出售
- `buy`:（仅 res=1 时）0-Steam在售底价购买 / 1-Steam求购购买
- `min_price` / `max_price`: 价格区间筛选
- `text`: 饰品名称关键字
- `turnover`: Steam日成交量下限筛选
- 返回：饰品ID/名称/图片 + 各平台在售/求购价格和数量 + Steam成交量 + 套现比例(max_price)

### 2.5 库存监控模块（7 个端点）

| # | API文档 | 方法 | CSQAQ路径 | 用途 | 认证 |
|---|---------|------|-----------|------|------|
| 16 | api-187131810 | POST | `/api/v1/monitor/get_task_list` | 监控任务列表：支持搜索Steam用户名/ID，按热度/创建时间/库存数量/变动时间/库存价值排序 | 需要 |
| 17 | api-187131809 | POST | `/api/v1/monitor/get_task_trends` | 库存变动动态：全站最新变动，或按 good_id 筛选特定饰品变动 | 需要 |
| 18 | api-187131813 | POST | `/api/v1/monitor/get_good_rank` | 饰品持有量排行榜：按 good_id 查询，返回持有该饰品的用户排行 | 需要 |
| 19 | api-187131814 | POST | `/api/v1/monitor/get_task_info` | 单个用户信息：需 task_id，返回用户详情 | 需要 |
| 20 | api-358158458 | POST | `/api/v1/monitor/get_task_trends_detail` | 单个用户库存动态：需 task_id，返回该用户的库存变动历史 | 需要 |
| 21 | api-187131815 | POST | `/api/v1/task/get_task_all` | 单个用户全部库存：需 task_id，支持快照 ID 查看历史库存 | 需要 |
| 22 | api-343919624 | POST | `/api/v1/monitor/get_snapshot_list` | 库存快照列表：返回用户的历史库存快照，用于对比不同日期的库存变化 | 需要 |

**库存变动类型 (type 字段)：** 0-默认库存 / 1-买入 / 2-卖出 / 3-存入 / 4-取出 / 5-CD恢复 / 6-取出/恢复 / 7-卖出/存入

### 2.6 实时成交数据模块（2 个端点，暂停更新）

| # | API文档 | 方法 | CSQAQ路径 | 用途 | 认证 |
|---|---------|------|-----------|------|------|
| 23 | api-187131821 | GET | `/api/v1/vol/current` | 平台实时成交量数据（暂停更新） | 需要 |
| 24 | api-187131822 | GET | `/api/v1/vol/detail?id={vol_id}` | 单品实时成交量历史图表和磨损数据（暂停更新） | 需要 |

> **注意：** 实时成交数据模块已暂停更新，前端集成时标注"数据暂停更新"状态，不影响其他功能。

### 2.7 系统设置模块（1 个端点）

| # | API文档 | 方法 | CSQAQ路径 | 用途 | 认证 |
|---|---------|------|-----------|------|------|
| 25 | api-342090738 | POST | `/api/v1/sys/bind_local_ip` | 绑定本机白名单 IP（频率限制 30秒/次），适用于非固定 IP 场景 | 需要 |

---

## 三、架构设计方案

### 3.1 前端状态管理重构

**方案：引入 Zustand 轻量状态管理**

```
store/
├── globalStore.ts        # 全局状态：subIndex, period, itemGoodId, platform, chartKey
├── itemStore.ts          # 单品搜索状态：搜索词、搜索结果、选中单品
├── monitorStore.ts       # 库存监控状态：选中用户、选中快照、变动筛选
└── settingsStore.ts      # 设置状态：apiToken, baseUrl, 主题
```

全局状态通过 Zustand 管理，所有页面共享，切换页面不丢失选择。状态同步到 URL query params（`?sub=手套&period=1day`），支持分享链接和刷新保持。

### 3.2 后端 API 层扩展

```
src/api/
├── client.py                 # 已有：CSQAQClient 基础客户端
├── endpoints.py              # 已有：3个端点（bind_local_ip, current_data, sub/kline）
├── market_endpoints.py       # 新增：大盘指数端点（扩展现有 current_data）
├── item_endpoints.py         # 新增：饰品搜索、详情、图表、存世量、批量价格
├── ranking_endpoints.py      # 新增：排行榜、饰品列表、热门系列
├── exchange_endpoints.py     # 新增：挂刀行情端点
├── monitor_endpoints.py      # 新增：库存监控7个端点
├── volume_endpoints.py       # 新增：实时成交数据端点（标注暂停）
├── settings_endpoints.py     # 新增：设置管理端点（读写 .env + IP绑定）
└── export_endpoints.py       # 新增：数据导出端点
```

### 3.3 后端端点映射表（CSQAQ API → 本地 FastAPI 端点）

| CSQAQ API | 本地端点 | 方法 | 路由前缀 |
|-----------|---------|------|---------|
| current_data?type=init | `/market/overview` | GET | /market |
| current_data?type=hours/kline/lease | `/market/data` | POST | /market |
| sub/kline | `/market/kline` | POST | /market |
| search/suggest | `/item/search` | POST | /item |
| goods/get_all_goods_id | `/item/all` | GET | /item |
| info/good | `/item/detail` | GET | /item |
| info/good/statistic | `/item/supply` | GET | /item |
| goods/getPriceByMarketHashName | `/item/batch-price` | POST | /item |
| info/chart | `/item/chart` | POST | /item |
| info/simple/chartAll | `/item/chart-all` | POST | /item |
| info/get_rank_list | `/rankings/list` | POST | /rankings |
| info/get_page_list | `/rankings/items` | POST | /rankings |
| info/get_series_list | `/rankings/series` | POST | /rankings |
| info/get_series_detail | `/rankings/series-detail` | POST | /rankings |
| info/exchange_detail | `/exchange/detail` | POST | /exchange |
| monitor/get_task_list | `/monitor/tasks` | POST | /monitor |
| monitor/get_task_trends | `/monitor/trends` | POST | /monitor |
| monitor/get_good_rank | `/monitor/good-rank` | POST | /monitor |
| monitor/get_task_info | `/monitor/user-info` | POST | /monitor |
| monitor/get_task_trends_detail | `/monitor/user-trends` | POST | /monitor |
| task/get_task_all | `/monitor/user-inventory` | POST | /monitor |
| monitor/get_snapshot_list | `/monitor/snapshots` | POST | /monitor |
| vol/current | `/volume/current` | GET | /volume |
| vol/detail | `/volume/detail` | GET | /volume |
| sys/bind_local_ip | `/settings/bind-ip` | POST | /settings |

### 3.4 前端页面结构

```
现有页面（重构）:
  /                    → 仪表盘（增强：大盘指数概览 + 涨跌分布 + 在线人数 + 热门排行Top10）
  /scenario            → 情景分析（增强：走势预测图 + 价位标注 + 成交量 + AI解释）
  /backtest            → 回测分析（增强：策略参数自定义 + 导出）
  /ensemble            → 集成策略（增强：下钻详情）
  /trend-scan          → 趋势扫描（增强：结果导出 + 参数应用）
  /reports             → 报告管理（增强：格式化展示 + 下载）
  /data                → 数据管理（增强：单品缓存 + 预览）
  /monitoring          → 系统监控（增强：历史趋势 + 阈值配置）

新增页面:
  /search              → 饰品搜索（搜索框 + 实时联想 + 结果列表 + 点击跳转详情）
  /item/:goodId        → 单品详情（7平台价格对比 + 多指标K线 + 存世量走势 + 租赁收益）
  /rankings            → 排行榜（30+维度排序 + 分页 + 搜索 + 筛选 + 30天走势图）
  /item-list           → 饰品列表（类型/品质/类别/磨损筛选 + 分页 + 搜索）
  /series              → 热门系列（系列卡片 + 涨跌幅 + 15天走势 + 点击进详情）
  /series/:seriesId    → 系列详情（系列内全部饰品列表 + 价格对比）
  /exchange            → 挂刀行情（挂刀/反向挂刀切换 + 平台选择 + 价格/成交量筛选 + 套现比例排行）
  /monitor             → 库存监控（任务列表 + 变动动态 + 用户详情 + 全部库存 + 快照对比）
  /monitor/:taskId     → 监控用户详情（用户信息 + 库存动态 + 全部库存 + 快照列表）
  /settings            → 系统设置（API Token + IP绑定 + 缓存清理 + 主题配置）
  /volume              → 实时成交（标注暂停更新，展示历史数据）
```

### 3.5 走势预测可视化方案

**K 线图增强：**
1. 在历史 K 线最右端标注"当前位置"（markPoint + 竖虚线 + 价格数值）
2. 支撑/阻力/目标/止损价位用 markLine 水平线叠加
3. 成交量副图（volume bar）
4. 多平台K线叠加对比（BUFF/YYYP/Steam/C5）

**未来走势预测图：**
1. 基于情景的 wave_sketch 数据，在 K 线右侧延伸模拟 K 线
2. 每条情景生成一组模拟走势（2-4条），用不同颜色区分
3. 概率以线条粗细或透明度表示
4. 当前价位处标注价格数值和点位

---

## 四、分阶段实施计划

### 第一阶段：Bug 修复与基础设施（P0 阻塞修复）

| 任务 | 文件 | 内容 |
|------|------|------|
| T1.1 引入 Zustand 全局状态 | `frontend/src/store/globalStore.ts` | 创建全局 store，管理 subIndex/period/platform/chartKey/itemGoodId，同步到 URL |
| T1.2 修复 useAsync 闪烁 | `frontend/src/hooks/useAsync.ts` | 改为 stale-while-revalidate 模式，切换时保留旧数据 |
| T1.3 添加 AbortController | `frontend/src/lib/api.ts` | request 函数支持 signal，useAsync 自动取消旧请求 |
| T1.4 修复 TrendScanPage 错位 | `frontend/src/pages/TrendScanPage.tsx` | 标题使用任务创建时的快照值，而非实时 state |
| T1.5 修复 Select 值不匹配 | `frontend/src/components/Selector.tsx` | meta 加载后校验当前值是否在列表中，否则自动选第一项 |
| T1.6 URL 状态持久化 | `frontend/src/App.tsx` | 用 URLSearchParams 同步 subIndex/period/itemGoodId，支持分享/刷新 |
| T1.7 添加 404 页面 | `frontend/src/pages/NotFound.tsx` | 替换兜底路由的 Dashboard |
| T1.8 前端 TypeScript 类型定义 | `frontend/src/types/csqaq.ts` | 为全部 25 个 CSQAQ API 响应定义 TypeScript 接口 |

### 第二阶段：K线图与走势预测增强（核心体验）

| 任务 | 文件 | 内容 |
|------|------|------|
| T2.1 K线图添加成交量 | `frontend/src/pages/ScenarioPage.tsx` | ECharts 双图布局：主图 candlestick + 副图 volume bar |
| T2.2 价位标注叠加 | `frontend/src/pages/ScenarioPage.tsx` | 用 markLine 标注支撑/阻力/目标/止损，用 markPoint 标注当前位置 + 价格数值 |
| T2.3 wave_sketch 波形图 | `frontend/src/components/WaveSketchChart.tsx` | 新建组件，将 wave_sketch 数据渲染为折线波形图 |
| T2.4 未来走势模拟K线 | `frontend/src/components/ForecastChart.tsx` | 新建组件：在历史K线右侧延伸模拟走势，2-4条情景用不同颜色，概率以透明度表示 |
| T2.5 接入历史相似 API | `frontend/src/pages/ScenarioPage.tsx` | 调用 `scenario.history`，展示历史相似片段及未来收益 |
| T2.6 接入模板匹配 API | `frontend/src/pages/ScenarioPage.tsx` | 调用 `scenario.templates`，展示匹配的经典图形成果 |
| T2.7 接入 AI 解释 API | `frontend/src/pages/ScenarioPage.tsx` | 调用 `scenario.explain`，展示自然语言情景解释 |

### 第三阶段：单品搜索与详情页（CSQAQ 饰品详情 API 集成）

| 任务 | 文件 | 内容 |
|------|------|------|
| T3.1 后端：搜索 suggest 端点 | `src/api/item_endpoints.py` | 封装 CSQAQ `/search/suggest`，新增 `POST /item/search` |
| T3.2 后端：全量饰品列表端点 | `src/api/item_endpoints.py` | 封装 CSQAQ `/goods/get_all_goods_id`，新增 `GET /item/all` |
| T3.3 后端：单品详情端点 | `src/api/item_endpoints.py` | 封装 CSQAQ `/info/good`，新增 `GET /item/detail?good_id=X`，返回 7 平台 50+ 字段 |
| T3.4 后端：单品图表端点 | `src/api/item_endpoints.py` | 封装 CSQAQ `/info/chart`，新增 `POST /item/chart`，支持 11 指标 × 4 平台 × 7 周期 |
| T3.5 后端：全量图表端点 | `src/api/item_endpoints.py` | 封装 CSQAQ `/info/simple/chartAll`，新增 `POST /item/chart-all` |
| T3.6 后端：存世量走势端点 | `src/api/item_endpoints.py` | 封装 CSQAQ `/info/good/statistic`，新增 `GET /item/supply?good_id=X` |
| T3.7 后端：批量价格端点 | `src/api/item_endpoints.py` | 封装 CSQAQ `/goods/getPriceByMarketHashName`，新增 `POST /item/batch-price`（≤50个） |
| T3.8 前端：饰品搜索页 | `frontend/src/pages/SearchPage.tsx` | 搜索框 + 实时联想（支持皮肤/武器/职业哥等特殊关键词） + 结果列表 + 点击跳转详情 |
| T3.9 前端：单品详情页 | `frontend/src/pages/ItemDetailPage.tsx` | 7 平台价格对比表 + 多指标 K 线图（11 指标切换） + 存世量走势图 + 租赁收益分析 + 挂刀比例展示 + 涨跌数据卡片 |
| T3.10 前端：全局搜索栏 | `frontend/src/components/ItemSearchBar.tsx` | 导航栏常驻搜索框，任何页面可快速搜索跳转 |
| T3.11 前端：多平台K线对比 | `frontend/src/components/MultiPlatformChart.tsx` | 4 平台 K 线叠加/切换对比组件 |
| T3.12 路由更新 | `frontend/src/App.tsx` | 添加 `/search` 和 `/item/:goodId` 路由 |

### 第四阶段：排行榜与饰品列表（CSQAQ 排行 API 集成）

| 任务 | 文件 | 内容 |
|------|------|------|
| T4.1 后端：排行榜端点 | `src/api/ranking_endpoints.py` | 封装 CSQAQ `/info/get_rank_list`，新增 `POST /rankings/list`，支持 30+ 排序维度和筛选 |
| T4.2 后端：饰品列表端点 | `src/api/ranking_endpoints.py` | 封装 CSQAQ `/info/get_page_list`，新增 `POST /rankings/items`，支持类型/品质/类别/磨损筛选 |
| T4.3 后端：热门系列列表端点 | `src/api/ranking_endpoints.py` | 封装 CSQAQ `/info/get_series_list`，新增 `POST /rankings/series` |
| T4.4 后端：热门系列详情端点 | `src/api/ranking_endpoints.py` | 封装 CSQAQ `/info/get_series_detail`，新增 `POST /rankings/series-detail` |
| T4.5 前端：排行榜页 | `frontend/src/pages/RankingsPage.tsx` | 30+ 维度排序选择器 + 分页 + 搜索 + 筛选 + 近30天走势迷你图 + 点击跳转单品详情 |
| T4.6 前端：饰品列表页 | `frontend/src/pages/ItemListPage.tsx` | 类型/品质/类别/磨损多级筛选面板 + 分页 + 搜索 + 卡片式展示 |
| T4.7 前端：热门系列页 | `frontend/src/pages/SeriesPage.tsx` | 系列卡片网格 + 涨跌幅色标 + 15天走势迷你图 + 系列类型分类（匕首/武器/印花/手套/其他） |
| T4.8 前端：系列详情页 | `frontend/src/pages/SeriesDetailPage.tsx` | 系列内全部饰品列表 + 价格对比 + 涨跌排行 |
| T4.9 路由更新 | `frontend/src/App.tsx` | 添加 `/rankings`、`/item-list`、`/series`、`/series/:seriesId` 路由 |

### 第五阶段：挂刀行情页（CSQAQ 挂刀 API 集成）

| 任务 | 文件 | 内容 |
|------|------|------|
| T5.1 后端：挂刀行情端点 | `src/api/exchange_endpoints.py` | 封装 CSQAQ `/info/exchange_detail`，新增 `POST /exchange/detail`，支持挂刀/反向挂刀、平台选择、价格/成交量筛选 |
| T5.2 前端：挂刀行情页 | `frontend/src/pages/ExchangePage.tsx` | 挂刀/反向挂刀模式切换 + 平台选择(BUFF/YYYP/双平台) + 出售方案选择 + 价格区间滑块 + 成交量筛选 + 搜索框 |
| T5.3 前端：套现比例排行表 | `frontend/src/components/ExchangeTable.tsx` | 套现比例排序表格 + 各平台价格对比 + Steam成交量 + 点击跳转单品详情 |
| T5.4 前端：挂刀计算器 | `frontend/src/components/ExchangeCalculator.tsx` | 输入饰品价格 → 自动计算各平台套现比例和利润 |
| T5.5 路由更新 | `frontend/src/App.tsx` | 添加 `/exchange` 路由 |

### 第六阶段：库存监控页（CSQAQ 库存监控 API 集成）

| 任务 | 文件 | 内容 |
|------|------|------|
| T6.1 后端：任务列表端点 | `src/api/monitor_endpoints.py` | 封装 CSQAQ `/monitor/get_task_list`，新增 `POST /monitor/tasks`，支持搜索和 5 种排序 |
| T6.2 后端：变动动态端点 | `src/api/monitor_endpoints.py` | 封装 CSQAQ `/monitor/get_task_trends`，新增 `POST /monitor/trends`，支持全站动态或按 good_id 筛选 |
| T6.3 后端：持有量排行端点 | `src/api/monitor_endpoints.py` | 封装 CSQAQ `/monitor/get_good_rank`，新增 `POST /monitor/good-rank` |
| T6.4 后端：用户信息端点 | `src/api/monitor_endpoints.py` | 封装 CSQAQ `/monitor/get_task_info`，新增 `POST /monitor/user-info` |
| T6.5 后端：用户动态端点 | `src/api/monitor_endpoints.py` | 封装 CSQAQ `/monitor/get_task_trends_detail`，新增 `POST /monitor/user-trends` |
| T6.6 后端：用户库存端点 | `src/api/monitor_endpoints.py` | 封装 CSQAQ `/task/get_task_all`，新增 `POST /monitor/user-inventory`，支持快照 ID |
| T6.7 后端：快照列表端点 | `src/api/monitor_endpoints.py` | 封装 CSQAQ `/monitor/get_snapshot_list`，新增 `POST /monitor/snapshots` |
| T6.8 前端：库存监控主页 | `frontend/src/pages/MonitorPage.tsx` | 任务列表（含搜索/排序）+ 最新变动动态流 + 变动类型图标和颜色标识 |
| T6.9 前端：监控用户详情页 | `frontend/src/pages/MonitorDetailPage.tsx` | 用户信息卡片 + 库存动态时间线 + 全部库存列表（分页）+ 快照列表 + 快照对比 |
| T6.10 前端：持有量排行组件 | `frontend/src/components/HoldingsRankTable.tsx` | 输入 good_id → 显示持有该饰品的用户排行 |
| T6.11 前端：库存变动类型标识 | `frontend/src/components/TrendTypeBadge.tsx` | 7 种变动类型（买入/卖出/存入/取出/CD恢复等）的颜色和图标标识 |
| T6.12 路由更新 | `frontend/src/App.tsx` | 添加 `/monitor` 和 `/monitor/:taskId` 路由 |

### 第七阶段：大盘指数增强与实时成交（CSQAQ 指数 + 成交 API 集成）

| 任务 | 文件 | 内容 |
|------|------|------|
| T7.1 后端：大盘指数扩展端点 | `src/api/market_endpoints.py` | 扩展 `/current_data` 使用，新增 `GET /market/overview` 和 `POST /market/data`（支持 hours/kline/lease 类型） |
| T7.2 后端：实时成交端点 | `src/api/volume_endpoints.py` | 封装 CSQAQ `/vol/current` 和 `/vol/detail`，新增 `GET /volume/current` 和 `GET /volume/detail`（标注暂停更新） |
| T7.3 前端：仪表盘全面增强 | `frontend/src/pages/Dashboard.tsx` | 子指数卡片网格（含涨跌幅色标）+ 涨跌分布图（按类型/价格区间）+ 在线人数实时显示 + 热门排行 Top10 + 快速导航 |
| T7.4 前端：子指数K线增强 | `frontend/src/pages/ScenarioPage.tsx` | K线图支持多周期切换(1h/4h/1d/7d) + 子指数切换时保持图表不闪烁 |
| T7.5 前端：实时成交页 | `frontend/src/pages/VolumePage.tsx` | 标注"数据暂停更新" + 展示历史成交量数据 + 单品成交量历史图表 |
| T7.6 前端：涨跌分布可视化 | `frontend/src/components/ChgDistributionChart.tsx` | 按类型（印花/步枪/匕首/手套等）和价格区间（大件/小件等）的涨跌分布柱状图 |
| T7.7 前端：在线人数组件 | `frontend/src/components/OnlineNumberCard.tsx` | 当前在线/今日峰值/本月峰值/月活/涨跌幅，自动刷新 |
| T7.8 路由更新 | `frontend/src/App.tsx` | 添加 `/volume` 路由 |

### 第八阶段：系统设置、数据导出与零命令行

| 任务 | 文件 | 内容 |
|------|------|------|
| T8.1 后端：设置管理端点 | `src/api/settings_endpoints.py` | `GET/POST /settings` 读写 .env 配置（apiToken, baseUrl 等） |
| T8.2 后端：IP 绑定端点 | `src/api/settings_endpoints.py` | 封装 CSQAQ `/sys/bind_local_ip`，新增 `POST /settings/bind-ip`（30秒频率限制提示） |
| T8.3 后端：服务控制端点 | `src/api/settings_endpoints.py` | `POST /settings/restart` 重启服务，`GET /settings/status` 健康检查 |
| T8.4 后端：数据导出端点 | `src/api/export_endpoints.py` | `POST /export/trades` 导出交易记录，`POST /export/scan` 导出扫描结果，`GET /export/report/:id` 下载报告 |
| T8.5 前端：设置页 | `frontend/src/pages/SettingsPage.tsx` | API Token 配置 + IP 绑定（一键绑定+频率提示）+ 缓存清理 + 服务重启 + 主题切换 |
| T8.6 前端：交易记录导出 | `frontend/src/pages/BacktestPage.tsx` | 导出 CSV/Excel：交易明细 + 权益曲线 |
| T8.7 前端：扫描结果导出 | `frontend/src/pages/TrendScanPage.tsx` | 导出 CSV：Top10/Bottom10 参数组合 |
| T8.8 前端：报告格式化展示 | `frontend/src/pages/ReportsPage.tsx` | JSON 美化 + 折叠树 + 下载 |
| T8.9 前端：策略参数自定义 | `frontend/src/pages/BacktestPage.tsx` | 可调参数面板：初始资金、止损比例、信号阈值等 |
| T8.10 前端：多平台价格对比表 | `frontend/src/components/PlatformPriceTable.tsx` | BUFF / 悠悠有品 / Steam / C5 / IGXE / ECOSteam / R8GAME 七平台价格对比 |
| T8.11 前端：租赁收益分析 | `frontend/src/components/LeaseAnalysisChart.tsx` | 短租/长租收益率图表 + 年化收益计算 + 过户底价展示 |
| T8.12 一键启动脚本 | `start.sh` / `start.bat` | 双击启动：检查环境 → 安装依赖 → 构建前端 → 启动服务 → 打开浏览器 |
| T8.13 路由更新 | `frontend/src/App.tsx` | 添加 `/settings` 路由 |

---

## 五、技术选型

| 领域 | 选型 | 理由 |
|------|------|------|
| 状态管理 | Zustand | 轻量（1KB），无 Provider 包裹，TypeScript 友好 |
| URL 同步 | zustand/middleware persist + URLSearchParams | 状态自动持久化到 URL |
| 请求取消 | AbortController + fetch signal | 浏览器原生 API，无额外依赖 |
| K线图表 | ECharts（已有） | 复用现有依赖，支持 markLine/markPoint/volume/双图布局 |
| 搜索联想 | 防抖 + AbortController | 300ms 防抖，可取消旧请求 |
| 数据导出 | 前端 Blob + CSV | 纯前端实现，无需后端支持 |
| 一键启动 | Shell/Bat 脚本 | 双击运行，检查环境并启动 |
| 筛选面板 | 自建组件 + Tailwind | 支持多级联动筛选（类型→具体型号） |

---

## 六、UI/UX 设计原则

1. **零命令行**：启动后所有操作（含 API Token 配置、服务重启、缓存管理、IP 绑定）均在前端完成
2. **全局搜索栏**：导航栏顶部常驻搜索框，任何页面可快速搜索饰品（支持特殊关键词如"杀猪刀""龙狙"等）
3. **状态一致性**：标的/周期/平台/图表指标选择全局同步，切换页面不丢失
4. **数据不闪烁**：切换参数时保留旧数据展示，新数据加载完成后平滑替换
5. **可视化优先**：能用图表展示的不用文字，能用标注的不用卡片
6. **色彩体系**：涨为红/跌为绿（符合国内习惯），变动类型用图标区分
7. **响应式布局**：关键功能在平板上可用
8. **空状态处理**：所有列表页在无数据时展示友好的空状态提示
9. **加载状态**：骨架屏 + 局部 loading，避免全屏白屏
10. **错误处理**：网络错误、API 限流、Token 过期等场景有明确提示

---

## 七、数据层级模型

```
大盘指数层（Market Index）
  ├── 子指数列表（手套/匕首/贴纸/步枪/百元主战...）
  │   └── 子指数K线（1h/4h/1d/7d 四种周期）
  ├── 涨跌分布
  │   ├── 按类型（印花/步枪/匕首/手套/手枪/微冲/其他）
  │   └── 按价格区间（大件/小件/中小件/中件/中大件）
  ├── 涨跌数量统计（1/7/15/30/90/180日 上涨/下跌/持平）
  └── 在线人数（当前/今日峰值/本月峰值/月活/涨跌幅）

单品层（Item / Goods）
  ├── 饰品搜索（名称联想，支持特殊关键词）
  ├── 全量饰品列表（ID→名称→hash名映射）
  ├── 单品详情
  │   ├── 7 平台价格（BUFF/YYYP/Steam/C5/IGXE/ECO/R8）
  │   ├── 租赁数据（短租/长租价格、收益率、在租量、过户底价）
  │   ├── 挂刀比例（Steam求购/在售挂刀比例、BUFF套现比例）
  │   ├── 涨跌数据（1/7/30/180日涨跌量和涨跌率）
  │   ├── 基础信息（磨损范围、品质、存世量、热度排名）
  │   └── Steam成交（成交量、成交均价）
  ├── 单品图表（11 指标 × 4 平台 × 7 周期）
  ├── 存世量走势（近180天）
  └── 批量价格查询（≤50个 marketHashName）

排行榜层（Ranking）
  ├── 全站排行（30+维度排序 + 近30天走势）
  ├── 饰品列表（类型/品质/类别/磨损筛选）
  └── 热门系列（涨跌幅 + 15天走势 + 系列详情）

挂刀行情层（Exchange）
  ├── 挂刀（平台买→Steam卖，获取Steam余额）
  └── 反向挂刀（Steam买→平台卖，获取平台余额）

库存监控层（Inventory Monitor）
  ├── 任务列表（搜索/排序）
  ├── 变动动态（全站/按饰品筛选）
  ├── 用户详情（信息/动态/库存/快照）
  └── 持有量排行（按饰品查询）

实时成交层（Volume，暂停更新）
  ├── 平台成交量
  └── 单品成交量历史
```

---

## 八、实施优先级与里程碑

| 里程碑 | 内容 | 预计工时 |
|--------|------|----------|
| M1 | 第一阶段：Bug 修复 + 基础设施 + TS类型定义 | 2天 |
| M2 | 第二阶段：K线增强 + 走势预测 | 3天 |
| M3 | 第三阶段：单品搜索 + 详情页（7个API集成） | 4天 |
| M4 | 第四阶段：排行榜 + 饰品列表 + 热门系列（4个API集成） | 3天 |
| M5 | 第五阶段：挂刀行情页（1个API集成） | 2天 |
| M6 | 第六阶段：库存监控页（7个API集成） | 4天 |
| M7 | 第七阶段：大盘指数增强 + 实时成交（5个API集成） | 2天 |
| M8 | 第八阶段：系统设置 + 导出 + 零命令行 | 2天 |

**总计约 22 个工作日，集成全部 25 个 CSQAQ API 端点，可按里程碑分批交付。**

---

## 九、验收标准

### Bug 修复验收
- [ ] 切换页面后标的/周期/平台保持不变
- [ ] 切换参数时无全屏闪烁（旧数据保留至新数据到达）
- [ ] 快速切换不会产生并发废请求（AbortController 生效）
- [ ] URL 状态持久化，刷新页面不丢失选择
- [ ] Select 组件值始终与选项列表匹配

### K线与走势预测验收
- [ ] K线图显示成交量副图
- [ ] K线图标注支撑/阻力/目标/止损水平线和当前位置标记
- [ ] 未来走势图在K线右侧显示2-4条模拟走势
- [ ] wave_sketch 渲染为波形图
- [ ] 历史相似片段和模板匹配结果正确展示
- [ ] AI 解释文本正确展示

### 单品搜索与详情验收
- [ ] 搜索框支持中文和特殊关键词（如"杀猪刀""龙狙"）
- [ ] 搜索结果实时联想，点击跳转单品详情
- [ ] 单品详情页显示 7 平台价格对比
- [ ] 单品图表支持 11 种指标 × 4 平台 × 7 周期切换
- [ ] 存世量走势图正确展示近 180 天数据
- [ ] 批量价格查询支持 ≤50 个饰品

### 排行榜与列表验收
- [ ] 排行榜支持 30+ 维度排序
- [ ] 排行榜支持搜索和分页
- [ ] 排行榜可显示近 30 天价格走势迷你图
- [ ] 饰品列表支持类型/品质/类别/磨损四级筛选
- [ ] 热门系列页显示涨跌幅和 15 天走势
- [ ] 系列详情页展示系列内全部饰品

### 挂刀行情验收
- [ ] 支持挂刀/反向挂刀模式切换
- [ ] 支持平台选择（BUFF/YYYP/双平台）
- [ ] 支持价格区间和成交量筛选
- [ ] 套现比例排行表正确展示
- [ ] 点击饰品可跳转单品详情

### 库存监控验收
- [ ] 任务列表支持搜索和 5 种排序方式
- [ ] 变动动态展示 7 种变动类型（图标和颜色区分）
- [ ] 用户详情页展示信息/动态/库存/快照
- [ ] 全部库存支持分页和快照对比
- [ ] 持有量排行按饰品查询正确

### 大盘指数验收
- [ ] 仪表盘展示子指数卡片网格和涨跌幅
- [ ] 涨跌分布图按类型和价格区间展示
- [ ] 在线人数实时显示
- [ ] 子指数K线支持多周期切换

### 系统设置与导出验收
- [ ] API Token 可在前端设置页配置
- [ ] IP 绑定一键操作且有频率限制提示
- [ ] 交易记录可导出 CSV/Excel
- [ ] 扫描结果可导出 CSV
- [ ] 报告可格式化展示和下载
- [ ] 双击启动脚本即可运行整个平台
- [ ] 全部操作在前端完成，无需命令行

### API 覆盖率验收
- [ ] 25 个 CSQAQ API 端点全部集成
- [ ] 7 个后端端点文件全部创建
- [ ] 13 个前端页面全部实现
- [ ] 实时成交页标注"暂停更新"状态
