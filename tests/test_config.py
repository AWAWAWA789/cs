import os

import pytest

from src.config import Settings


def test_settings_reads_all_env_vars(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "test-token")
    monkeypatch.setenv("CSQAQ_BASE_URL", "https://test.csqaq.com/api/v1")
    monkeypatch.setenv("CSQAQ_CACHE_PATH", "/tmp/test-cache")
    monkeypatch.setenv("SUB_INDEX_ID", "42")
    monkeypatch.setenv("SUB_INDEX_NAME", "手套")
    monkeypatch.setenv("DEFAULT_PERIOD", "1hour")

    s = Settings()
    assert s.api_token == "test-token"
    assert s.base_url == "https://test.csqaq.com/api/v1"
    assert s.cache_path == "/tmp/test-cache"
    assert s.sub_index_id == "42"
    assert s.sub_index_name == "手套"
    assert s.default_period == "1hour"


def test_settings_has_sensible_defaults(monkeypatch):
    monkeypatch.delenv("CSQAQ_API_TOKEN", raising=False)
    monkeypatch.delenv("CSQAQ_BASE_URL", raising=False)
    monkeypatch.delenv("CSQAQ_CACHE_PATH", raising=False)
    monkeypatch.delenv("SUB_INDEX_ID", raising=False)
    monkeypatch.delenv("SUB_INDEX_NAME", raising=False)
    monkeypatch.delenv("DEFAULT_PERIOD", raising=False)

    s = Settings()
    assert s.base_url == "https://api.csqaq.com/api/v1"
    assert s.cache_path == "./data/cache"
    assert s.sub_index_id == ""
    assert s.sub_index_name == "手套"
    assert s.default_period == "4hour"


def test_validate_raises_when_api_token_missing(monkeypatch):
    monkeypatch.delenv("CSQAQ_API_TOKEN", raising=False)
    s = Settings()
    with pytest.raises(ValueError, match="CSQAQ_API_TOKEN is required"):
        s.validate()
