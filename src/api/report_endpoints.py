"""Report viewing API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.logging import LOGGER, log_request

router = APIRouter(prefix="/reports", tags=["reports"])

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


@router.get("/list")
def list_reports() -> dict[str, Any]:
    """List all JSON report files in the reports directory."""
    if not REPORTS_DIR.exists():
        return {"reports": []}

    files = []
    for path in sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.name):
        stat = path.stat()
        files.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    log_request(LOGGER, endpoint="/reports/list", extra={"file_count": len(files)})
    return {"reports": files}


@router.get("/get")
def get_report(filename: str = Query(..., description="Report filename.")) -> dict[str, Any]:
    """Get the content of a specific report file."""
    # Use resolve() to canonicalize path and prevent traversal
    target = (REPORTS_DIR / filename).resolve()
    reports_resolved = REPORTS_DIR.resolve()

    # Verify the resolved path is within reports directory
    try:
        target.relative_to(reports_resolved)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    try:
        content = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse report: {exc}") from exc

    log_request(LOGGER, endpoint="/reports/get", extra={"filename": filename})
    return {"filename": filename, "content": content}
