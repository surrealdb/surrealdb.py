"""The async websocket reconnects on its own, and the server sees no gap.

Each test cuts the TCP connection under a working client and then checks that
what the server had been told - who is signed in, which namespace and database,
the variables, the live queries - is in place again on the new connection.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from surrealdb import ReconnectOptions
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.events import EVENTS
from surrealdb.errors import ConnectionUnavailableError
from surrealdb.features import Features
from surrealdb.types import Tokens
from tests.unit_tests.connections.reconnect.conftest import DroppableProxy

_FAST = ReconnectOptions(retry_delay=0.05, retry_delay_max=0.2)
_WAIT = 10.0


class _Events:
    """Records every event a connection publishes, in order."""

    def __init__(self, db: AsyncWsSurrealConnection) -> None:
        self.seen: list[tuple[str, tuple[Any, ...]]] = []
        self._changed = asyncio.Event()
        for event in EVENTS:
            db.subscribe(event, self._recorder(event))

    def _recorder(self, event: str) -> Any:
        def record(*payload: Any) -> None:
            self.seen.append((event, payload))
            self._changed.set()

        return record

    def names(self) -> list[str]:
        return [name for name, _ in self.seen]

    async def wait_for(self, event: str, after: int = 0) -> None:
        """Wait until *event* has been published since index *after*."""

        async def _poll() -> None:
            while event not in self.names()[after:]:
                self._changed.clear()
                await self._changed.wait()

        await asyncio.wait_for(_poll(), _WAIT)


async def _connected(
    proxy: DroppableProxy,
    connection_params: dict[str, Any],
    reconnect: bool | ReconnectOptions = _FAST,
) -> AsyncWsSurrealConnection:
    db = AsyncWsSurrealConnection(proxy.ws_url, reconnect=reconnect)
    await db.signin(connection_params["vars_params"])
    await db.use(connection_params["namespace"], connection_params["database_name"])
    return db


@pytest.fixture
async def db(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> AsyncIterator[AsyncWsSurrealConnection]:
    connection = await _connected(proxy, connection_params)
    try:
        yield connection
    finally:
        await connection.close()


async def _drop_and_recover(
    db: AsyncWsSurrealConnection, events: _Events, proxy: DroppableProxy
) -> None:
    mark = len(events.seen)
    proxy.drop()
    await events.wait_for("reconnecting", mark)
    await events.wait_for("connected", mark)


async def test_status_follows_the_connection(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = AsyncWsSurrealConnection(proxy.ws_url, reconnect=_FAST)
    events = _Events(db)
    assert db.status == "disconnected"
    assert not db.is_connected
    await db.connect()
    assert db.is_connected
    assert events.names() == ["connecting", "connected"]
    assert events.seen[1][1] == (db.server_version,)
    await db.close()
    assert db.status == "disconnected"
    assert events.names()[-1] == "disconnected"


async def test_reconnect_replays_auth_namespace_database_and_variables(
    db: AsyncWsSurrealConnection,
    proxy: DroppableProxy,
    connection_params: dict[str, Any],
) -> None:
    await db.let("answer", 42)
    events = _Events(db)

    await _drop_and_recover(db, events, proxy)

    assert db.status == "connected"
    result = await db.query(
        "RETURN [$answer, session::ns(), session::db(), $auth.id OR $session.ac];"
    ).first()
    assert isinstance(result, list)
    assert result[:3] == [
        42,
        connection_params["namespace"],
        connection_params["database_name"],
    ]
    # Only a root user can read the root's definitions.
    assert isinstance(await db.query("INFO FOR ROOT;").first(), dict)
    assert db.namespace == connection_params["namespace"]
    assert db.database == connection_params["database_name"]


async def test_a_request_made_while_reconnecting_waits_for_the_replay(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = await _connected(
        proxy,
        connection_params,
        ReconnectOptions(retry_delay=0.3, retry_delay_jitter=0),
    )
    try:
        await db.let("answer", 42)
        events = _Events(db)
        proxy.drop()
        await events.wait_for("reconnecting")
        assert await db.query("RETURN $answer;").first() == 42
    finally:
        await db.close()


async def test_a_live_query_keeps_its_id_across_a_reconnect(
    db: AsyncWsSurrealConnection,
    proxy: DroppableProxy,
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await async_ws_connection.query(
        "DEFINE TABLE IF NOT EXISTS reconnect_live; DELETE reconnect_live;"
    )
    query_id = await db.live("reconnect_live")
    subscription = await db.subscribe_live(query_id)
    events = _Events(db)

    await _drop_and_recover(db, events, proxy)
    await async_ws_connection.query("CREATE reconnect_live:one SET n = 1;")

    notification = await asyncio.wait_for(subscription.__anext__(), _WAIT)
    assert notification["action"] == "CREATE"
    assert notification["id"] == query_id

    await db.kill(query_id)
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(subscription.__anext__(), _WAIT)
    await async_ws_connection.query("DELETE reconnect_live;")


async def test_a_killed_live_query_is_not_restarted(
    db: AsyncWsSurrealConnection, proxy: DroppableProxy
) -> None:
    query_id = await db.live("reconnect_live")
    await db.kill(query_id)
    events = _Events(db)

    await _drop_and_recover(db, events, proxy)

    assert "error" not in events.names()
    assert db._registry.live == {}


async def test_sessions_are_replayed(
    db: AsyncWsSurrealConnection,
    proxy: DroppableProxy,
    connection_params: dict[str, Any],
) -> None:
    if not db.is_feature_supported(Features.SESSIONS):
        pytest.skip("sessions need SurrealDB 3.0.0 or later")
    session = await db.new_session()
    await session.use(connection_params["namespace"], "reconnect_session_db")
    await session.let("where", "session")
    await db.let("where", "root")
    events = _Events(db)

    await _drop_and_recover(db, events, proxy)

    assert await session.query("RETURN [$where, session::db()];").first() == [
        "session",
        "reconnect_session_db",
    ]
    assert await db.query("RETURN $where;").first() == "root"
    await session.close_session()


async def test_without_reconnect_a_drop_forgets_the_session(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = await _connected(proxy, connection_params, reconnect=False)
    try:
        await db.let("answer", 42)
        events = _Events(db)
        proxy.drop()
        await events.wait_for("disconnected")
        assert "reconnecting" not in events.names()
        assert db.namespace is None
        assert db.token is None
        # The next request opens a fresh connection the server knows nothing
        # about.
        await db.use(connection_params["namespace"], connection_params["database_name"])
        assert await db.query("RETURN $answer;").first() is None
    finally:
        await db.close()


async def test_giving_up_reports_the_failure_and_forgets_the_session(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = await _connected(
        proxy, connection_params, ReconnectOptions(attempts=2, retry_delay=0.01)
    )
    try:
        await db.let("answer", 42)
        query_id = await db.live("reconnect_live")
        subscription = await db.subscribe_live(query_id)
        events = _Events(db)
        proxy.refuse()
        proxy.drop()
        await events.wait_for("disconnected")

        errors = [payload[0] for name, payload in events.seen if name == "error"]
        assert isinstance(errors[-1], ConnectionUnavailableError)
        assert "2 attempt(s)" in str(errors[-1])
        with pytest.raises(ConnectionUnavailableError):
            await asyncio.wait_for(subscription.__anext__(), _WAIT)
        with pytest.raises(ConnectionUnavailableError):
            await db.query("RETURN 1;")

        proxy.accept()
        await db.use(connection_params["namespace"], connection_params["database_name"])
        assert await db.query("RETURN $answer;").first() is None
        assert db.status == "connected"
    finally:
        await db.close()


async def test_close_stops_a_reconnect_in_progress(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = await _connected(proxy, connection_params, ReconnectOptions(retry_delay=0.2))
    events = _Events(db)
    proxy.refuse()
    proxy.drop()
    await events.wait_for("reconnecting")
    await db.close()
    assert db.status == "disconnected"
    mark = len(events.seen)
    await asyncio.sleep(0.5)
    assert "connecting" not in events.names()[mark:]
    assert "connected" not in events.names()[mark:]


async def test_auth_and_using_events(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = AsyncWsSurrealConnection(proxy.ws_url, reconnect=_FAST)
    events = _Events(db)
    try:
        tokens = await db.signin(connection_params["vars_params"])
        await db.use(connection_params["namespace"], connection_params["database_name"])
        await db.invalidate()
    finally:
        await db.close()
    auth = [payload for name, payload in events.seen if name == "auth"]
    assert isinstance(auth[0][0], Tokens)
    assert auth[0][0].access == tokens.access
    assert auth[0][1] is None
    assert auth[-1] == (None, None)
    using = [payload for name, payload in events.seen if name == "using"]
    assert using == [
        (connection_params["namespace"], connection_params["database_name"], None)
    ]


async def test_an_async_listener_is_scheduled(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = AsyncWsSurrealConnection(proxy.ws_url, reconnect=_FAST)
    heard = asyncio.Event()

    async def on_connected(_version: str | None) -> None:
        heard.set()

    db.subscribe("connected", on_connected)
    try:
        await db.connect()
        await asyncio.wait_for(heard.wait(), _WAIT)
    finally:
        await db.close()


async def test_a_failing_listener_does_not_break_the_connection(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = AsyncWsSurrealConnection(proxy.ws_url, reconnect=_FAST)

    def broken(*_payload: Any) -> None:
        raise RuntimeError("listener bug")

    db.subscribe("connected", broken)
    unsubscribe = db.subscribe("auth", broken)
    try:
        await db.signin(connection_params["vars_params"])
        unsubscribe()
        assert await db.query("RETURN 1;").first() == 1
    finally:
        await db.close()
