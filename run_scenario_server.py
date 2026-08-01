"""Entry point for the Phase 16 scenario web server.

Launches a FastAPI application on ``0.0.0.0:8000`` that serves:

- ``/scenario/*`` API routes defined in ``src.api.scenario_endpoints``.
- ``/backtest/*`` API routes defined in ``src.api.backtest_endpoints``.
- ``/monitoring/*`` API routes defined in ``src.api.monitoring``.
- Static files from the ``frontend/dist`` directory at the root path.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Load .env file before any Settings are created
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from src.api.accumulation_endpoints import router as accumulation_router
from src.api.backtest_endpoints import router as backtest_router
from src.api.data_endpoints import router as data_router
from src.api.ensemble_endpoints import router as ensemble_router
from src.api.item_endpoints import router as item_router
from src.api.monitor_endpoints import router as monitor_router
from src.api.rank_endpoints import router as rank_router
from src.api.monitoring import monitoring_router
from src.api.report_endpoints import router as report_router
from src.api.scenario_endpoints import router as scenario_router
from src.api.trend_scan_endpoints import router as trend_scan_router
from src.api.volume_endpoints import router as volume_router


class CacheControlStaticFiles(StaticFiles):
    """``StaticFiles`` that sets a long ``Cache-Control`` header on hashed assets.

    Vite emits content-hashed filenames (``assets/index-<hash>.js``) so the
    bytes at a given URL never change. Browsers can safely cache them for a
    year. ``index.html`` itself is left to its default (no long cache) so
    users pick up new deploys immediately.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        # Only cache the immutable hashed assets under /assets/. The HTML
        # entrypoint must remain uncached so new deploys are picked up.
        if path.startswith("assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


app = FastAPI(
    title="CSQAQ Glove Quant Scenario API",
    description="Algorithmic scenario generation, similarity search, template matching, backtest visualization and monitoring.",
    version="0.20.0",
)

# GZip compresses JSON responses (OHLC payloads, scenario blobs, equity
# curves) which are highly compressible text. minimum_size matches the
# starlette default to skip trivially small payloads.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenario_router)
app.include_router(backtest_router)
app.include_router(ensemble_router)
app.include_router(trend_scan_router)
app.include_router(report_router)
app.include_router(data_router)
app.include_router(monitoring_router)
app.include_router(item_router)
app.include_router(rank_router)
app.include_router(monitor_router)
app.include_router(volume_router)
app.include_router(accumulation_router)

frontend_dir = Path(__file__).parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount(
        "/",
        CacheControlStaticFiles(directory=str(frontend_dir), html=True),
        name="frontend",
    )
else:

    @app.get("/")
    def frontend_not_built():
        """前端未构建时返回提示信息。"""
        return HTMLResponse(
            "<h1>前端未构建</h1>"
            "<p>请先运行 <code>cd frontend && npm install && npm run build</code></p>",
            status_code=503,
        )


if __name__ == "__main__":
    import uvicorn

    # Multiple workers improve throughput under concurrent demo traffic and
    # are safe because every endpoint is stateless (caches are per-process
    # TTL caches, which is fine for demo-grade load).
    uvicorn.run(
        "run_scenario_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=2,
    )
