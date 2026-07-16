"""Lifecycle tests for the async HTTP connection (issues #8 and #10).

These are fully mocked with ``aioresponses`` and need no live server.
"""

from typing import Any

import aiohttp
import pytest
from aioresponses import aioresponses

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.cbor import encode

URL = "http://localhost:8000"
RPC = f"{URL}/rpc"


def _version_body(version: str = "surrealdb-2.0.0") -> bytes:
    return encode({"id": "1", "result": version})


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

    connection = AsyncHttpSurrealConnection(URL)
    with aioresponses() as mocked:
        mocked.post(RPC, body=_version_body(), status=200)
        mocked.post(RPC, body=_version_body(), status=200)
        async with connection:
            pooled = connection._session
            assert pooled is not None
            await connection.version()
            await connection.version()
            # Both requests reused the same pooled session object.
            assert connection._session is pooled

    # Exactly one session was created for the whole context manager,
    # not one per request.
    assert len(created) == 1
    # It was closed on exit and the reference cleared.
    assert created[0].closed is True
    assert connection._session is None


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

    connection = AsyncHttpSurrealConnection(URL)
    with aioresponses() as mocked:
        mocked.post(RPC, body=_version_body(), status=200)
        mocked.post(RPC, body=_version_body(), status=200)
        await connection.version()
        await connection.version()

    assert connection._session is None
    assert len(created) == 2


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
