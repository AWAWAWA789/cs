# 第八阶段战略-战术对齐检查报告

> **对应战略文档：** [strategic-document.md](computer:///workspace/strategic-document.md)  
> **对应战术文档：** [tactical-document-phase8.md](computer:///workspace/tactical-document-phase8.md)  
> **阶段周期：** 2026-07-29 至 2026-08-08  
> **检查日期：** 2026-07-27  
> **前置报告：** [strategic-alignment-phase7.md](computer:///workspace/csqaq-glove-quant/strategic-alignment-phase7.md)

---

## 检查结论

第八阶段战术目标**部分完成**。代码实现、测试与可视化验证均已落地，`sub_index_recommendations.json` 已更新为第八阶段参数；但 walk-forward 稳健性校验显示 **百元主战** 与 **匕首** 两个子板块的平均样本外收益仍未达到 AC57 设定的 `≥ +2%` 阈值，需在下一阶段继续攻坚。

---

## 战术目标完成情况

| 任务 | 状态 | 关键交付 | 说明 |
|------|------|----------|------|
| T60 修复百元主战 walk-forward 失效 | 部分完成 | `reports/walkforward_phase8_百元主战_1d.json` | 平均测试收益从 -0.15% 提升至 +1.03%，但未达 AC53 的 +2% |
| T61 优化 trend-following 独立收益 | 完成 | `reports/quick_trend_scan_glove.json` | 手套子指数 trend-following 独立收益达到 +2.57%，满足 AC54 |
| T62 动态权重与信号质量参数入格 | 完成 | `src/optimization/param_scan.py` 新增 `ensemble_grid()` | 扫描 `dynamic_weight` 范围、ADX 缩放与 `signal_quality` 阈值 |
| T63 更新板块自适应推荐参数 | 完成 | `sub_index_recommendations.json` | 已写入第八阶段稳健参数及 walk-forward 元数据 |
| T64 新推荐参数 walk-forward 校验 | 部分完成 | `reports/walkforward_phase8_*.json`（4 个板块） | 手套、贴纸达标；百元主战、匕首未达标 |
| T65 可视化样本验证 | 完成 | `reports/phase8_samples/` | 手套与百元主战交易标注图、权益曲线、regime 诊断文件 |
| T66 战略-战术对齐检查 | 完成 | 本报告 | 记录阶段成果、未达标项与下一阶段方向 |

---

## 验收标准对照

| 编号 | 验收项 | 判定标准 | 实际结果 | 状态 |
|------|--------|---------|---------|------|
| AC53 | 百元主战 walk-forward 修复 | 平均测试收益 ≥ +2% | +1.03% | ❌ 未达标 |
| AC54 | trend-following 独立收益改善 | 至少一个子指数上独立收益 ≥ 0% | 手套 +2.57% | ✅ 达标 |
| AC55 | ensemble 严格优于 pullback | 至少一个子指数上 ensemble 收益严格高于 pullback 单独收益 | 已通过 `ensemble_grid()` 扫描验证，手套/贴纸存在 ensemble 更优参数 | ✅ 达标 |
| AC56 | 动态权重参数校准 | `dynamic_weight` 模式参数经过扫描，且在至少一个子指数上收益高于默认 `regime_switch` | `ensemble_grid()` 已覆盖；扫描结果中存在 dynamic_weight 更优组合 | ✅ 达标 |
| AC57 | 推荐参数稳健性 | 四个子指数 walk-forward 平均测试收益均 ≥ +2% | 手套 +2.65%、贴纸 +12.79% 达标；百元主战 +1.03%、匕首 +0.50% 未达标 | ❌ 未达标 |
| AC58 | 无成交量依赖 | 新增脚本、特征、回测逻辑仍不读取 `volume` | `run_trend_scan.py`、`ensemble_grid()` 均未引用 volume | ✅ 达标 |
| AC59 | 双环境兼容 | 同一版本代码在本地和 TRAE 中均能通过 `pytest` 全部测试 | 148 passed in 3.40s | ✅ 达标 |
| AC60 | 文档更新 | `strategic-alignment-phase8.md` 完成，且战术文档状态更新为已完成 | 本报告已生成；战术文档状态已更新 | ✅ 达标 |

**阶段验收结果：5/8 项完全达标，2 项部分达标，2 项（AC53、AC57）未达标。**

---

## 核心改动说明

### 1. 针对百元主战修复 walk-forward 失效

- 在 `/data/user/work/ensemble_walkforward.py` 中构建针对百元主战的精简网格，固定 pullback 基线，仅扫描 ensemble 模式、ADX 阈值与信号质量开关。
- 将训练窗口从 200 根 K 线扩大到 **300 根 K 线**，选择标准从总收益改为 **Sharpe 比率**，以降低对少数高波动窗口的过拟合。
- 百元主战专用基线参数：`swing_order=1`、`tp_target=1.272`，相比默认参数显著降低入场门槛并提前止盈，改善样本外胜率。

### 2. trend-following 独立收益优化

- 新增独立扫描脚本 `run_trend_scan.py`，对手套子指数系统扫描 DI 过滤、波动率过滤、回踩确认、ADX 阈值等 9 维参数组合。
- 最优组合为：`swing_order=1`、`use_pullback_confirmation=True`，其余过滤关闭，取得 **+2.57%** 全样本收益、胜率 60%、最大回撤 -2.04%。
- 结论：trend-following 在手套样本上可以作为独立策略运行，验证了第七阶段模块重构的有效性。

### 3. ensemble 动态权重与信号质量参数网格

- `src/optimization/param_scan.py` 新增 `ensemble_grid()`，固定 pullback 参数基线，扫描：
  - `ensemble_mode`: `regime_switch` / `union` / `dynamic_weight`
  - `ensemble_adx_threshold`: 20.0 / 25.0 / 30.0
  - `ensemble_regime_confirmations`: 2 / 4 / 6
  - `ensemble_dynamic_weight_min/max`: (0.1,0.5) / (0.2,0.8) / (0.3,0.7)
  - `ensemble_dynamic_weight_adx_scale`: 20.0 / 25.0 / 30.0
  - `ensemble_use_signal_quality`: True / False
  - `ensemble_min_signal_quality`: 0.0 / 0.3 / 0.5
- 通过命令行 `--grid ensemble` 可直接调用该网格，CLI 入口已同步更新。

### 4. 推荐参数文件更新

- `sub_index_recommendations.json` 已更新为第八阶段参数，并为每个子指数增加 `phase8_walkforward` 元数据：
  - 平均样本外收益
  - 正收益窗口数
  - 来源报告文件名

---

## Walk-forward 稳健性结果

使用 `sub_index_recommendations.json` 中的第八阶段推荐参数，窗口设置为 **train 300 / test 100 / step 100**，选择标准为 **Sharpe 比率**，结果如下：

| 子板块 | 窗口数 | 平均测试收益 | 正收益窗口 | 评估 |
|--------|--------|--------------|------------|------|
| 手套 | 6 | +2.65% | 3/6 | 稳健，达到 AC57 阈值 |
| 匕首 | 6 | +0.50% | 2/6 | 未达标，样本外波动大 |
| 百元主战 | 6 | +1.03% | 2/6 | 较第七阶段 -0.15% 明显改善，但仍低于 +2% |
| 贴纸 | 6 | +12.79% | 2/6 | 收益极高，但正收益窗口占比偏低，收益集中于个别窗口 |

**说明**：
- 训练窗口扩大至 300 后，模型对近期市场结构变化的敏感度下降，百元主战与匕首在两个连续窗口中出现回撤。
- 贴纸平均收益极高主要由 600–700 窗口的 +134% 级别收益驱动，收益分布极不均匀，存在尾部依赖风险。
- 正收益窗口占比未纳入验收标准，但可作为下一阶段风险预算分配的参考。

---

## 样本可视化验证

已使用 `run_ensemble.py` 与可视化模块生成手套、百元主战样本：

- `reports/phase8_samples/ensemble_手套_1day_trades.png`
- `reports/phase8_samples/ensemble_手套_1day_equity_curve.png`
- `reports/phase8_samples/ensemble_百元主战_1day_trades.png`
- `reports/phase8_samples/ensemble_百元主战_1day_equity_curve.png`
- 对应 regime 诊断 JSON：`ensemble_手套_1d_regime.json`、`ensemble_百元主战_1d_regime.json`

可视化确认：
- `dynamic_weight` 模式下趋势权重随 ADX 变化正常。
- 信号质量过滤可通过 CLI 开关控制，低质量信号被正确剔除。
- 交易标注图可区分 pullback / trend-following / ensemble 信号来源。

---

## 测试状态

全量测试通过：

```text
148 passed in 3.40s
```

新增/修改代码均已由既有测试覆盖，未引入回归。关键验证点包括：

- `test_ensemble.py`：dynamic_weight 模式、信号质量过滤。
- `test_param_scan.py`：默认网格与 ensemble 网格均可正常构建。
- `test_trend_following*.py`：波动率、DI、回踩确认过滤。
- `test_walk_forward.py`：walk-forward 框架在多参数下正常运行。

---

## 风险与下一步

### 已暴露风险

1. **百元主战与匕首仍未达稳健阈值**：AC53 与 AC57 未完全达成，说明当前参数对这两个板块的市场微观结构适配不足。
2. **贴纸收益分布不均**：虽然平均值极高，但高度依赖单个窗口，实盘Deploy时仓位管理需特别谨慎。
3. **训练窗口扩大带来的滞后性**：300 根 K 线训练窗可能错过快速切换的市场状态，需在第九阶段探索自适应窗口或在线学习机制。

### 下一阶段建议（第九阶段方向）

1. **板块专用参数细化**：为百元主战、匕首单独跑更小粒度、更长周期的网格，重点扫描 `tp_target`、`stop_loss_buffer`、`ensemble_min_signal_quality`。
2. **引入信号质量过滤的板块差异化**：仅对百元主战/匕首启用 `min_signal_quality ≥ 0.3–0.5`，其他板块保持关闭，避免误删高盈利信号。
3. **ensemble 仓位/风险预算**：对贴纸等收益波动大的板块增加最大回撤约束或 Kelly 仓位缩放。
4. **在线/滚动参数更新**：探索更短的滚动训练窗口或状态切换检测，减少 300 窗口的滞后问题。
5. **趋势跟随独立策略实盘化**：基于 `run_trend_scan.py` 的最优参数，为手套子指数单独准备一份 trend-following 配置，作为 ensemble 的备用策略。

---

## 战略对齐

| 检查项 | 是否对齐战略 | 说明 |
|--------|-------------|------|
| 框架无硬编码标的 | 对齐 G1 | 所有新增扫描脚本均通过 `--sub-index` 或环境变量切换标的 |
| 不使用成交量 | 对齐 G3 | 新增 trend-following 扫描与 ensemble 网格均未引用 `volume` |
| 信号可解释 | 对齐 G3 | 每笔交易仍附带 `signal_reason`，可视化保留信号来源颜色标注 |
| 多子指数可迁移 | 对齐 G1 | 切换子指数仅需修改 CLI 参数或 `.env` 中的 `SUB_INDEX_NAME` |
| 双环境可运行 | 对齐 G4 | 已通过 AC59：`pytest` 148 项全部通过 |
| 风险管理闭环 | 对齐 G2 | walk-forward 暴露板块差异，风险预案与下一阶段计划已明确 |

---

## 修订记录

| 版本 | 日期 | 修订内容 | 修订人 |
|-----|------|---------|--------|
| v1.0 | 2026-07-27 | 初始完成第八阶段对齐检查 | AI Assistant |
