"""The same token and session methods on the blocking websocket and on HTTP."""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from surrealdb import Null
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import ServerError, UnsupportedFeatureError


@pytest.fixture
def ws(connection_params: dict[str, Any]) -> Iterator[BlockingWsSurrealConnection]:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def http(connection_params: dict[str, Any]) -> Iterator[BlockingHttpSurrealConnection]:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
async def ahttp(
    connection_params: dict[str, Any],
) -> AsyncIterator[AsyncHttpSurrealConnection]:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    try:
        yield connection
    finally:
        await connection.close()


def test_blocking_ws_refresh_and_revoke(
    ws: BlockingWsSurrealConnection, record_user: dict[str, Any]
) -> None:
    first = ws.signup(record_user)
    renewed = ws.refresh()
    assert renewed.refresh not in (None, first.refresh)
    assert ws.token == renewed.access
    assert ws.query("RETURN $access;").first() == record_user["access"]
    ws.revoke()
    with pytest.raises(ServerError):
        ws.refresh(renewed)


def test_blocking_ws_reset_sessions_and_fork(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    ws.use(connection_params["namespace"], connection_params["database_name"])
    ws.let("where", "root")

    fork = ws.fork_session()
    assert fork.id in ws.sessions()
    assert fork.query("RETURN [$where, session::db()];").first() == [
        "root",
        connection_params["database_name"],
    ]
    fork.reset()
    fork.use(connection_params["namespace"], connection_params["database_name"])
    assert fork.query("RETURN $where;").first() is None
    fork.close_session()

    ws.reset()
    assert ws.token is None
    assert ws.namespace is None


def test_blocking_ws_partial_use(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    ws.use(connection_params["namespace"], connection_params["database_name"])
    ws.use(database="other_db")
    assert ws.query("RETURN [session::ns(), session::db()];").first() == [
        connection_params["namespace"],
        "other_db",
    ]
    ws.use(Null, Null)
    assert ws.namespace is None


def test_blocking_ws_health(ws: BlockingWsSurrealConnection) -> None:
    ws.health()


def test_http_refresh_and_revoke(
    http: BlockingHttpSurrealConnection, record_user: dict[str, Any]
) -> None:
    first = http.signup(record_user)
    renewed = http.refresh()
    assert renewed.refresh not in (None, first.refresh)
    assert http.token == renewed.access
    http.use(record_user["namespace"], record_user["database"])
    assert http.query("RETURN $access;").first() == record_user["access"]
    http.revoke()
    with pytest.raises(ValueError, match="refresh token"):
        http.refresh()


async def test_async_http_refresh(
    ahttp: AsyncHttpSurrealConnection, record_user: dict[str, Any]
) -> None:
    await ahttp.signup(record_user)
    renewed = await ahttp.refresh()
    assert ahttp.token == renewed.access
    await ahttp.revoke()
    with pytest.raises(ServerError):
        await ahttp.refresh(renewed)


def test_http_reset_and_partial_use(
    http: BlockingHttpSurrealConnection, connection_params: dict[str, Any]
) -> None:
    http.signin(connection_params["vars_params"])
    http.use(connection_params["namespace"], connection_params["database_name"])
    http.use(database="other_db")
    assert http.namespace == connection_params["namespace"]
    assert http.database == "other_db"
    http.let("answer", 42)
    http.reset()
    assert (http.namespace, http.database, http.token, http.vars) == (
        None,
        None,
        None,
        {},
    )
    with pytest.raises(UnsupportedFeatureError):
        http.sessions()


async def test_http_health(
    http: BlockingHttpSurrealConnection, ahttp: AsyncHttpSurrealConnection
) -> None:
    http.health()
    await ahttp.health()
