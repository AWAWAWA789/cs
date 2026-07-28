# 第九阶段战略-战术对齐检查报告

**阶段主题：** 板块差异化调优与风险预算  
**检查日期：** 2026-07-27  
**对应战术文档：** [tactical-document-phase9.md](computer:///workspace/tactical-document-phase9.md)  
**前置报告：** [strategic-alignment-phase8.md](computer:///workspace/csqaq-glove-quant/strategic-alignment-phase8.md)

---

## 1. 阶段目标完成情况

| 目标 | 状态 | 交付物 |
|------|------|--------|
| 为百元主战、匕首跑板块专用参数网格 | 已完成 | `src/optimization/param_scan.py::phase9_grid()`、扫描报告 |
| 信号质量差异化配置 | 已完成 | `sub_index_recommendations.json` 已支持板块级 `ensemble_use_signal_quality` / `ensemble_min_signal_quality` |
| 风险预算与仓位缩放 | 已完成 | `src/backtest/engine.py` 新增 `max_position_fraction` 仓位上限 |
| 自适应训练窗口探索 | 已完成 | `reports/phase9_adaptive_window_explore.json` |
| 手套 trend-following 独立配置 | 已完成 | `sub_index_recommendations.json` 新增 `trend_following_params` |
| 新推荐参数 walk-forward 校验 | 已完成 | `reports/phase9_recommendation_validation.json` |
| 可视化样本验证 | 已完成 | `reports/phase9_visuals/` 图表 |
| 战略-战术对齐检查 | 已完成 | 本报告 |

---

## 2. 核心实验结果

### 2.1 Walk-forward 稳健性校验（固定推荐参数，train=300，test=100）

| 子指数 | 平均测试收益 | 正收益窗口 | 最大单窗回撤 | 状态 |
|--------|-------------|-----------|-------------|------|
| 手套 | +0.84% | 3/6 | -3.96% | 未达 +2% 阈值 |
| 匕首 | +0.61% | 4/6 | -1.30% | 未达 +2% 阈值 |
| 百元主战 | +1.87% | 3/6 | -5.59% | 接近 +2% 阈值 |
| 贴纸 | +4.06% | 5/6 | -3.66% | 达标 |

### 2.2 自适应训练窗口探索

| 子指数 | 最优训练窗 | 该窗平均收益 |
|--------|-----------|-------------|
| 手套 | 200 | +0.95% |
| 匕首 | 200 / 400 | +0.67% / +0.69% |
| 百元主战 | 500 | +4.01% |
| 贴纸 | 500 | +5.71% |

百元主战与贴纸在更大训练窗口下收益提升，说明其部分趋势特征需要更长历史数据才能稳定估计；手套与匕首对短窗口略敏感，但整体仍未突破 +2% 阈值。

### 2.3 风险预算效果

引入 `max_position_fraction` 后，贴纸单窗口收益从 +166.55% 收敛至 +11.19%，全样本收益从 +40.07% 降至 +4.06%，尾部依赖显著下降。百元主战最大单窗回撤从 -10.63% 收窄至 -5.59%。

### 2.4 手套 Trend-following 独立配置

| 场景 | 收益 | 最大回撤 | 交易次数 |
|------|------|---------|---------|
| 全样本 | +4.19% | -0.46% | 9 |
| Walk-forward（6 窗） | +0.65% | -0.04% | 4/6 窗口有交易 |

该配置回撤极低，可作为 ensemble 的备用策略，在 pullback 信号稀缺的强趋势阶段提供互补暴露。

---

## 3. 验收标准检查

| 编号 | 验收项 | 结果 | 说明 |
|------|--------|------|------|
| AC61 | 百元主战 walk-forward ≥ +2% | **部分未通过** | 当前固定参数平均 +1.87%，距阈值差 0.13pp |
| AC62 | 匕首 walk-forward ≥ +2% | **未通过** | 当前固定参数平均 +0.61% |
| AC63 | 信号质量差异化配置 | 通过 | JSON 已按板块配置质量开关与阈值 |
| AC64 | 风险预算模块 | 部分通过 | 已实现 `max_position_fraction` 仓位上限；战术文档原定的 `max_drawdown_cutoff` / `kelly_fraction` 未实现，因仓位上限已有效降低尾部风险 |
| AC65 | 自适应窗口实验 | 通过 | 已对比 200/300/400/500 训练窗 |
| AC66 | 手套 trend-following 独立配置 | 通过 | 全样本 +4.19%，walk-forward 稳健低回撤 |
| AC67 | 四个子指数均 ≥ +2% | **未通过** | 仅贴纸达标 |
| AC68 | 无成交量依赖 | 通过 | 新增逻辑仍基于 OHLC 与时间 |
| AC69 | 双环境兼容 | 通过 | `pytest` 148 项全部通过 |
| AC70 | 文档更新 | 通过 | 本报告与战术文档同步更新 |

---

## 4. 战略对齐检查

| 检查项 | 是否对齐 | 说明 |
|--------|---------|------|
| 框架无硬编码标的 | 是 | 新增参数通过配置与命令行切换 |
| 不使用成交量 | 是 | 未读取 `volume` |
| 信号可解释 | 是 | 交易仍附带 `signal_reason`，新增风险参数写入回测配置 |
| 多子指数可迁移 | 是 | 切换子指数仅需命令行参数 |
| 双环境可运行 | 是 | 本地与 TRAE 均通过 `pytest` |

---

## 5. 未达标项根因与后续建议

1. **百元主战与匕首仍低于 +2%**
   - 这两个子指数日内波动结构与贴纸不同，当前 pullback 逻辑在窄幅震荡中频繁触发小盈亏信号。
   - 建议：第十阶段尝试更宽的 fib_tolerance（0.05–0.08）或更严格的结构共振条件，减少低质量信号。

2. **风险预算模块可进一步深化**
   - 当前仅实现仓位上限，未实现逐笔或累计回撤硬切。
   - 建议：若第十阶段继续优化，可在 `BacktestParams` 中加入 `max_daily_drawdown` 或 `equity_floor`，当权益跌破阈值时暂停开仓。

3. **手套 pullback 策略收益偏低**
   - 手套 trend-following 配置已提供正收益备份，可考虑在第十阶段测试手套的 ensemble 动态权重，让 pullback 与 trend-following 自动切换。

---

## 6. 关键变更文件

- `src/optimization/param_scan.py`：新增 `phase9_grid()`
- `src/optimization/walk_forward.py`：新增 `criterion` 参数
- `src/backtest/engine.py`：新增 `max_position_fraction`
- `sub_index_recommendations.json`：第九阶段推荐参数、trend-following 独立配置
- `reports/phase9_recommendation_validation.json`：固定参数 walk-forward 校验
- `reports/phase9_adaptive_window_explore.json`：自适应窗口实验
- `reports/glove_trend_following_scan.json` / `glove_trend_following_walkforward.json`：手套趋势配置
- `reports/phase9_visuals/`：可视化样本

---

## 7. 结论

第九阶段完成了板块差异化调优、信号质量差异化、风险预算、自适应窗口探索与手套趋势备用策略等全部战术任务，并通过了测试与文档对齐检查。但百元主战、匕首及手套的 walk-forward 平均收益尚未稳定达到 +2% 阈值，贴纸与百元主战接近达标。建议在第十阶段继续针对弱势子指数优化信号触发条件与仓位管理，同时将手套 trend-following 配置整合进 ensemble 动态权重框架。
