"""Lifecycle tests for the async HTTP connection (issues #8 and #10).

These drive the connection against a throwaway local ``aiohttp`` server
started by the test itself, so they need no live SurrealDB.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, NamedTuple

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.cbor import encode

URL = "http://localhost:8000"


def _version_body(version: str = "surrealdb-2.0.0") -> bytes:
    return encode({"id": "1", "result": version})


class _Recorded(NamedTuple):
    """One request as the stub server saw it.

    ``transport`` identifies the TCP connection the request arrived on, which
    is how a reused pooled session (one connection) is told apart from a fresh
    session per request (one connection each).
    """

    method: str
    path: str
    transport: asyncio.Transport | None


@asynccontextmanager
async def _version_server(recorded: list[_Recorded]) -> AsyncIterator[str]:
    """Serve a canned ``version`` RPC reply, recording every request.

    Yields the base URL to point the connection at. The server is always shut
    down on the way out so tests do not leak sockets.
    """

    async def handler(request: web.Request) -> web.Response:
        await request.read()
        recorded.append(_Recorded(request.method, request.path, request.transport))
        return web.Response(body=_version_body(), content_type="application/cbor")

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    try:
        yield str(server.make_url("/")).rstrip("/")
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_pooled_session_reused_across_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single pooled session is created on entry and reused per request."""
    created: list[aiohttp.ClientSession] = []
    original = aiohttp.ClientSession

    def _factory(*args: Any, **kwargs: Any) -> aiohttp.ClientSession:
        session = original(*args, **kwargs)
        created.append(session)
        return session

    monkeypatch.setattr(
        "surrealdb.connections.async_http.aiohttp.ClientSession", _factory
    )

    recorded: list[_Recorded] = []
    async with _version_server(recorded) as url:
        connection = AsyncHttpSurrealConnection(url)
        async with connection:
            pooled = connection._session
            assert pooled is not None
            assert await connection.version() == "surrealdb-2.0.0"
            assert await connection.version() == "surrealdb-2.0.0"
            # Both requests reused the same pooled session object.
            assert connection._session is pooled

    # Exactly one session was created for the whole context manager,
    # not one per request.
    assert len(created) == 1
    # It was closed on exit and the reference cleared.
    assert created[0].closed is True
    assert connection._session is None

    # The server really served both RPCs, and both arrived on the single
    # connection the pooled session keeps alive.
    assert [(entry.method, entry.path) for entry in recorded] == [
        ("POST", "/rpc"),
        ("POST", "/rpc"),
    ]
    assert recorded[0].transport is not None
    assert recorded[0].transport is recorded[1].transport


@pytest.mark.asyncio
async def test_new_session_per_request_without_context_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outside a context manager each request opens its own session."""
    created: list[aiohttp.ClientSession] = []
    original = aiohttp.ClientSession

    def _factory(*args: Any, **kwargs: Any) -> aiohttp.ClientSession:
        session = original(*args, **kwargs)
        created.append(session)
        return session

    monkeypatch.setattr(
        "surrealdb.connections.async_http.aiohttp.ClientSession", _factory
    )

    recorded: list[_Recorded] = []
    async with _version_server(recorded) as url:
        connection = AsyncHttpSurrealConnection(url)
        assert await connection.version() == "surrealdb-2.0.0"
        assert await connection.version() == "surrealdb-2.0.0"

    assert connection._session is None
    assert len(created) == 2

    # Each per-request session brought its own connection, and closed it.
    assert [(entry.method, entry.path) for entry in recorded] == [
        ("POST", "/rpc"),
        ("POST", "/rpc"),
    ]
    assert recorded[0].transport is not recorded[1].transport


@pytest.mark.asyncio
async def test_close_is_noop_on_fresh_connection() -> None:
    """close() is a safe, idempotent no-op when no session is open."""
    connection = AsyncHttpSurrealConnection(URL)
    assert connection._session is None
    await connection.close()
    await connection.close()
    assert connection._session is None


@pytest.mark.asyncio
async def test_close_closes_pooled_session() -> None:
    """close() closes an open pooled session and clears it."""
    connection = AsyncHttpSurrealConnection(URL)
    connection._session = aiohttp.ClientSession()
    session = connection._session
    await connection.close()
    assert session.closed is True
    assert connection._session is None
    # Second close is still a safe no-op.
    await connection.close()
