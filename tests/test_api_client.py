"""Tests for the CSQAQ API client and endpoint wrappers."""

import time

import pytest
import responses

from src.api.client import CSQAQAPIError, CSQAQClient
from src.api.endpoints import bind_local_ip, get_current_data_init, get_sub_kline
from src.config import Settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("CSQAQ_API_TOKEN", "test-token")
    monkeypatch.setenv("CSQAQ_BASE_URL", "https://api.csqaq.com/api/v1")
    return Settings()


@pytest.fixture
def client(settings):
    return CSQAQClient(settings)


@responses.activate
def test_client_sends_api_token_and_parses_data(client):
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={"code": 200, "msg": "Success", "data": {"sub_index_data": []}},
        status=200,
    )

    data = client.get("/current_data", params={"type": "init"}, skip_rate_limit=True)

    assert data == {"sub_index_data": []}
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["ApiToken"] == "test-token"


@responses.activate
def test_client_raises_on_http_error(client):
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={"code": 401, "msg": "Unauthorized"},
        status=401,
    )

    with pytest.raises(CSQAQAPIError, match="HTTP error 401"):
        client.get("/current_data", params={"type": "init"}, skip_rate_limit=True)


@responses.activate
def test_client_raises_on_api_error_code(client):
    responses.get(
        "https://api.csqaq.com/api/v1/sub/kline?id=1&type=4hour",
        json={"code": 400, "msg": "参数错误", "data": None},
        status=200,
    )

    with pytest.raises(CSQAQAPIError, match="API error 400"):
        client.get("/sub/kline", params={"id": "1", "type": "4hour"}, skip_rate_limit=True)


@responses.activate
def test_client_enforces_normal_rate_limit(client, monkeypatch):
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={"code": 200, "msg": "Success", "data": {}},
        status=200,
    )
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={"code": 200, "msg": "Success", "data": {}},
        status=200,
    )

    sleeps = []
    original_sleep = time.sleep

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)

    # Force the client to believe a request just happened.
    client._last_request_time = original_sleep(0) or time.monotonic()

    client.get("/current_data", params={"type": "init"})
    client.get("/current_data", params={"type": "init"})

    assert len(responses.calls) == 2
    assert len(sleeps) >= 1
    assert sleeps[-1] >= CSQAQClient.NORMAL_COOLDOWN - 0.05


@responses.activate
def test_client_enforces_bind_ip_rate_limit(client, monkeypatch):
    responses.post(
        "https://api.csqaq.com/api/v1/sys/bind_local_ip",
        json={"code": 200, "msg": "Success", "data": "绑定IP更新成功"},
        status=200,
    )

    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)

    client._last_bind_ip_time = time.monotonic()

    bind_local_ip(client)

    assert len(responses.calls) == 1
    assert len(sleeps) == 1
    assert sleeps[0] >= CSQAQClient.BIND_IP_COOLDOWN - 0.05


@responses.activate
def test_get_current_data_init_endpoint(client):
    responses.get(
        "https://api.csqaq.com/api/v1/current_data?type=init",
        json={
            "code": 200,
            "msg": "Success",
            "data": {"sub_index_data": [{"id": "1", "name": "手套"}]},
        },
        status=200,
    )

    data = get_current_data_init(client, skip_rate_limit=True)

    assert data["sub_index_data"][0]["name"] == "手套"


@responses.activate
def test_get_sub_kline_endpoint(client):
    responses.get(
        "https://api.csqaq.com/api/v1/sub/kline?id=1&type=4hour",
        json={
            "code": 200,
            "msg": "Success",
            "data": {
                "t": [1700000000000],
                "o": [100.0],
                "c": [101.0],
                "h": [102.0],
                "l": [99.0],
                "v": [0],
            },
        },
        status=200,
    )

    data = get_sub_kline(client, "1", "4hour", skip_rate_limit=True)

    assert data["c"] == [101.0]
    assert data["v"] == [0]
