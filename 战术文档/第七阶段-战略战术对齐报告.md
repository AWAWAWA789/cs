# 第七阶段战略-战术对齐检查报告

## 检查结论

第七阶段战术目标已按计划完成，代码实现与测试均通过， walk-forward 稳健性校验显示推荐参数在三个子板块上保持正收益，但百元主战出现轻微负收益，需作为第八阶段重点观察对象。

## 战术目标完成情况

| 任务 | 状态 | 关键交付 |
|------|------|----------|
| T53 重构 trend-following 模块 | 完成 | `trend_following.py` / `trend_following_strategy.py` 新增波动率过滤、DI 过滤、回踩确认 |
| T54 优化 ensemble 切换逻辑 | 完成 | `ensemble.py` 新增 `dynamic_weight` 模式与动态权重参数 |
| T55 信号质量评分机制 | 完成 | `signal_quality.py` 扩展趋势一致性、结构共振、概念共振三维评分；`signal.py` 与 `ensemble.py` 接入阈值过滤 |
| T56 推荐参数 walk-forward 校验 | 完成 | `reports/walkforward_recommendations_phase7.json` |
| T57 可视化样本验证 | 完成 | `reports/phase7_samples/ensemble_手套_1day_*.png` |
| T58 对齐检查与提交 | 完成 | 本报告 + git 提交 |

## 核心改动说明

### 1. trend-following 模块重构

- 在 `add_trend_following_features` 中新增：
  - `use_volatility_filter`：要求突破幅度超过 `volatility_atr_multiplier * ATR`，过滤震荡市中的微小假突破。
  - `use_di_filter`：要求 `DI+ > DI-`，确保仅做多方向主导的行情。
  - `use_pullback_confirmation`：突破后等待回踩确认，避免买在突破顶点。
- `trend_strength.py` 的 `average_directional_index` 现在返回 `adx, di_plus, di_minus, atr` 四元组，为波动率过滤提供 ATR。

### 2. ensemble 动态权重

新增 `dynamic_weight` 模式，趋势跟踪权重随 ADX 与 regime 状态线性变化：

- 非上升趋势：权重固定为最小值（默认 0.2）。
- 上升趋势：权重 = `weight_min + min(1, ADX / adx_scale) * (weight_max - weight_min)`。

该模式在强趋势市自动提高 trend-following 权重，在弱趋势市回退到 pullback。

### 3. 信号质量评分

`signal_quality.py` 中 `add_signal_quality_features` 综合三项评分：

- 趋势一致性（40%）：ADX 高低与 +DI/-DI 方向。
- 结构共振（40%）：收盘价与信号锚定 swing low 的距离。
- 概念共振（20%）：同一根 K 线上是否同时触发 Fibonacci 回调、Smart Money、趋势突破等多重逻辑。

`SignalParams` 与 `EnsembleParams` 均新增 `use_signal_quality` 与 `min_signal_quality`，低质量信号会被过滤。

## Walk-forward 稳健性结果

使用 `sub_index_recommendations.json` 中的推荐参数，窗口设置为 train 200 / test 100 / step 100，结果如下：

| 子板块 | 窗口数 | 平均测试收益 | 正收益窗口 | 评估 |
|--------|--------|--------------|------------|------|
| 手套 | 7 | 3.64% | 4/7 | 稳健，多数窗口盈利 |
| 匕首 | 7 | 2.01% | 5/7 | 稳健 |
| 百元主战 | 7 | -0.15% | 3/7 | 轻微失效，需重点关注 |
| 贴纸 | 7 | 34.35% | 6/7 | 非常强劲 |

说明：推荐参数在第六阶段基于全样本优化得到，第七阶段 walk-forward 显示其在手套、匕首、贴纸上具有样本外稳健性；百元主战的参数在 2024-2025 年部分窗口出现回撤，下一阶段可尝试降低仓位或启用信号质量过滤。

## 样本可视化验证

已使用 `run_ensemble.py` 生成 手套 1day 的对比样本：

- `regime_switch` 与 `union` 模式图表已保存至 `reports/phase7_samples/`。
- `dynamic_weight` 模式图表验证切换逻辑可正常工作。
- 新增趋势过滤参数（DI、波动率、回踩确认）可通过 CLI 开关启用。

## 测试状态

全量测试通过：

```text
148 passed in 3.46s
```

新增测试覆盖：

- `test_trend_following.py`：波动率过滤、DI 过滤、回踩确认。
- `test_trend_following_strategy.py`：回踩确认信号。
- `test_ensemble.py`：dynamic_weight 模式、信号质量过滤。
- `test_signal_quality.py`：质量评分、最小阈值过滤。
- `test_trend_strength.py`：更新为四元组返回值并校验 ATR。

## 风险与下一步

1. **百元主战参数失效风险**：walk-forward 显示平均收益为负，下一阶段应优先为该子板块启用信号质量过滤或重新扫描参数。
2. **trend-following 独立收益仍为负**：在 手套 样本中，启用全部过滤后 trend-following 独立收益为 -6.39%，说明需要更细粒度的参数搜索或限制 trend-following 仓位权重。
3. **动态权重参数未优化**：当前 `dynamic_weight_min=0.2, max=0.8, adx_scale=25` 为默认值，下一阶段可纳入参数扫描。
4. **信号质量权重可优化**：当前 0.4/0.4/0.2 为经验值，建议第八阶段通过网格搜索校准。

## 战略对齐

- 与阶段目标一致：通过过滤与确认机制降低假突破，通过动态权重与质量评分让 ensemble 在强趋势市真正启用 trend-following。
- 与风险管理一致：walk-forward 暴露的板块差异为下一阶段的风险预算分配提供依据。
- 与工程规范一致：所有改动均附带测试，CLI 入口已同步更新。
