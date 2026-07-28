"""Structured logging utilities for the scenario API.

The module provides a small factory that returns loggers emitting JSON lines
when ``CSQAQ_LOG_FORMAT=json`` is set, and plain human-readable lines
otherwise. Every log record can carry a ``request_context`` dict with fields
such as ``sub_index``, ``period``, ``latency_ms`` and ``result_summary``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


_DEFAULT_LEVEL = os.getenv("CSQAQ_LOG_LEVEL", "INFO").upper()
_DEFAULT_FORMAT = os.getenv("CSQAQ_LOG_FORMAT", "text").lower()


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_context") and isinstance(record.request_context, dict):
            payload["request_context"] = record.request_context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Merge extra fields that were attached directly to the record.
        for key in ("sub_index", "period", "latency_ms", "cached", "scenario_count", "error"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    """Human-readable formatter that still includes request context when present."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record)} [{record.levelname}] {record.name}: {record.getMessage()}"
        ctx = getattr(record, "request_context", None)
        if isinstance(ctx, dict):
            ctx_str = " ".join(f"{k}={v}" for k, v in ctx.items())
            base = f"{base} | {ctx_str}"
        return base


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with the requested ``name``.

    The returned logger has exactly one handler so repeated calls do not
    duplicate log lines. The format is controlled by the environment variable
    ``CSQAQ_LOG_FORMAT`` (``json`` or ``text``).
    """
    logger = logging.getLogger(name)
    logger.setLevel(_DEFAULT_LEVEL)

    # Avoid adding multiple handlers when the module is imported more than once.
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(_DEFAULT_LEVEL)

    if _DEFAULT_FORMAT == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_TextFormatter())

    logger.addHandler(handler)
    return logger


def log_request(
    logger: logging.Logger,
    *,
    endpoint: str,
    sub_index: str | None = None,
    period: str | None = None,
    latency_ms: float | None = None,
    cached: bool | None = None,
    scenario_count: int | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log a structured API request summary.

    Args:
        logger: Logger returned by :func:`get_logger`.
        endpoint: API endpoint path, e.g. ``/scenario/generate``.
        sub_index: Sub-index Chinese name.
        period: K-line period.
        latency_ms: Request latency in milliseconds.
        cached: Whether the response was served from cache.
        scenario_count: Number of scenarios returned.
        error: Exception or error message, if any.
        extra: Additional fields to attach to the log record.
    """
    context: dict[str, Any] = {"endpoint": endpoint}
    if sub_index is not None:
        context["sub_index"] = sub_index
    if period is not None:
        context["period"] = period
    if latency_ms is not None:
        context["latency_ms"] = round(latency_ms, 3)
    if cached is not None:
        context["cached"] = cached
    if scenario_count is not None:
        context["scenario_count"] = scenario_count
    if error is not None:
        context["error"] = error
    if extra:
        context.update(extra)

    if error is not None:
        logger.error("%s request failed", endpoint, extra={"request_context": context})
    else:
        logger.info("%s request completed", endpoint, extra={"request_context": context})
