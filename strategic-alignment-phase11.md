# 第十一阶段战略-战术对齐检查报告

**阶段主题：** 预定义模式模板库轨道  
**检查日期：** 2026-07-27  
**对应战术文档：** [tactical-document-phase11.md](computer:///workspace/tactical-document-phase11.md)  
**前置报告：** [strategic-alignment-phase10.md](computer:///workspace/csqaq-glove-quant/strategic-alignment-phase10.md)

---

## 1. 阶段目标完成情况

| 目标 | 状态 | 交付物 |
|------|------|--------|
| 设计模板 DSL | 已完成 | `config/scenario_template_schema.json` |
| 实现模板匹配引擎 | 已完成 | `src/scenario_engine/template_matcher.py` |
| 实现三浪延伸与五浪推动模板 | 已完成 | `config/scenario_templates/wave_extension.json`、`config/scenario_templates/five_wave_impulse.json` |
| 实现三角整理与旗形整理模板 | 已完成 | `config/scenario_templates/triangle_consolidation.json`、`config/scenario_templates/flag_consolidation.json` |
| 实现头肩底 / 顶与双底 / 双顶模板 | 已完成 | `config/scenario_templates/head_and_shoulders.json`、`config/scenario_templates/double_bottom_top.json` |
| 实现模板动态权重 | 已完成 | `src/scenario_engine/template_weights.py` |
| 模板历史回测验证 | 已完成 | `generate_phase11_report.py`、`reports/phase11_template_backtest.json` |
| 单元测试与双环境校验 | 已完成 | `tests/scenario_engine/test_template_matcher.py`、`tests/scenario_engine/test_template_weights.py` |
| 战略-战术对齐检查 | 已完成 | 本报告 |

---

## 2. 核心实验结果

### 2.1 验证数据集

| 子指数 | K 线数量 | 起始时间 | 结束时间 |
|--------|---------|---------|---------|
| 手套 | 938 | 2024-01-01 | 2026-07-26 |
| 匕首 | 938 | 2024-01-01 | 2026-07-26 |
| 百元主战 | 938 | 2024-01-01 | 2026-07-26 |
| 贴纸 | 938 | 2024-01-01 | 2026-07-26 |

### 2.2 模板库回测摘要（四个子指数汇总）

| 模板 | 匹配次数 | 平均置信度 | 5 日胜率 | 10 日胜率 | 20 日胜率 | 平均有向收益（20 日） |
|------|---------|-----------|---------|----------|-----------|---------------------|
| `wave_extension_bullish` | 134 | 0.9575 | 0.6418 | 0.5448 | 0.5075 | 0.001350 |
| `wave_extension_bearish` | 62 | 0.9442 | 0.6452 | 0.5968 | 0.6452 | 0.065691 |
| `five_wave_impulse_bullish` | 6 | 0.8877 | 0.6667 | 0.6667 | 0.8333 | 0.102350 |
| `five_wave_impulse_bearish` | 27 | 0.9396 | 0.7037 | 0.7778 | 0.8148 | 0.054397 |
| `triangle_bullish` | 136 | 1.0000 | 0.6250 | 0.5588 | 0.5882 | 0.021039 |
| `triangle_bearish` | 50 | 1.0000 | 0.8000 | 0.6400 | 0.6200 | 0.038554 |
| `flag_bullish` | 102 | 0.9534 | 0.6373 | 0.5686 | 0.6176 | 0.005547 |
| `flag_bearish` | 97 | 0.9470 | 0.5979 | 0.6598 | 0.6392 | 0.059962 |
| `head_and_shoulders_top` | 20 | 1.0000 | 0.5000 | 0.6500 | 0.7000 | 0.019913 |
| `head_and_shoulders_bottom` | 7 | 1.0000 | 0.8571 | 0.8571 | 0.5714 | -0.009819 |
| `double_bottom_bullish` | 363 | 1.0000 | 0.6832 | 0.6474 | 0.6419 | 0.022078 |
| `double_top_bearish` | 258 | 1.0000 | 0.5310 | 0.5620 | 0.5504 | 0.012207 |

> 说明：回测基于 `min_confidence=0.5`， horizons 为 5 / 10 / 20 根 K 线，收益按模板方向折算（多头取原始收益，空头取反向收益）。

---

## 3. 验收标准检查

| 编号 | 验收项 | 结果 | 说明 |
|------|--------|------|------|
| AC79 | 模板 DSL 完整 | 通过 | Schema 覆盖结构条件、价格条件、时间条件、推演规则四类定义 |
| AC80 | 至少 6 种核心模板 | 通过 | 实现 6 种基础模板，共 12 个方向变体 |
| AC81 | 模板输出包含关键价位 | 通过 | 每个匹配结果包含 `support`、`resistance`、`target`、`stop_loss`、`probability_prior` |
| AC82 | 模板动态权重可调 | 通过 | `compute_template_weights(market_state)` 支持 `uptrend`/`downtrend`/`choppy`，权重可配置、可归一化 |
| AC83 | 模板历史回测方向胜率 ≥50% | 通过 | 所有模板主要方向在 5 / 10 / 20 日 horizons 上均 ≥50%；`five_wave_impulse_bullish` 样本仅 6 次，胜率虽达标但统计意义有限 |
| AC84 | 无成交量依赖 | 通过 | 新增代码未读取 `volume` |
| AC85 | 子指数可迁移 | 通过 | 切换子指数仅需修改配置或命令行参数，板块名称未硬编码在模板/引擎中 |
| AC86 | 双环境兼容 | 通过 | `pytest` 202 项全部通过 |
| AC87 | 波浪理论合规 | 通过 | 三浪延伸、五浪推动模板在 `rules` 与结构条件中明确体现艾略特波浪基本规则 |

---

## 4. 战略对齐检查

| 检查项 | 是否对齐 | 说明 |
|--------|---------|------|
| 框架无硬编码标的 | 是 | 模板配置与子指数无关，仅依赖 OHLC 与时间 |
| 不使用成交量 | 是 | 模板条件仅基于 `open` / `high` / `low` / `close` 与 K 线索引 |
| 核心判断去 LLM 化 | 是 | 形态识别、权重调整、回测统计均由算法输出 |
| 多子指数可迁移 | 是 | 切换子指数仅需配置 |
| 双环境可运行 | 是 | 验收 AC86 |

---

## 5. 未达标项根因与后续建议

1. **五浪推动（多头）样本稀少**
   - 全部四个子指数仅匹配 6 次，虽然胜率达标但置信区间较宽。
   - 根因：完整五浪结构在日线级别出现频率低，且突破第 5 浪高点的确认条件较严。
   - 建议：Phase 12 可将其作为低先验、高赔率的“强信号”模板，与 KNN/聚类结果做贝叶斯融合时降权使用；或在更短周期（如 4h）上补充样本。

2. **头肩形 / 双顶底模板对 Swing 检测参数敏感**
   - 子指数间匹配次数差异大（如 `head_and_shoulders_bottom` 在部分子指数仅 1-2 次）。
   - 根因：这些形态对左右肩/底的对称性要求较高，当前 `swing_order=2` 的局部极值检测在波动率差异大的板块上表现不一致。
   - 建议：Phase 12 引入自适应 Swing 窗口或模糊匹配，进一步提升跨板块稳定性。

3. **胜率统计未考虑交易成本与滑点**
   - 当前为方向胜率与毛收益，未扣除手续费、滑点与冲击成本。
   - 建议：Phase 12 融合阶段使用 `src/backtest/engine.py` 进行带成本的精细化回测。

---

## 6. 关键变更文件

- `config/scenario_template_schema.json`
- `config/scenario_templates/wave_extension.json`
- `config/scenario_templates/five_wave_impulse.json`
- `config/scenario_templates/triangle_consolidation.json`
- `config/scenario_templates/flag_consolidation.json`
- `config/scenario_templates/head_and_shoulders.json`
- `config/scenario_templates/double_bottom_top.json`
- `src/scenario_engine/template_matcher.py`
- `src/scenario_engine/template_weights.py`
- `generate_phase11_report.py`
- `tests/scenario_engine/test_template_matcher.py`
- `tests/scenario_engine/test_template_weights.py`
- `reports/phase11_template_backtest.json`

---

## 7. 结论

第十一阶段完成了预定义模式模板库轨道：定义了可扩展的模板 DSL，实现了 6 类核心价格形态（含 12 个方向变体）的自动识别、动态权重调整与历史回测验证。所有模板均满足“不使用成交量、不硬编码板块、输出关键价位”的约束，`pytest` 全部通过。建议在第十二阶段将本轨道与 Phase 10 的历史相似性搜索轨道进行贝叶斯融合，形成双轨情景预判引擎。
