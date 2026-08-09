"""Session / transaction wrappers forward the non-builder RPCs too.

``AsyncSurrealSession`` / ``BlockingSurrealSession`` (and the transaction
equivalents) wrap a connection and thread ``session`` / ``txn`` onto every
operation. ``query_raw``, ``info``, and ``version`` were missing from that
sweep, so calling them on a session raised ``AttributeError`` even though
the underlying connection methods already accepted the context.

These server-independent tests pin the forwarding: the wrapper must reach
the connection method *and* stamp the session (and, for a transaction,
the txn) onto the outgoing request message.
"""

from typing import Any
from uuid import uuid4

import pytest

from surrealdb.connections.async_ws import (
    AsyncSurrealSession,
    AsyncSurrealTransaction,
    AsyncWsSurrealConnection,
)
from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingSurrealTransaction,
    BlockingWsSurrealConnection,
)
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


def _capture(store: dict[str, Any]) -> Any:
    def fake_send(
        message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        store["message"] = message
        return {"result": []}

    return fake_send


def _async_capture(store: dict[str, Any]) -> Any:
    async def fake_send(
        message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        store["message"] = message
        return {"result": []}

    return fake_send


async def test_async_session_query_raw_forwards_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _async_capture(store))
    session_id = uuid4()
    session = AsyncSurrealSession(conn, session_id)

    await session.query_raw("SELECT * FROM person WHERE age > $age", vars={"age": 18})

    message = store["message"]
    assert message.method == RequestMethod.QUERY
    assert message.kwargs["query"] == "SELECT * FROM person WHERE age > $age"
    assert message.kwargs["params"] == {"age": 18}
    assert message.kwargs["session"] == session_id
    assert "txn" not in message.kwargs


async def test_async_session_info_and_version_forward_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _async_capture(store))
    session_id = uuid4()
    session = AsyncSurrealSession(conn, session_id)

    await session.info()
    assert store["message"].method == RequestMethod.INFO
    assert store["message"].kwargs["session"] == session_id

    await session.version()
    assert store["message"].method == RequestMethod.VERSION
    assert store["message"].kwargs["session"] == session_id


async def test_async_transaction_query_raw_forwards_session_and_txn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _async_capture(store))
    session_id, txn_id = uuid4(), uuid4()
    txn = AsyncSurrealTransaction(conn, session_id, txn_id)

    await txn.query_raw("INFO FOR DB")

    message = store["message"]
    assert message.kwargs["session"] == session_id
    assert message.kwargs["txn"] == txn_id


async def test_async_transaction_info_and_version_forward_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _async_capture(store))
    session_id, txn_id = uuid4(), uuid4()
    txn = AsyncSurrealTransaction(conn, session_id, txn_id)

    await txn.info()
    assert store["message"].kwargs["session"] == session_id

    await txn.version()
    assert store["message"].kwargs["session"] == session_id


def test_blocking_session_query_raw_forwards_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _capture(store))
    session_id = uuid4()
    session = BlockingSurrealSession(conn, session_id)

    session.query_raw("SELECT * FROM person WHERE age > $age", {"age": 21})

    message = store["message"]
    assert message.kwargs["params"] == {"age": 21}
    assert message.kwargs["session"] == session_id
    assert "txn" not in message.kwargs


def test_blocking_session_info_and_version_forward_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _capture(store))
    session_id = uuid4()
    session = BlockingSurrealSession(conn, session_id)

    session.info()
    assert store["message"].method == RequestMethod.INFO
    assert store["message"].kwargs["session"] == session_id

    session.version()
    assert store["message"].method == RequestMethod.VERSION
    assert store["message"].kwargs["session"] == session_id


def test_blocking_transaction_query_raw_forwards_session_and_txn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _capture(store))
    session_id, txn_id = uuid4(), uuid4()
    txn = BlockingSurrealTransaction(conn, session_id, txn_id)

    txn.query_raw("INFO FOR DB")

    message = store["message"]
    assert message.kwargs["session"] == session_id
    assert message.kwargs["txn"] == txn_id


def test_blocking_transaction_info_and_version_forward_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _capture(store))
    session_id, txn_id = uuid4(), uuid4()
    txn = BlockingSurrealTransaction(conn, session_id, txn_id)

    txn.info()
    assert store["message"].kwargs["session"] == session_id

    txn.version()
    assert store["message"].kwargs["session"] == session_id
