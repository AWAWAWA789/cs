# CSQAQ Glove Quant 本地部署与运行指南

本仓库托管于 `https://github.com/AWAWAWA789/cs`，本地部署后可用于运行价格行为量化策略、生成情景分析、启动可视化 API 服务。以下流程已在 Python 3.10+ 的 Linux/macOS/Windows(WSL) 环境验证。

## 前置要求

- **Python**：>= 3.10
- **Git**：用于克隆仓库
- **CSQAQ API Token**（可选）：若需要拉取真实 OHLC 数据，需向 CSQAQ 申请 ApiToken；仅做测试或查看效果时，可使用内置合成数据
- **Docker**（可选）：用于容器化部署

## 1. 克隆仓库

```bash
git clone https://github.com/AWAWAWA789/cs.git
cd cs
```

仓库目录结构：

```
cs/
├── src/                 # 核心代码
│   ├── api/             # CSQAQ API 客户端与 FastAPI 端点
│   ├── scenario_engine/ # 情景生成、相似搜索、模板匹配
│   ├── strategy/        # 信号生成与风控
│   ├── backtest/        # 回测引擎
│   └── features/        # 价格行为特征
├── frontend/            # 可视化前端（HTML/JS）
├── config/              # 情景模板与 JSON Schema
├── tests/               # 单元测试
├── run_mvp.py           # MVP 回测入口
├── run_scenario_server.py  # API 服务入口
├── run_ensemble.py      # 集成策略入口
├── run_trend_scan.py    # 趋势扫描入口
├── deploy.sh            # 一键部署脚本
├── Dockerfile           # 容器构建文件
├── pyproject.toml       # 依赖配置
└── .env.example         # 环境变量模板
```

## 2. 创建并激活虚拟环境

推荐使用虚拟环境隔离依赖。

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate   # Windows
```

## 3. 安装依赖

```bash
pip install -e .
```

在受限制的 Linux 系统上，若出现系统包冲突，可改用：

```bash
pip install -e . --break-system-packages
```

## 4. 配置环境变量

复制模板文件并填写真实配置：

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
# 必填（若使用真实数据）
CSQAQ_API_TOKEN=your_api_token_here

# 可选
CSQAQ_BASE_URL=https://api.csqaq.com/api/v1
CSQAQ_CACHE_PATH=./data/cache
SUB_INDEX_NAME=手套
```

`.env` 已加入 `.gitignore`，不会被提交。

## 5. 验证安装

运行单元测试确认环境正常：

```bash
pytest tests --tb=short
```

首次运行可能需要联网下载依赖；若未配置 `CSQAQ_API_TOKEN`，测试会使用合成数据，不会调用外部 API。

## 6. 本地运行方式

### 6.1 运行 MVP 回测

默认对手套板块进行 4 小时周期回测：

```bash
python run_mvp.py
```

切换其他子指数或周期：

```bash
python run_mvp.py --sub-index 匕首 --period 1day
python run_mvp.py --sub-index 百元主战 --period 4hour --force-refresh
```

### 6.2 运行趋势扫描

```bash
python run_trend_scan.py
```

### 6.3 运行集成策略回测

```bash
python run_ensemble.py
```

### 6.4 启动情景 API 服务

```bash
python run_scenario_server.py
```

服务启动后监听 `0.0.0.0:8000`：

- 前端界面：`http://localhost:8000/`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`curl http://localhost:8000/scenario/meta`
- 生成情景：`curl "http://localhost:8000/scenario/generate?sub_index=手套&period=1day"`

### 6.5 使用一键部署脚本

```bash
./deploy.sh
```

该脚本会依次执行：安装依赖、运行测试、构建状态索引、启动后台服务、健康检查。

## 7. Docker 部署

构建镜像：

```bash
docker build -t csqaq-scenario .
```

运行容器：

```bash
docker run -p 8000:8000 -e CSQAQ_API_TOKEN=your_api_token_here csqaq-scenario
```

服务启动后访问 `http://localhost:8000`。

## 8. 常见问题

**Q：未配置 CSQAQ_API_TOKEN 能否运行？**
可以。API 端点和部分脚本在没有 Token 时会回退到确定性合成数据，仅用于演示和测试。

**Q：如何清除本地缓存？**
删除 `data/cache/` 目录，或在调用 API 时加上 `refresh=true` 参数。

**Q：服务启动后前端空白？**
确认 `frontend/` 目录存在且包含 `index.html`；`run_scenario_server.py` 会自动挂载该目录为静态文件根目录。

**Q：测试失败怎么办？**
先确认已激活虚拟环境并执行 `pip install -e .`，再运行 `pytest tests -v` 查看具体失败用例。

## 9. 目录约定

- `data/cache/`：本地 K 线缓存与状态索引
- `reports/`：回测报告与图表
- `docs/`：项目文档与战术计划

首次运行后这些目录会自动生成，无需手动创建。
