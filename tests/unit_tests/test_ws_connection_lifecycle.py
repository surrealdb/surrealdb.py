"""Server-independent tests for the blocking websocket's socket lifecycle.

Driven through fake sockets so they run on every CI leg, including the ones
with no reachable server (unlike the integration cover in
``tests/unit_tests/connections/test_ws_reconnect.py``).

Covers:
* ``close()`` releasing its reference, which is what lets ``connect()`` reopen
  - the async transport has always done this, the blocking one did not.
* ``connect(url)`` re-pointing a connection that is already open.
* ``__del__`` closing a socket the caller never closed, so the two
  ``websockets`` worker threads behind it are not leaked.
"""

import gc
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

WS_URL = "ws://localhost:8000"
OTHER_WS_URL = "ws://127.0.0.1:9999"


class _FakeSocket:
    """Stands in for a ``websockets.sync`` client connection.

    ``close()`` is the graceful handshake-then-join teardown; ``close_socket()``
    is the one that just drops the socket. They are counted separately because
    which one runs matters: the graceful close deadlocks in a destructor.
    """

    def __init__(self) -> None:
        self.close_calls = 0
        self.close_socket_calls = 0

    def close(self) -> None:
        self.close_calls += 1

    def close_socket(self) -> None:
        self.close_socket_calls += 1

    def send(self, data: Any) -> None:
        pass


@pytest.fixture
def connection(
    monkeypatch: pytest.MonkeyPatch,
) -> BlockingWsSurrealConnection:
    """A connection whose ``_connect_socket`` hands out fakes, never a socket."""
    conn = BlockingWsSurrealConnection(WS_URL)
    monkeypatch.setattr(conn, "_connect_socket", _FakeSocket)
    return conn


def test_close_releases_the_socket(connection: BlockingWsSurrealConnection) -> None:
    connection.connect()
    socket = connection.socket
    assert isinstance(socket, _FakeSocket)

    connection.close()

    assert socket.close_calls == 1
    # The reference has to go, not just the underlying connection: while it
    # stayed, `connect()` saw a socket and returned without doing anything.
    assert connection.socket is None


def test_close_is_idempotent(connection: BlockingWsSurrealConnection) -> None:
    connection.connect()
    socket = connection.socket
    assert isinstance(socket, _FakeSocket)

    connection.close()
    connection.close()

    assert socket.close_calls == 1


def test_connect_after_close_opens_a_new_socket(
    connection: BlockingWsSurrealConnection,
) -> None:
    connection.connect()
    first = connection.socket
    connection.close()

    connection.connect()

    assert isinstance(connection.socket, _FakeSocket)
    assert connection.socket is not first


def test_connect_is_a_no_op_while_open(
    connection: BlockingWsSurrealConnection,
) -> None:
    connection.connect()
    first = connection.socket

    connection.connect()

    assert connection.socket is first


def test_connect_with_a_url_repoints_an_open_connection(
    connection: BlockingWsSurrealConnection,
) -> None:
    """A new URL replaces the socket rather than being quietly dropped."""
    connection.connect()
    first = connection.socket
    assert isinstance(first, _FakeSocket)

    connection.connect(OTHER_WS_URL)

    assert first.close_calls == 1, "the socket for the old endpoint stayed open"
    assert connection.socket is not first
    assert connection.raw_url == f"{OTHER_WS_URL}/rpc"
    assert connection.host == "127.0.0.1"
    assert connection.port == 9999


def test_connect_with_the_current_url_keeps_the_socket(
    connection: BlockingWsSurrealConnection,
) -> None:
    """Re-pointing at the endpoint already in use must not cost the session.

    Reconnecting starts a fresh, anonymous server-side session, so tearing the
    socket down here would silently undo a completed ``signin()`` and
    ``use()`` - a defensive ``connect(url)`` would turn working code into
    permission errors.
    """
    connection.connect(WS_URL)
    first = connection.socket
    assert isinstance(first, _FakeSocket)

    connection.connect(WS_URL)

    assert connection.socket is first
    assert first.close_calls == 0


def test_connect_recognises_the_current_url_with_a_trailing_slash(
    connection: BlockingWsSurrealConnection,
) -> None:
    """Same endpoint, spelled with a trailing slash: still a no-op."""
    connection.connect(WS_URL)
    first = connection.socket

    connection.connect(f"{WS_URL}/")

    assert connection.socket is first


@pytest.mark.parametrize(
    "target",
    [
        pytest.param("ws://localhost:8000/gateway", id="path-only-difference"),
        pytest.param("wss://localhost:8000", id="scheme-difference"),
        pytest.param("ws://localhost:8001", id="port-difference"),
        pytest.param("ws://127.0.0.1:8000", id="host-difference"),
    ],
)
def test_connect_applies_a_url_that_differs_anywhere(
    connection: BlockingWsSurrealConnection, target: str
) -> None:
    """Whatever part of the URL changed, the connection has to move to it.

    Deciding *whether to reconnect* and deciding *whether to apply the URL* are
    separate questions. Folding them together drops any part of the URL the
    comparison does not look at - the connection then opens against the old
    endpoint while reporting the new one, which is the defect this method was
    fixed for in the first place.
    """
    connection.connect()

    connection.connect(target)

    assert connection.raw_url == f"{target}/rpc"
    assert connection.url.raw_url == target


@pytest.mark.parametrize(
    "target",
    [
        pytest.param("ws://localhost:8000/gateway", id="path-only-difference"),
        pytest.param("ws://localhost:9999", id="port-difference"),
    ],
)
def test_connect_applies_a_url_before_any_socket_exists(
    connection: BlockingWsSurrealConnection, target: str
) -> None:
    """The first ``connect(url)`` on a fresh connection must honour *url*.

    There is no socket to compare against here, so any implementation that
    only applies the URL when it decides to reconnect drops it entirely and
    opens against the URL the connection was constructed with.
    """
    assert connection.socket is None

    connection.connect(target)

    assert connection.raw_url == f"{target}/rpc"
    assert connection.url.raw_url == target
    assert connection.port == (9999 if target.endswith("9999") else 8000)


def test_a_dropped_connection_closes_its_socket() -> None:
    """Letting a connection go out of scope releases the socket behind it.

    Each open websocket holds a TCP socket and two ``websockets`` worker
    threads. Nothing else releases them, so building connections in a loop and
    letting them fall out of scope accumulated all three per connection for the
    lifetime of the process.
    """
    socket = _FakeSocket()
    connection = BlockingWsSurrealConnection(WS_URL)
    connection.socket = socket  # type: ignore[assignment]

    del connection
    gc.collect()

    # The socket is dropped, *not* closed gracefully: the graceful path joins
    # the reader thread, which never returns at interpreter shutdown and stalls
    # for the close timeout whenever the peer has gone quiet.
    assert socket.close_socket_calls == 1
    assert socket.close_calls == 0, "the destructor used the blocking teardown"


def test_dropping_a_connection_that_never_opened_one_is_quiet() -> None:
    """``__del__`` runs even when ``__init__`` did not finish; it must not raise."""
    connection = BlockingWsSurrealConnection(WS_URL)
    assert connection.socket is None

    del connection
    gc.collect()


def test_del_survives_a_socket_that_raises_on_teardown() -> None:
    """A teardown failure during GC is unraisable, so it must be swallowed.

    ``close_socket`` is the method the destructor actually calls; making the
    graceful ``close`` raise instead tests nothing, because the destructor
    never reaches it.
    """

    class _AngrySocket(_FakeSocket):
        def close_socket(self) -> None:
            raise OSError("socket already gone")

    connection = BlockingWsSurrealConnection(WS_URL)
    connection.socket = _AngrySocket()  # type: ignore[assignment]

    # Calling it directly rather than via `del`: an exception escaping __del__
    # is printed and ignored, so a GC-driven test would pass either way.
    connection.__del__()
