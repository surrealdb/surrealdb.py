"""Server-independent unit tests for the WebSocket live-query lifecycle.

These exercise the concurrency-sensitive fixes in ``async_ws`` and
``blocking_ws`` using in-memory fake sockets, so they run without a live
SurrealDB instance (unlike the integration tests under
``tests/unit_tests/connections`` which self-skip when no server is reachable).

Covers:
* #11a async ``subscribe_live`` leak: ``kill``/``close`` wake and deregister
  waiting consumers via a sentinel.
* #11b async disconnect: pending requests surface ``ConnectionUnavailableError``
  (not a raw ``CancelledError``/``KeyError``) when the socket closes.
* #11c blocking ``_send`` reply correlation: an interleaved live notification is
  never returned as an RPC result and is routed to its live queue.
"""

import asyncio
import queue
import uuid
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.cbor import encode
from surrealdb.errors import ConnectionUnavailableError
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod

WS_URL = "ws://localhost:8000"


# --------------------------------------------------------------------------- #
#  Fakes                                                                       #
# --------------------------------------------------------------------------- #


class _FakeSyncSocket:
    """Minimal stand-in for a ``websockets.sync`` client connection."""

    def __init__(self, frames: list[bytes]) -> None:
        self._frames = list(frames)
        self.sent: list[Any] = []

    def send(self, data: Any) -> None:
        self.sent.append(data)

    def recv(self, timeout: float | None = None, decode: bool | None = None) -> bytes:
        return self._frames.pop(0)

    def close(self) -> None:
        pass


class _ClosedAsyncSocket:
    """Async socket that yields nothing then stops, mimicking a closed WS."""

    def __aiter__(self) -> "_ClosedAsyncSocket":
        return self

    async def __anext__(self) -> bytes:
        raise StopAsyncIteration

    async def send(self, data: Any) -> None:
        pass

    async def close(self) -> None:
        pass


class _NeverRepliesAsyncSocket:
    """Async socket that accepts sends but never delivers a reply."""

    async def send(self, data: Any) -> None:
        pass

    async def close(self) -> None:
        pass


# --------------------------------------------------------------------------- #
#  #11c - blocking _send reply correlation                                     #
# --------------------------------------------------------------------------- #


def _notification_frame(live_id: str, action: str = "CREATE") -> bytes:
    return encode({"result": {"id": live_id, "action": action, "result": {"n": 1}}})


def _reply_frame(request_id: str) -> bytes:
    return encode({"id": request_id, "result": [{"status": "OK", "result": []}]})


def test_blocking_send_skips_interleaved_notification() -> None:
    """A live notification arriving before the reply is not returned as result."""
    conn = BlockingWsSurrealConnection(WS_URL)
    message = RequestMessage(RequestMethod.QUERY, query="SELECT 1", params={})
    live_id = str(uuid.uuid4())
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [_notification_frame(live_id), _reply_frame(message.id)]
    )

    response = conn._send(message, "query", bypass=True)

    # The reply, not the id-less notification, is returned.
    assert response["id"] == message.id
    assert "action" not in response


def test_blocking_send_routes_notification_to_live_queue() -> None:
    """An interleaved notification is routed to a registered subscriber queue."""
    conn = BlockingWsSurrealConnection(WS_URL)
    message = RequestMessage(RequestMethod.QUERY, query="SELECT 1", params={})
    live_id = str(uuid.uuid4())
    notifications: queue.Queue[dict[str, Any]] = queue.Queue()
    conn.live_queues[live_id] = [notifications]
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [_notification_frame(live_id, action="UPDATE"), _reply_frame(message.id)]
    )

    conn._send(message, "query", bypass=True)

    routed = notifications.get_nowait()
    assert routed["action"] == "UPDATE"
    assert str(routed["id"]) == live_id


def test_blocking_send_drops_notification_without_subscriber() -> None:
    """An interleaved notification with no subscriber is dropped, not returned."""
    conn = BlockingWsSurrealConnection(WS_URL)
    message = RequestMessage(RequestMethod.QUERY, query="SELECT 1", params={})
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [_notification_frame(str(uuid.uuid4())), _reply_frame(message.id)]
    )

    response = conn._send(message, "query", bypass=True)

    assert response["id"] == message.id
    assert conn.live_queues == {}


def test_blocking_subscribe_live_yields_from_socket() -> None:
    """subscribe_live reads notifications for its query id straight off the socket."""
    conn = BlockingWsSurrealConnection(WS_URL)
    live_id = str(uuid.uuid4())
    conn.socket = _FakeSyncSocket([_notification_frame(live_id)])  # type: ignore[assignment]

    gen = conn.subscribe_live(live_id)
    try:
        notif = next(gen)
        assert notif["action"] == "CREATE"
        # The consumer queue was registered while iterating.
        assert live_id in conn.live_queues
    finally:
        gen.close()

    # Closing the generator deregisters the consumer queue.
    assert live_id not in conn.live_queues


# --------------------------------------------------------------------------- #
#  #11b - async disconnect surfaces a typed error                              #
# --------------------------------------------------------------------------- #


async def test_async_recv_task_fails_pending_with_connection_error() -> None:
    """When the socket closes, pending futures get ConnectionUnavailableError."""
    conn = AsyncWsSurrealConnection(WS_URL)
    conn.loop = asyncio.get_running_loop()
    conn.socket = _ClosedAsyncSocket()

    fut: asyncio.Future[dict[str, Any]] = conn.loop.create_future()
    conn.qry["req-1"] = fut

    await conn._recv_task()

    assert conn.qry == {}
    assert fut.done()
    with pytest.raises(ConnectionUnavailableError):
        fut.result()


async def test_async_send_surfaces_connection_error_and_pops_key() -> None:
    """_send raises ConnectionUnavailableError (no KeyError) on socket close."""
    conn = AsyncWsSurrealConnection(WS_URL)
    conn.loop = asyncio.get_running_loop()
    conn.socket = _NeverRepliesAsyncSocket()

    message = RequestMessage(RequestMethod.QUERY, query="SELECT 1", params={})

    async def _run() -> dict[str, Any]:
        return await conn._send(message, "query")

    task = asyncio.create_task(_run())

    # Let _send register its future and block awaiting the reply.
    for _ in range(10):
        await asyncio.sleep(0)
        if conn.qry:
            break
    assert message.id in conn.qry

    # Mimic _recv_task's cleanup when the socket closes mid-request.
    conn.qry[message.id].set_exception(
        ConnectionUnavailableError("WebSocket connection closed.")
    )

    with pytest.raises(ConnectionUnavailableError):
        await task
    # finally: pop(query_id, None) leaves no dangling entry and never KeyErrors.
    assert conn.qry == {}


# --------------------------------------------------------------------------- #
#  #11a - async subscribe_live lifecycle                                       #
# --------------------------------------------------------------------------- #


async def test_async_subscribe_live_terminates_on_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kill() wakes the consumer, ends iteration, and deregisters the queue."""
    conn = AsyncWsSurrealConnection(WS_URL)
    suid = str(uuid.uuid4())
    subscription = await conn.subscribe_live(suid)

    conn.live_queues[suid][0].put_nowait({"action": "CREATE", "result": {"id": 1}})
    first = await asyncio.wait_for(subscription.__anext__(), timeout=1)
    assert first["action"] == "CREATE"

    async def _fake_send(
        message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(conn, "_send", _fake_send)

    await conn.kill(suid)

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(subscription.__anext__(), timeout=1)
    assert suid not in conn.live_queues


async def test_async_subscribe_live_terminates_on_close() -> None:
    """close() wakes any waiting consumers so their generators terminate."""
    conn = AsyncWsSurrealConnection(WS_URL)
    suid = str(uuid.uuid4())
    subscription = await conn.subscribe_live(suid)

    await conn.close()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(subscription.__anext__(), timeout=1)
    # The consumer deregistered its own queue on exit.
    assert conn.live_queues.get(suid) == []


async def test_async_subscribe_live_multi_subscriber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple consumers on one query id each receive notifications and stop."""
    conn = AsyncWsSurrealConnection(WS_URL)
    suid = str(uuid.uuid4())
    sub1 = await conn.subscribe_live(suid)
    sub2 = await conn.subscribe_live(suid)
    assert len(conn.live_queues[suid]) == 2

    # Fan-out mirrors _recv_task pushing to every registered queue.
    for consumer_queue in conn.live_queues[suid]:
        consumer_queue.put_nowait({"action": "CREATE", "result": {"id": 1}})

    assert (await asyncio.wait_for(sub1.__anext__(), timeout=1))["action"] == "CREATE"
    assert (await asyncio.wait_for(sub2.__anext__(), timeout=1))["action"] == "CREATE"

    async def _fake_send(
        message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(conn, "_send", _fake_send)
    await conn.kill(suid)

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(sub1.__anext__(), timeout=1)
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(sub2.__anext__(), timeout=1)
    assert suid not in conn.live_queues
