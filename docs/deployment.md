# 本地部署与运行教程

本仓库托管于 `https://github.com/AWAWAWA789/cs`，本文档介绍从克隆代码到本地运行的完整流程。适用于 Python 3.10+ 的 Linux、macOS 及 Windows（WSL）环境。

## 前置要求

| 项目 | 说明 |
|------|------|
| Python | >= 3.10 |
| Git | 用于克隆仓库 |
| CSQAQ API Token | 可选。需要拉取真实 OHLC 数据时填写；仅测试或查看效果时可使用内置合成数据 |
| Docker | 可选。用于容器化部署 |

## 第一步：克隆仓库

```bash
git clone https://github.com/AWAWAWA789/cs.git
cd cs
```

克隆后得到的目录结构如下：

```
cs/
├── src/                     # 核心代码
│   ├── api/                 # CSQAQ API 客户端与 FastAPI 端点
│   ├── data/                # 缓存与数据管道
│   ├── features/            # 价格行为特征
│   ├── strategy/            # 信号生成与风控
│   ├── backtest/            # 回测引擎
│   ├── analysis/            # 绩效指标
│   └── scenario_engine/     # 情景生成引擎
├── frontend/                # 可视化前端（HTML/JS）
├── config/                  # 情景模板与 JSON Schema
├── tests/                   # 单元测试
├── 战术文档/                 # 战略文档与各阶段战术文档
├── docs/                    # 部署指南与 API 文档
├── data/cache/              # 本地 K 线缓存（运行后自动生成）
├── reports/                 # 回测报告与图表（运行后自动生成）
├── run_mvp.py               # MVP 回测入口
├── run_scenario_server.py   # API 服务入口
├── run_ensemble.py          # 集成策略入口
├── run_trend_scan.py        # 趋势扫描入口
├── deploy.sh                # 一键部署脚本
├── Dockerfile               # 容器构建文件
├── pyproject.toml           # 依赖配置
└── .env.example             # 环境变量模板
```

## 第二步：创建虚拟环境

推荐使用虚拟环境隔离依赖，避免与系统 Python 包冲突。

```bash
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows
```

激活后命令行提示符前会出现 `(.venv)` 标识。

## 第三步：安装依赖

```bash
pip install -e .
```

如果在某些 Linux 发行版上遇到 `externally-managed-environment` 报错，改用：

```bash
pip install -e . --break-system-packages
```

依赖列表定义在 `pyproject.toml` 中，主要包含：requests、pandas、numpy、scikit-learn、fastapi、uvicorn、matplotlib 等。

## 第四步：配置环境变量

复制模板文件：

```bash
cp .env.example .env
```

编辑 `.env`，填入你的配置：

```ini
# CSQAQ API Token（需要真实数据时填写）
CSQAQ_API_TOKEN=your_api_token_here

# API 基础地址
CSQAQ_BASE_URL=https://api.csqaq.com/api/v1

# 本地缓存目录
CSQAQ_CACHE_PATH=./data/cache

# 默认子指数
SUB_INDEX_NAME=手套
```

`.env` 已在 `.gitignore` 中排除，不会被提交到仓库。

## 第五步：验证安装

运行单元测试确认环境正常：

```bash
pytest tests --tb=short
```

全部通过则说明安装成功。若未配置 `CSQAQ_API_TOKEN`，测试会自动使用合成数据，不会调用外部 API。

## 运行方式

### 方式一：MVP 回测

默认对手套板块进行 4 小时周期回测：

```bash
python run_mvp.py
```

切换子指数或周期：

```bash
python run_mvp.py --sub-index 匕首 --period 1day
python run_mvp.py --sub-index 百元主战 --period 4hour --force-refresh
```

支持的周期：`1hour`、`4hour`、`1day`、`7day`。

### 方式二：启动情景 API 服务

```bash
python run_scenario_server.py
```

服务启动后监听 `0.0.0.0:8000`，可访问以下地址：

| 地址 | 说明 |
|------|------|
| `http://localhost:8000/` | 前端可视化界面 |
| `http://localhost:8000/docs` | FastAPI 自动生成的交互式 API 文档 |
| `http://localhost:8000/scenario/meta` | 可用子指数与周期列表 |
| `http://localhost:8000/scenario/generate?sub_index=手套&period=1day` | 生成情景分析 |

API 端点的详细说明参见 [情景 API 文档](scenario_api.md)。

### 方式三：一键部署脚本

```bash
./deploy.sh
```

脚本会依次完成：安装依赖 → 运行测试 → 构建状态索引 → 启动后台服务 → 健康检查。适合首次部署或 CI 环境使用。

### 方式四：Docker 容器部署

构建镜像：

```bash
docker build -t csqaq-scenario .
```

运行容器：

```bash
docker run -p 8000:8000 -e CSQAQ_API_TOKEN=your_api_token_here csqaq-scenario
```

容器启动后访问 `http://localhost:8000`。

## 数据加载策略

API 端点按以下优先级加载 OHLC 数据：

1. **本地缓存**：优先读取 `CSQAQ_CACHE_PATH`（默认 `./data/cache`）下的 Parquet 文件。
2. **API 拉取**：若配置了 `CSQAQ_API_TOKEN`，则调用 CSQAQ API 获取数据并写入缓存。
3. **合成数据**：若以上均不可用，生成确定性合成数据，仅用于演示和测试。

## 常见问题

**未配置 CSQAQ_API_TOKEN 能否运行？**
可以。没有 Token 时系统回退到合成数据，功能正常但数据非真实行情。

**如何清除本地缓存？**
删除 `data/cache/` 目录，或在 API 请求中加上 `refresh=true` 参数强制刷新。

**服务启动后前端页面空白？**
确认 `frontend/` 目录存在且包含 `index.html`。`run_scenario_server.py` 会自动挂载该目录为静态文件根目录。

**测试失败怎么办？**
确认已激活虚拟环境并执行了 `pip install -e .`，然后运行 `pytest tests -v` 查看具体失败用例。

**如何查看各阶段战术文档？**
所有战略与战术文档已统一整理到 `战术文档/` 目录下，按阶段编号中文命名。README 中有快速链接。
