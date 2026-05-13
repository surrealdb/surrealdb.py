from __future__ import annotations

import json
import time

import pytest
import responses

from surrealdb.spectron import AuthError, NotFoundError, RateLimitError, ServerError
from surrealdb.spectron._transport import BlockingTransport

API_KEY = "test-key"
BASE = "https://api.spectron.test"


@pytest.fixture
def transport() -> BlockingTransport:
    return BlockingTransport(endpoint=BASE, api_key=API_KEY, max_retries=3)


@responses.activate
def test_get_sends_bearer_header(transport: BlockingTransport):
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/x/health",
        json={"ok": True},
        status=200,
    )
    body = transport.get("/api/v1/x/health")
    assert body == {"ok": True}
    sent = responses.calls[0].request
    assert sent.headers["Authorization"] == f"Bearer {API_KEY}"
    assert sent.headers["Accept"] == "application/json"


@responses.activate
def test_get_retries_on_5xx_then_succeeds(monkeypatch, transport: BlockingTransport):
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    responses.add(responses.GET, f"{BASE}/api/v1/x/y", json={"e": 1}, status=503)
    responses.add(responses.GET, f"{BASE}/api/v1/x/y", json={"e": 2}, status=502)
    responses.add(responses.GET, f"{BASE}/api/v1/x/y", json={"ok": True}, status=200)

    body = transport.get("/api/v1/x/y")
    assert body == {"ok": True}
    assert len(responses.calls) == 3


@responses.activate
def test_get_retries_exhaust_raises_server_error(monkeypatch, transport: BlockingTransport):
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    for _ in range(4):
        responses.add(responses.GET, f"{BASE}/api/v1/x/y", json={"title": "down"}, status=500)
    with pytest.raises(ServerError) as info:
        transport.get("/api/v1/x/y")
    assert info.value.status == 500
    assert len(responses.calls) == 4


@responses.activate
def test_post_does_not_retry_on_5xx(monkeypatch, transport: BlockingTransport):
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    responses.add(responses.POST, f"{BASE}/api/v1/x/z", json={"title": "down"}, status=503)
    with pytest.raises(ServerError):
        transport.post("/api/v1/x/z", json={"hello": "world"})
    assert len(responses.calls) == 1


@responses.activate
def test_404_maps_to_not_found(transport: BlockingTransport):
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/x/missing",
        json={"title": "gone", "detail": "no such doc"},
        status=404,
    )
    with pytest.raises(NotFoundError) as info:
        transport.get("/api/v1/x/missing")
    assert info.value.detail == "no such doc"


@responses.activate
def test_401_maps_to_auth_error(transport: BlockingTransport):
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/x/secure",
        json={"title": "auth"},
        status=401,
    )
    with pytest.raises(AuthError):
        transport.get("/api/v1/x/secure")


@responses.activate
def test_429_preserves_retry_after(transport: BlockingTransport):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/x/burst",
        json={"title": "slow"},
        status=429,
        headers={"Retry-After": "7"},
    )
    with pytest.raises(RateLimitError) as info:
        transport.post("/api/v1/x/burst", json={})
    assert info.value.retry_after == 7.0


@responses.activate
def test_body_json_payload_sent(transport: BlockingTransport):
    responses.add(responses.POST, f"{BASE}/api/v1/x/echo", json={"ack": True}, status=200)
    transport.post("/api/v1/x/echo", json={"hello": "world"})
    sent = responses.calls[0].request
    assert sent.headers["Content-Type"].startswith("application/json")
    assert json.loads(sent.body) == {"hello": "world"}


@responses.activate
def test_no_content_returns_none(transport: BlockingTransport):
    responses.add(responses.DELETE, f"{BASE}/api/v1/x/r", body="", status=204)
    assert transport.delete("/api/v1/x/r") is None


def test_api_key_ignores_environment(monkeypatch):
    monkeypatch.setenv("SPECTRON_API_KEY", "env-key")
    with pytest.raises(ValueError, match="API key"):
        BlockingTransport(endpoint=BASE)


def test_api_key_required():
    with pytest.raises(ValueError, match="API key"):
        BlockingTransport(endpoint=BASE)


def test_api_key_empty_string_rejected():
    with pytest.raises(ValueError, match="API key"):
        BlockingTransport(endpoint=BASE, api_key="")


def test_endpoint_required():
    with pytest.raises(ValueError, match="endpoint"):
        BlockingTransport(api_key=API_KEY)


def test_endpoint_empty_string_rejected():
    with pytest.raises(ValueError, match="endpoint"):
        BlockingTransport(endpoint="", api_key=API_KEY)
