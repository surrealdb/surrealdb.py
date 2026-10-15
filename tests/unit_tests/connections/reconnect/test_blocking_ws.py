"""The blocking websocket reconnects when it next needs the socket.

It has no background reader, so a drop is noticed by the request or live
subscription that next uses the socket. That one reconnects and replays the
state before carrying on, so the caller sees the answer it would have had.
"""

import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from websockets.protocol import State

from surrealdb import ReconnectOptions
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.events import EVENTS
from surrealdb.errors import ConnectionUnavailableError
from surrealdb.features import Features
from tests.unit_tests.connections.reconnect.proxy import DroppableProxy

_FAST = ReconnectOptions(retry_delay=0.05, retry_delay_max=0.2)


def _drop(proxy: DroppableProxy, db: BlockingWsSurrealConnection) -> None:
    """Cut the connection and wait for the client's socket to notice.

    A request sent in the instant after the cut can still be written into the
    dead connection, and then fails rather than reconnecting, since it may have
    run. That case has a test of its own; the rest want the common one, a drop
    noticed before the next request.
    """
    socket = db.socket
    assert socket is not None
    proxy.drop()
    deadline = time.monotonic() + 5
    while socket.state is State.OPEN and time.monotonic() < deadline:
        time.sleep(0.01)


class _Events:
    def __init__(self, db: BlockingWsSurrealConnection) -> None:
        self.seen: list[tuple[str, tuple[Any, ...]]] = []
        for event in EVENTS:
            db.subscribe(event, self._recorder(event))

    def _recorder(self, event: str) -> Any:
        def record(*payload: Any) -> None:
            self.seen.append((event, payload))

        return record

    def names(self) -> list[str]:
        return [name for name, _ in self.seen]


def _connected(
    proxy: DroppableProxy,
    connection_params: dict[str, Any],
    reconnect: bool | ReconnectOptions = _FAST,
) -> BlockingWsSurrealConnection:
    db = BlockingWsSurrealConnection(proxy.ws_url, reconnect=reconnect)
    db.signin(connection_params["vars_params"])
    db.use(connection_params["namespace"], connection_params["database_name"])
    return db


@pytest.fixture
def db(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> Iterator[BlockingWsSurrealConnection]:
    connection = _connected(proxy, connection_params)
    try:
        yield connection
    finally:
        connection.close()


def test_status_follows_the_connection(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = BlockingWsSurrealConnection(proxy.ws_url, reconnect=_FAST)
    events = _Events(db)
    assert db.status == "disconnected"
    db.connect()
    assert db.is_connected
    assert events.names() == ["connecting", "connected"]
    db.close()
    assert not db.is_connected
    assert events.names()[-1] == "disconnected"


def test_the_next_request_reconnects_and_replays_the_session(
    db: BlockingWsSurrealConnection,
    proxy: DroppableProxy,
    connection_params: dict[str, Any],
) -> None:
    db.let("answer", 42)
    events = _Events(db)

    _drop(proxy, db)
    result = db.query("RETURN [$answer, session::ns(), session::db()];").first()

    assert result == [
        42,
        connection_params["namespace"],
        connection_params["database_name"],
    ]
    assert isinstance(db.query("INFO FOR ROOT;").first(), dict)
    assert events.names()[:2] == ["reconnecting", "connected"]
    assert db.is_connected


def test_a_live_subscription_carries_on_across_a_reconnect(
    db: BlockingWsSurrealConnection,
    proxy: DroppableProxy,
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query(
        "DEFINE TABLE IF NOT EXISTS reconnect_live; DELETE reconnect_live;"
    ).execute()
    query_id = db.live("reconnect_live")
    subscription = db.subscribe_live(query_id)

    _drop(proxy, db)
    # Any use of the socket notices the drop and replays the live query.
    assert db.query("RETURN 1;").first() == 1
    blocking_ws_connection.query("CREATE reconnect_live:one SET n = 1;").execute()

    notification = next(subscription)
    assert notification["action"] == "CREATE"
    assert notification["id"] == query_id
    db.kill(query_id)
    blocking_ws_connection.query("DELETE reconnect_live;").execute()


def test_a_subscription_reading_when_the_socket_drops_reconnects_itself(
    db: BlockingWsSurrealConnection,
    proxy: DroppableProxy,
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query(
        "DEFINE TABLE IF NOT EXISTS reconnect_live; DELETE reconnect_live;"
    ).execute()
    query_id = db.live("reconnect_live")
    subscription = db.subscribe_live(query_id)
    events = _Events(db)

    def create_once_reconnected(*_payload: Any) -> None:
        blocking_ws_connection.query("CREATE reconnect_live:two SET n = 2;").execute()

    db.subscribe("connected", create_once_reconnected)
    proxy.drop()

    notification = next(subscription)
    assert notification["action"] == "CREATE"
    assert notification["id"] == query_id
    assert "reconnecting" in events.names()
    db.kill(query_id)
    blocking_ws_connection.query("DELETE reconnect_live;").execute()


def test_sessions_are_replayed(
    db: BlockingWsSurrealConnection,
    proxy: DroppableProxy,
    connection_params: dict[str, Any],
) -> None:
    if not db.is_feature_supported(Features.SESSIONS):
        pytest.skip("sessions need SurrealDB 3.0.0 or later")
    session = db.new_session()
    session.use(connection_params["namespace"], "reconnect_session_db")
    session.let("where", "session")
    db.let("where", "root")

    _drop(proxy, db)

    assert session.query("RETURN [$where, session::db()];").first() == [
        "session",
        "reconnect_session_db",
    ]
    assert db.query("RETURN $where;").first() == "root"
    session.close_session()


def test_without_reconnect_the_next_request_starts_afresh(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = _connected(proxy, connection_params, reconnect=False)
    try:
        db.let("answer", 42)
        events = _Events(db)
        _drop(proxy, db)
        db.use(connection_params["namespace"], connection_params["database_name"])
        assert db.query("RETURN $answer;").first() is None
        assert "reconnecting" not in events.names()
        assert db.token is None
    finally:
        db.close()


def test_giving_up_raises_and_forgets_the_session(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    db = _connected(
        proxy, connection_params, ReconnectOptions(attempts=2, retry_delay=0.01)
    )
    try:
        db.let("answer", 42)
        events = _Events(db)
        proxy.refuse()
        _drop(proxy, db)
        with pytest.raises(ConnectionUnavailableError, match=r"2 attempt\(s\)"):
            db.query("RETURN 1;").execute()
        assert events.names()[-2:] == ["disconnected", "error"]
        assert db.namespace is None

        proxy.accept()
        db.use(connection_params["namespace"], connection_params["database_name"])
        assert db.query("RETURN $answer;").first() is None
    finally:
        db.close()


def test_a_request_cut_off_mid_flight_fails_and_the_next_one_reconnects(
    db: BlockingWsSurrealConnection, proxy: DroppableProxy
) -> None:
    db.let("answer", 42)
    timer = threading.Timer(0.2, proxy.drop)
    timer.start()
    try:
        with pytest.raises(ConnectionUnavailableError):
            db.query("RETURN sleep(1s);").execute()
    finally:
        timer.join()
    assert db.query("RETURN $answer;").first() == 42


def _iterate_in_background(subscription: Any) -> tuple[threading.Thread, list[object]]:
    """Iterate *subscription* on a thread, recording how the iteration ended."""
    outcome: list[object] = []

    def run() -> None:
        try:
            for _ in subscription:
                pass
            outcome.append("ended")
        except ConnectionUnavailableError as exc:
            outcome.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    time.sleep(0.3)
    return thread, outcome


def test_a_reading_subscription_hears_when_a_dead_socket_is_replaced(
    proxy: DroppableProxy,
    connection_params: dict[str, Any],
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query("DEFINE TABLE IF NOT EXISTS reconnect_live;").execute()
    db = _connected(proxy, connection_params, reconnect=False)
    try:
        subscription = db.subscribe_live(db.live("reconnect_live"))
        thread, outcome = _iterate_in_background(subscription)
        with db._lock:
            _drop(proxy, db)
            db._ready_locked()
        thread.join(5)
        assert len(outcome) == 1
        assert isinstance(outcome[0], ConnectionUnavailableError)
    finally:
        db.close()


def test_a_reconnect_ends_an_attached_subscription(
    db: BlockingWsSurrealConnection,
    proxy: DroppableProxy,
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query("DEFINE TABLE IF NOT EXISTS reconnect_live;").execute()
    live_id = db.query("LIVE SELECT * FROM reconnect_live;").first()
    subscription = db.live_of(str(live_id))
    thread, outcome = _iterate_in_background(subscription)
    with db._lock:
        _drop(proxy, db)
        db._ready_locked()
    thread.join(5)
    assert len(outcome) == 1
    assert isinstance(outcome[0], ConnectionUnavailableError)
    assert not subscription.is_alive
