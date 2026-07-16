from __future__ import annotations

import json
import time

import pytest
import responses

from surrealdb.spectron import (
    SpectronAPIError,
    SpectronAuthError,
    SpectronNotFoundError,
)
from surrealdb.spectron._transport import BlockingTransport

API_KEY = "test-key"
BASE = "https://api.spectron.test"


@pytest.fixture
def transport() -> BlockingTransport:
    return BlockingTransport(endpoint=BASE, api_key=API_KEY, max_retries=3)


@responses.activate
def test_get_sends_bearer_header(transport: BlockingTransport) -> None:
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
    assert "X-API-Key" not in sent.headers
    assert "x-api-key" not in sent.headers


@responses.activate
def test_post_only_auth_header_is_bearer(transport: BlockingTransport) -> None:
    responses.add(
        responses.POST, f"{BASE}/api/v1/x/echo", json={"ok": True}, status=200
    )
    transport.post("/api/v1/x/echo", json={"hello": "world"})
    sent = responses.calls[0].request
    assert sent.headers["Authorization"] == f"Bearer {API_KEY}"
    auth_headers = [
        k for k in sent.headers if "auth" in k.lower() or "key" in k.lower()
    ]
    assert auth_headers == ["Authorization"], auth_headers


@responses.activate
def test_get_retries_on_5xx_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, transport: BlockingTransport
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    responses.add(responses.GET, f"{BASE}/api/v1/x/y", json={"e": 1}, status=503)
    responses.add(responses.GET, f"{BASE}/api/v1/x/y", json={"e": 2}, status=502)
    responses.add(responses.GET, f"{BASE}/api/v1/x/y", json={"ok": True}, status=200)

    body = transport.get("/api/v1/x/y")
    assert body == {"ok": True}
    assert len(responses.calls) == 3


@responses.activate
def test_get_retries_exhaust_raises_api_error(
    monkeypatch: pytest.MonkeyPatch, transport: BlockingTransport
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    for _ in range(4):
        responses.add(
            responses.GET, f"{BASE}/api/v1/x/y", json={"message": "down"}, status=500
        )
    with pytest.raises(SpectronAPIError) as info:
        transport.get("/api/v1/x/y")
    assert info.value.status_code == 500
    assert len(responses.calls) == 4


@responses.activate
def test_post_does_not_retry_on_5xx(
    monkeypatch: pytest.MonkeyPatch, transport: BlockingTransport
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    responses.add(
        responses.POST, f"{BASE}/api/v1/x/z", json={"message": "down"}, status=503
    )
    with pytest.raises(SpectronAPIError):
        transport.post("/api/v1/x/z", json={"hello": "world"})
    assert len(responses.calls) == 1


@responses.activate
def test_idempotent_post_retries_on_5xx(
    monkeypatch: pytest.MonkeyPatch, transport: BlockingTransport
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    responses.add(responses.POST, f"{BASE}/api/v1/x/facts", json={"e": 1}, status=503)
    responses.add(
        responses.POST, f"{BASE}/api/v1/x/facts", json={"ok": True}, status=200
    )
    body = transport.request(
        "POST",
        "/api/v1/x/facts",
        json={"text": "hi"},
        idempotent=True,
    )
    assert body == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_404_maps_to_not_found(transport: BlockingTransport) -> None:
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/x/missing",
        json={"message": "no such doc"},
        status=404,
    )
    with pytest.raises(SpectronNotFoundError) as info:
        transport.get("/api/v1/x/missing")
    assert info.value.message == "no such doc"


@responses.activate
def test_401_maps_to_auth_error(transport: BlockingTransport) -> None:
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/x/secure",
        json={"message": "auth"},
        status=401,
    )
    with pytest.raises(SpectronAuthError):
        transport.get("/api/v1/x/secure")


@responses.activate
def test_body_json_payload_sent(transport: BlockingTransport) -> None:
    responses.add(
        responses.POST, f"{BASE}/api/v1/x/echo", json={"ack": True}, status=200
    )
    transport.post("/api/v1/x/echo", json={"hello": "world"})
    sent = responses.calls[0].request
    assert sent.headers["Content-Type"].startswith("application/json")
    assert json.loads(sent.body) == {"hello": "world"}


@responses.activate
def test_no_content_returns_none(transport: BlockingTransport) -> None:
    responses.add(responses.DELETE, f"{BASE}/api/v1/x/r", body="", status=204)
    assert transport.delete("/api/v1/x/r") is None


def test_api_key_ignores_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECTRON_API_KEY", "env-key")
    with pytest.raises(ValueError, match="API key"):
        BlockingTransport(endpoint=BASE)


def test_api_key_required() -> None:
    with pytest.raises(ValueError, match="API key"):
        BlockingTransport(endpoint=BASE)


def test_api_key_empty_string_rejected() -> None:
    with pytest.raises(ValueError, match="API key"):
        BlockingTransport(endpoint=BASE, api_key="")


def test_endpoint_required() -> None:
    with pytest.raises(ValueError, match="endpoint"):
        BlockingTransport(api_key=API_KEY)


def test_endpoint_empty_string_rejected() -> None:
    with pytest.raises(ValueError, match="endpoint"):
        BlockingTransport(endpoint="", api_key=API_KEY)
