from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any, NamedTuple

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from surrealdb.spectron import SpectronAPIError, SpectronNotFoundError
from surrealdb.spectron._transport import AsyncTransport

API_KEY = "test-key"

_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class _Call(NamedTuple):
    """One request exactly as the server received it.

    This replaces introspecting `aioresponses`' `m.requests`: the handler
    records what the SDK actually sent, so call counts, target paths and
    outbound headers stay assertable without mocking aiohttp at all.
    """

    method: str
    path: str
    # At runtime this is aiohttp's case-insensitive multidict, so membership
    # tests below hold for any spelling of a header name.
    headers: Mapping[str, str]


def _record(calls: list[_Call], request: web.Request) -> None:
    calls.append(_Call(request.method, request.path, request.headers.copy()))


@asynccontextmanager
async def _serve(handler: _Handler) -> AsyncIterator[str]:
    """Run `handler` on a real loopback HTTP server, yielding its base URL.

    The transport is driven purely by its `endpoint`, so pointing it at this
    server exercises the genuine aiohttp request path with no mocking. The
    catch-all route means a request to the *wrong* path is still served, which
    is why every test asserts the path the handler saw - that is the coverage
    `aioresponses`' URL matching used to provide implicitly.
    """
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    try:
        yield str(server.make_url("/"))
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_async_get_sends_bearer_header() -> None:
    calls: list[_Call] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        _record(calls, request)
        return web.json_response({"ok": True}, status=200)

    async with (
        _serve(handler) as base,
        AsyncTransport(endpoint=base, api_key=API_KEY) as t,
    ):
        body = await t.get("/api/v1/x/health")
        assert body == {"ok": True}
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].path == "/api/v1/x/health"
        sent_headers = calls[0].headers
        assert sent_headers["Authorization"] == f"Bearer {API_KEY}"
        # Header lookups here are case-insensitive, so these two also rule
        # out any other spelling of the legacy API-key header.
        assert "X-API-Key" not in sent_headers
        assert "x-api-key" not in sent_headers


@pytest.mark.asyncio
async def test_async_get_retries_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    calls: list[_Call] = []
    responses: list[tuple[int, dict[str, Any]]] = [
        (503, {"e": 1}),
        (502, {"e": 2}),
        (200, {"ok": True}),
    ]

    async def handler(request: web.Request) -> web.StreamResponse:
        _record(calls, request)
        # An IndexError here means the SDK retried more times than the test
        # scripted, which surfaces as a failed assertion below.
        status, payload = responses[len(calls) - 1]
        return web.json_response(payload, status=status)

    async with (
        _serve(handler) as base,
        AsyncTransport(endpoint=base, api_key=API_KEY) as t,
    ):
        body = await t.get("/api/v1/x/y")
        assert body == {"ok": True}
        assert len(calls) == 3
        assert [c.path for c in calls] == ["/api/v1/x/y"] * 3


@pytest.mark.asyncio
async def test_async_post_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    calls: list[_Call] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        _record(calls, request)
        return web.json_response({"message": "down"}, status=503)

    async with (
        _serve(handler) as base,
        AsyncTransport(endpoint=base, api_key=API_KEY) as t,
    ):
        with pytest.raises(SpectronAPIError):
            await t.post("/api/v1/x/z", json={})
        # A plain POST is not idempotent, so a 5xx must surface immediately
        # rather than being retried.
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert calls[0].path == "/api/v1/x/z"


@pytest.mark.asyncio
async def test_async_idempotent_post_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    calls: list[_Call] = []
    responses: list[tuple[int, dict[str, Any]]] = [(503, {"e": 1}), (200, {"ok": True})]

    async def handler(request: web.Request) -> web.StreamResponse:
        _record(calls, request)
        status, payload = responses[len(calls) - 1]
        return web.json_response(payload, status=status)

    async with (
        _serve(handler) as base,
        AsyncTransport(endpoint=base, api_key=API_KEY) as t,
    ):
        body = await t.request(
            "POST",
            "/api/v1/x/facts",
            json={"text": "hi"},
            idempotent=True,
        )
        assert body == {"ok": True}
        assert len(calls) == 2
        assert [c.method for c in calls] == ["POST", "POST"]
        assert [c.path for c in calls] == ["/api/v1/x/facts"] * 2


@pytest.mark.asyncio
async def test_async_404_maps_to_not_found() -> None:
    calls: list[_Call] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        _record(calls, request)
        return web.json_response({"message": "gone"}, status=404)

    async with (
        _serve(handler) as base,
        AsyncTransport(endpoint=base, api_key=API_KEY) as t,
    ):
        with pytest.raises(SpectronNotFoundError):
            await t.get("/api/v1/x/missing")
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].path == "/api/v1/x/missing"
