"""``query_raw`` bound-variable kwarg is unified to ``vars`` (#5).

Every connection previously spelled the bound-variable argument ``params``
while ``query`` spelled it ``vars``. These server-independent tests pin the
new, single vocabulary: ``query_raw(query, vars=...)`` must accept the
``vars`` keyword and forward it into the wire-level ``params`` field of the
QUERY request message.
"""

from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


def _capture(store: dict[str, Any]) -> Any:
    """Build a fake ``_send`` that records the outgoing RequestMessage."""

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


async def test_async_ws_query_raw_vars_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _async_capture(store))

    await conn.query_raw("SELECT * FROM person WHERE age > $age", vars={"age": 18})

    message = store["message"]
    assert message.method == RequestMethod.QUERY
    assert message.kwargs["query"] == "SELECT * FROM person WHERE age > $age"
    assert message.kwargs["params"] == {"age": 18}


async def test_async_ws_query_raw_vars_defaults_to_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _async_capture(store))

    await conn.query_raw("INFO FOR DB")

    assert store["message"].kwargs["params"] == {}


def test_blocking_ws_query_raw_vars_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _capture(store))

    conn.query_raw("SELECT * FROM person WHERE age > $age", vars={"age": 18})

    message = store["message"]
    assert message.kwargs["query"] == "SELECT * FROM person WHERE age > $age"
    assert message.kwargs["params"] == {"age": 18}


def test_blocking_ws_query_raw_vars_positional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bound-variable argument stays positional-compatible after the rename."""
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _capture(store))

    conn.query_raw("SELECT * FROM person WHERE age > $age", {"age": 21})

    assert store["message"].kwargs["params"] == {"age": 21}


async def test_async_http_query_raw_vars_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncHttpSurrealConnection("http://localhost:8000")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _async_capture(store))

    await conn.query_raw("SELECT * FROM person WHERE age > $age", vars={"age": 18})

    message = store["message"]
    assert message.kwargs["query"] == "SELECT * FROM person WHERE age > $age"
    assert message.kwargs["params"] == {"age": 18}


def test_blocking_http_query_raw_vars_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingHttpSurrealConnection("http://localhost:8000")
    store: dict[str, Any] = {}
    monkeypatch.setattr(conn, "_send", _capture(store))

    conn.query_raw("SELECT * FROM person WHERE age > $age", vars={"age": 18})

    message = store["message"]
    assert message.kwargs["query"] == "SELECT * FROM person WHERE age > $age"
    assert message.kwargs["params"] == {"age": 18}
