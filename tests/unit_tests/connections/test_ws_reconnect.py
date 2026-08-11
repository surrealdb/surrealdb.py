"""A closed websocket connection can be opened again, and dropping a blocking
one does not leak the threads behind it.

Against a real server, because the defects are in what the socket does rather
than in what the SDK records: blocking ``close()`` left the closed socket in
place, so ``connect()`` returned without reconnecting and every later call
failed on a dead socket; a connection that went out of scope kept its socket
and both ``websockets`` worker threads alive for the rest of the process; and
on both transports ``connect(url)`` quietly dropped the new URL when a socket
was already open.
"""

import gc
import subprocess
import sys
import textwrap
import threading
import time
from typing import Any

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def _signed_in(params: dict[str, Any]) -> BlockingWsSurrealConnection:
    connection = BlockingWsSurrealConnection(params["ws_url"])
    connection.signin(params["vars_params"])
    connection.use(
        namespace=params["namespace"],
        database=params["database_name"],
    )
    return connection


def test_connection_works_again_after_close(connection_params: dict[str, Any]) -> None:
    """The full recover-a-closed-connection path, end to end."""
    connection = _signed_in(connection_params)
    try:
        assert connection.query("RETURN 1").first() == 1

        connection.close()
        connection.connect()

        # A new socket is a new server-side session, so it starts
        # unauthenticated - as documented on `close()`.
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        assert connection.query("RETURN 2").first() == 2
    finally:
        connection.close()


def test_lazy_reconnect_after_close(connection_params: dict[str, Any]) -> None:
    """``_send`` reopens too, so a closed connection is not a dead object."""
    connection = _signed_in(connection_params)
    try:
        connection.close()

        # No explicit connect() - the first call opens the socket, exactly as
        # it does before any connect() on a fresh connection.
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        assert connection.query("RETURN 3").first() == 3
    finally:
        connection.close()


def test_repointing_an_open_connection(connection_params: dict[str, Any]) -> None:
    """``connect(url)`` moves an open connection to the new endpoint."""
    connection = _signed_in(connection_params)
    try:
        # Same server, spelled differently, so the reconnect is observable
        # without needing a second instance running.
        relocated = connection_params["ws_url"].replace("localhost", "127.0.0.1")
        connection.connect(relocated)

        assert connection.host == "127.0.0.1"
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        assert connection.query("RETURN 4").first() == 4
    finally:
        connection.close()


def test_repointing_at_the_same_url_keeps_the_session(
    connection_params: dict[str, Any],
) -> None:
    """A defensive ``connect(url)`` must not throw the session away.

    Reconnecting starts a fresh, anonymous server-side session, so tearing the
    socket down for a url the connection is already using would turn a
    completed ``signin()`` into ``NotAllowedError`` on the next query.
    """
    connection = _signed_in(connection_params)
    try:
        connection.connect(connection_params["ws_url"])

        # No signin() in between - the original session has to still be there.
        assert connection.query("RETURN 6").first() == 6
    finally:
        connection.close()


async def test_async_repointing_at_the_same_url_keeps_the_session(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    try:
        await connection.signin(connection_params["vars_params"])
        await connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )

        await connection.connect(connection_params["ws_url"])

        assert await connection.query("RETURN 7").first() == 7
    finally:
        await connection.close()


async def test_async_repointing_an_open_connection(
    connection_params: dict[str, Any],
) -> None:
    """The async transport re-points too, rather than swallowing the new URL."""
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    try:
        await connection.signin(connection_params["vars_params"])
        await connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        first_socket = connection.socket

        relocated = connection_params["ws_url"].replace("localhost", "127.0.0.1")
        await connection.connect(relocated)

        assert connection.host == "127.0.0.1"
        assert connection.socket is not first_socket
        await connection.signin(connection_params["vars_params"])
        await connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        assert await connection.query("RETURN 5").first() == 5
    finally:
        await connection.close()


def _worker_threads() -> set[int]:
    """Ids of the ``websockets`` worker threads currently alive."""
    return {
        thread.ident
        for thread in threading.enumerate()
        if thread.ident is not None
        and ("recv_events" in thread.name or "keepalive" in thread.name)
    }


def test_dropped_connections_do_not_leak_threads(
    connection_params: dict[str, Any],
) -> None:
    """Five connections used and discarded leave no worker threads behind.

    Each open websocket runs a ``recv_events`` thread and a ``keepalive``
    thread; before ``__del__`` closed the socket, five discarded connections
    left ten of them running for the rest of the process.
    """
    gc.collect()
    before = _worker_threads()

    for _ in range(5):
        connection = _signed_in(connection_params)
        assert connection.query("RETURN 1").first() == 1
        del connection

    gc.collect()

    # The threads exit once the socket closes, which is not instantaneous.
    deadline = time.monotonic() + 10
    leaked = _worker_threads() - before
    while leaked and time.monotonic() < deadline:
        time.sleep(0.1)
        leaked = _worker_threads() - before

    assert not leaked, (
        f"{len(leaked)} websocket worker thread(s) outlived the connections"
    )


def test_a_connection_left_open_does_not_block_interpreter_exit(
    connection_params: dict[str, Any],
) -> None:
    """A process holding a live connection at exit still terminates.

    Releasing the socket in ``__del__`` must not use the graceful close: that
    performs a closing handshake and then joins the reader thread, and at
    interpreter shutdown the reader has already been stopped without releasing
    its lock, so the join never returns. A plain script that connects, queries,
    and ends - the most ordinary shape there is - hung forever instead of
    exiting, while the whole test suite passed.
    """
    script = textwrap.dedent(f"""
        from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

        connection = BlockingWsSurrealConnection({connection_params["ws_url"]!r})
        connection.signin({connection_params["vars_params"]!r})
        connection.use({connection_params["namespace"]!r}, {connection_params["database_name"]!r})
        print(connection.query("RETURN 8").first(), flush=True)
        # Deliberately no close(): the connection is still bound at exit.
    """)

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "8"
