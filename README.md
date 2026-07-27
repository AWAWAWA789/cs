# CSQAQ 饰品市场纯价格行为量化策略框架

基于 CSQAQ API 的 CS:GO/CS2 饰品市场量化策略框架。框架本身与子指数无关，当前以手套板块作为首个验证场景。

## 核心原则

- **不依赖成交量**：所有信号仅基于 OHLC 与时间。
- **通用框架**：通过配置切换子指数，代码不硬编码任何板块信息。
- **双环境兼容**：本地与 TRAE 环境均可运行。
- **测试驱动**：每个核心模块均附单元测试。

## 快速开始

1. 复制环境变量模板并填写真实 ApiToken：

```bash
cp .env.example .env
# 编辑 .env，填入 CSQAQ_API_TOKEN
```

2. 安装依赖：

```bash
pip install -e . --break-system-packages
```

3. 运行 MVP 回测（默认手套板块）：

```bash
python run_mvp.py
```

4. 切换其他子指数：

```bash
python run_mvp.py --sub-index-name 匕首
```

## 项目结构

```
csqaq-glove-quant/
├── src/
│   ├── api/          # CSQAQ API 客户端
│   ├── data/         # 缓存与数据管道
│   ├── features/     # 价格行为特征
│   ├── strategy/     # 信号生成与风控
│   ├── backtest/     # 回测引擎
│   └── analysis/     # 绩效指标
├── tests/            # 单元测试
├── data/cache/       # 本地 K 线缓存
└── reports/          # 回测报告与图表
```

## 数据范围

仅使用 2024-01-01 00:00:00 UTC 之后的 K 线数据。

## 文档

- [战略文档](/workspace/strategic-document.md)
- [战术文档（第一阶段）](/workspace/tactical-document.md)
- [策略方案](/workspace/price-action-quant-strategy-plan.md)
