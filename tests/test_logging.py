"""Tests for the structured API logging module."""

from __future__ import annotations

import json
import logging

import pytest

from src.api.logging import get_logger, log_request


def _capture_log_records(caplog):
    """Return the last log record or None."""
    return caplog.records[-1] if caplog.records else None


def test_get_logger_returns_configured_logger():
    """get_logger should return a logger with a handler."""
    logger = get_logger("csqaq.test")
    assert isinstance(logger, logging.Logger)
    assert logger.handlers


def test_log_request_attaches_context(caplog):
    """log_request should attach request context to the log record."""
    logger = get_logger("csqaq.test.request")
    with caplog.at_level(logging.INFO, logger="csqaq.test.request"):
        log_request(
            logger,
            endpoint="/scenario/generate",
            sub_index="手套",
            period="1day",
            latency_ms=123.456,
            cached=False,
            scenario_count=4,
        )
    record = _capture_log_records(caplog)
    assert record is not None
    assert record.request_context["endpoint"] == "/scenario/generate"
    assert record.request_context["sub_index"] == "手套"
    assert record.request_context["period"] == "1day"
    assert record.request_context["latency_ms"] == 123.456
    assert record.request_context["cached"] is False
    assert record.request_context["scenario_count"] == 4


def test_log_request_error_level(caplog):
    """log_request with an error should emit an ERROR level record."""
    logger = get_logger("csqaq.test.error")
    with caplog.at_level(logging.ERROR, logger="csqaq.test.error"):
        log_request(
            logger,
            endpoint="/scenario/generate",
            sub_index="手套",
            period="1day",
            latency_ms=200.0,
            error="generation timeout",
        )
    record = _capture_log_records(caplog)
    assert record is not None
    assert record.levelname == "ERROR"
    assert record.request_context["error"] == "generation timeout"


def test_json_formatter_includes_context(monkeypatch, capsys):
    """With CSQAQ_LOG_FORMAT=json, output should be parseable JSON."""
    import importlib

    monkeypatch.setenv("CSQAQ_LOG_FORMAT", "json")
    import src.api.logging as logging_module

    importlib.reload(logging_module)
    logger = logging_module.get_logger("csqaq.test.json")

    logging_module.log_request(
        logger,
        endpoint="/scenario/history",
        sub_index="匕首",
        period="4hour",
        latency_ms=50.0,
        extra={"match_count": 10},
    )
    captured = capsys.readouterr()
    last_line = captured.out.strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload["level"] == "INFO"
    assert payload["request_context"]["endpoint"] == "/scenario/history"
    assert payload["request_context"]["sub_index"] == "匕首"
    assert payload["request_context"]["match_count"] == 10
