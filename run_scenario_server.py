"""Entry point for the Phase 13 scenario web server.

Launches a FastAPI application on ``0.0.0.0:8000`` that serves:

- ``/scenario/*`` API routes defined in ``src.api.scenario_endpoints``.
- Static files from the ``frontend`` directory at the root path.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.scenario_endpoints import router as scenario_router


app = FastAPI(
    title="CSQAQ Glove Quant Scenario API",
    description="Algorithmic scenario generation, similarity search, template matching and constrained LLM explanation.",
    version="0.13.0",
)

app.include_router(scenario_router)

frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("run_scenario_server:app", host="0.0.0.0", port=8000, reload=False)
