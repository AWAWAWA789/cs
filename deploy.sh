#!/usr/bin/env bash
# One-click deployment script for the CSQAQ scenario API.
#
# Actions:
#   1. Install Python dependencies in the current virtual environment.
#   2. Run pytest to verify the build.
#   3. Build pre-computed state indexes for discovered sub-indices.
#   4. Start the uvicorn server in the background.
#   5. Poll the health endpoint until it returns HTTP 200.
#
# Environment variables:
#   CSQAQ_API_TOKEN      API token for fetching fresh OHLC data (optional).
#   CSQAQ_CACHE_PATH     Local cache directory (default: ./data/cache).
#   CSQAQ_LOG_FORMAT     Set to "json" for structured JSON logs.
#   CSQAQ_HOST           Bind host (default: 0.0.0.0).
#   CSQAQ_PORT           Bind port (default: 8000).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${CSQAQ_HOST:-0.0.0.0}"
PORT="${CSQAQ_PORT:-8000}"
HEALTH_URL="http://${HOST}:${PORT}/scenario/meta"

cd "${SCRIPT_DIR}"

echo "[deploy] Installing dependencies..."
python -m pip install -e . --quiet

echo "[deploy] Running pytest..."
python -m pytest tests --tb=short --quiet

echo "[deploy] Building state indexes..."
python - <<'PY'
import os
from pathlib import Path

import pandas as pd

from src.config import Settings
from src.data.cache import cache_file_path, load as load_cache
from src.scenario_engine.index_builder import build_state_index, save_index

settings = Settings()
cache_dir = Path(settings.cache_path)
if not cache_dir.exists():
    print("[deploy] No cache directory found; skipping index build.")
    raise SystemExit(0)

for path in sorted(cache_dir.glob("*_1d.parquet")):
    name = path.stem.rsplit("_", 1)[0]
    if not name:
        continue
    try:
        df = load_cache(str(path))
        if df is None or df.empty:
            continue
        index_df = build_state_index(df)
        index_path = cache_dir / f"{name}_1day_state_index.parquet"
        save_index(index_df, index_path)
        print(f"[deploy] Built index for {name}: {index_path}")
    except Exception as exc:
        print(f"[deploy] Failed to build index for {name}: {exc}")
PY

echo "[deploy] Starting server on ${HOST}:${PORT}..."
python -m uvicorn run_scenario_server:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --reload false \
    &
SERVER_PID=$!

echo "[deploy] Waiting for health check at ${HEALTH_URL}..."
for i in {1..30}; do
    if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
        echo "[deploy] Health check passed."
        curl -sS "${HEALTH_URL}" | python -m json.tool
        echo "[deploy] Server PID: ${SERVER_PID}"
        exit 0
    fi
    sleep 1
done

echo "[deploy] Health check failed after 30 seconds."
kill "${SERVER_PID}" 2>/dev/null || true
exit 1
