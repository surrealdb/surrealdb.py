"""Mocked regression tests for the ``info()`` record-auth ``$auth`` fallback
over the WebSocket transports (finding #23, finding #8-fragile-match).

WebSocket traffic cannot be intercepted with ``responses`` / ``aioresponses``
(those are HTTP mock libraries), so instead a fake socket is injected that
speaks the CBOR RPC framing directly: every request it receives is answered
by a ``responder`` keyed on the RPC ``method``. This exercises the real
``info()`` -> ``$auth`` fallback path including CBOR encode/decode.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.cbor import decode, encode
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import NotAllowedError

Responder = Callable[[dict[str, Any]], dict[str, Any]]

RECORD_SIGNIN = {
    "namespace": "test_ns",
    "database": "test_db",
    "access": "user",
    "variables": {"email": "tobie@example.com", "password": "password123"},
}


def _auth_record() -> dict[str, Any]:
    return {
        "id": RecordID("user", "tobie"),
        "name": "Tobie",
        "email": "tobie@example.com",
    }


def _make_responder(
    info_error: dict[str, Any],
    auth_records: list[dict[str, Any]],
) -> Responder:
    """Build a responder that answers signin/info/query RPCs.

    The response ``id`` always echoes the request ``id`` so the WS transports'
    request/response correlation succeeds.
    """

    def _responder(request: dict[str, Any]) -> dict[str, Any]:
        rid = request["id"]
        method = request["method"]
        if method == "signin":
            return {"id": rid, "result": "a.jwt.token"}
        if method == "info":
            return {"id": rid, "error": info_error}
        if method == "query":
            return {
                "id": rid,
                "result": [{"status": "OK", "result": auth_records, "time": "1ms"}],
            }
        raise AssertionError(f"unexpected RPC method: {method}")

    return _responder


class _FakeBlockingWsSocket:
    """Minimal stand-in for ``websockets.sync.client.ClientConnection``."""

    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self._pending: bytes | None = None

    def send(self, data: bytes) -> None:
        self._pending = encode(self._responder(decode(data)))

    def recv(self) -> bytes:
        assert self._pending is not None, "recv() called before send()"
        payload, self._pending = self._pending, None
        return payload

    def close(self) -> None:  # pragma: no cover - trivial
        pass


class _FakeAsyncWsSocket:
    """Minimal stand-in for an async ``websockets`` connection.

    ``send`` enqueues the canned response; the connection's ``_recv_task``
    iterates the socket and resolves the pending future by matching ``id``.
    """

    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def send(self, data: bytes) -> None:
        self._queue.put_nowait(encode(self._responder(decode(data))))

    def __aiter__(self) -> _FakeAsyncWsSocket:
        return self

    async def __anext__(self) -> bytes:
        return await self._queue.get()

    async def close(self) -> None:  # pragma: no cover - trivial
        pass


_NOT_FOUND_ERRORS = [
    pytest.param(
        {"code": -32000, "message": "No result found"}, id="legacy-code-32000"
    ),
    pytest.param(
        {"code": 0, "kind": "NotFound", "message": "There was no result"},
        id="structured-notfound-kind",
    ),
]


# --------------------------------------------------------------------------- #
# Blocking WS
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("error", _NOT_FOUND_ERRORS)
def test_blocking_ws_info_uses_auth_fallback(error: dict[str, Any]) -> None:
    record = _auth_record()
    db = BlockingWsSurrealConnection("ws://localhost:8000")
    db.socket = _FakeBlockingWsSocket(_make_responder(error, [record]))  # type: ignore[assignment]

    db.signin(RECORD_SIGNIN)
    outcome = db.info()

    assert outcome == record
    assert outcome["id"] == RecordID("user", "tobie")


def test_blocking_ws_info_non_not_found_error_raises() -> None:
    db = BlockingWsSurrealConnection("ws://localhost:8000")
    db.socket = _FakeBlockingWsSocket(  # type: ignore[assignment]
        _make_responder({"code": -32602, "message": "Not allowed"}, [])
    )

    db.signin(RECORD_SIGNIN)
    with pytest.raises(NotAllowedError):
        db.info()


# --------------------------------------------------------------------------- #
# Async WS
# --------------------------------------------------------------------------- #


async def _run_async_ws(responder: Responder) -> AsyncWsSurrealConnection:
    db = AsyncWsSurrealConnection("ws://localhost:8000")
    db.socket = _FakeAsyncWsSocket(responder)
    db.loop = asyncio.get_running_loop()
    db.recv_task = asyncio.create_task(db._recv_task())
    return db


async def _shutdown(db: AsyncWsSurrealConnection) -> None:
    if db.recv_task is not None:
        db.recv_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await db.recv_task


@pytest.mark.parametrize("error", _NOT_FOUND_ERRORS)
async def test_async_ws_info_uses_auth_fallback(error: dict[str, Any]) -> None:
    record = _auth_record()
    db = await _run_async_ws(_make_responder(error, [record]))
    try:
        await db.signin(RECORD_SIGNIN)
        outcome = await db.info()
        assert outcome == record
        assert outcome["id"] == RecordID("user", "tobie")
    finally:
        await _shutdown(db)


async def test_async_ws_info_non_not_found_error_raises() -> None:
    db = await _run_async_ws(
        _make_responder({"code": -32602, "message": "Not allowed"}, [])
    )
    try:
        await db.signin(RECORD_SIGNIN)
        with pytest.raises(NotAllowedError):
            await db.info()
    finally:
        await _shutdown(db)
