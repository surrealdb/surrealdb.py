"""One bad request must not take unrelated ones down with it.

A protocol-level error arrives with no ``id``: the server could not parse the
frame far enough to read one. Exactly one request is affected - the one whose
frame was rejected, which will never be answered - while every other request in
flight still gets its own reply.

The reader failed *every* pending future, so one malformed request turned into N
failures. Measured before the fix: three ordinary queries plus one malformed one
issued together, and all four came back ``ValidationError: Parse error``; the
same three run alone succeeded.

Nothing on the wire says which request was rejected, so with several in flight
the error is held and reported to whichever request hits its deadline - the
doomed one, since it is the only one that never gets a reply. With a single
request in flight there is no ambiguity and it fails at once.
"""

import asyncio
import uuid
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import SurrealError, TransportTimeoutError

# A record id whose table name is not a string. The server cannot parse the
# frame, so it answers with an error carrying no `id` - the shape this file is
# about. Every non-string table name behaves the same way.
UNPARSEABLE: Any = RecordID(1, "x")  # type: ignore[arg-type]


async def test_a_bad_request_does_not_fail_its_neighbours(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )

    async def good(index: int) -> Any:
        return (await connection.query(f"SLEEP 300ms; RETURN {index}").execute())[-1]

    async def bad() -> Any:
        # Sent after the good ones are already in flight.
        await asyncio.sleep(0.05)
        return await connection.query("RETURN $v", {"v": UNPARSEABLE}).execute()

    results = await asyncio.gather(
        good(1), good(2), good(3), bad(), return_exceptions=True
    )

    healthy, doomed = list(results[:3]), results[3]
    assert healthy == [1, 2, 3], (
        f"unrelated requests were failed by a malformed neighbour: {healthy}"
    )
    # Not merely "some SurrealError": a bare `TransportTimeoutError` is one too,
    # and that is what comes out if the held error is dropped rather than
    # delivered to the request that was actually rejected.
    assert isinstance(doomed, SurrealError)
    assert not isinstance(doomed, TransportTimeoutError), (
        f"the doomed request reported a bare deadline instead of the server's "
        f"explanation: {doomed}"
    )
    assert "timed out" not in str(doomed).lower()

    await connection.close()


async def test_the_only_request_in_flight_fails_immediately(
    connection_params: dict[str, Any],
) -> None:
    """With nothing to confuse it for, the error needs no deadline."""
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )

    with pytest.raises(SurrealError):
        # Two seconds is far below the 30s RPC deadline, so this only passes
        # if the error was delivered straight to the waiting request.
        await asyncio.wait_for(
            connection.query("RETURN $v", {"v": UNPARSEABLE}).execute(), timeout=2.0
        )

    await connection.close()


async def test_the_error_carries_the_servers_message_not_a_bare_timeout(
    connection_params: dict[str, Any],
) -> None:
    """Holding the error must not lose it.

    The doomed request waits for its deadline because nothing identifies it
    sooner, but what it reports has to be the server's explanation rather than
    "no reply within 30s", which says nothing about what was wrong.
    """
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )

    with pytest.raises(SurrealError) as caught:
        await connection.query("RETURN $v", {"v": UNPARSEABLE}).execute()

    assert "timed out" not in str(caught.value).lower()
    assert str(caught.value)

    await connection.close()


async def test_a_held_error_does_not_leak_into_a_later_request(
    connection_params: dict[str, Any],
) -> None:
    """A protocol error belongs to one request, not to the connection."""
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )

    with pytest.raises(SurrealError):
        await connection.query("RETURN $v", {"v": UNPARSEABLE}).execute()

    # The connection is fine, and nothing is left over to poison this.
    assert await connection.query("RETURN 'after'").first() == "after"
    assert connection._uncorrelated_error is None

    await connection.close()


async def test_close_clears_a_held_error(
    connection_params: dict[str, Any],
) -> None:
    """A held error must not survive into the next socket."""
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    connection._uncorrelated_error = SurrealError("stale")

    await connection.close()

    assert connection._uncorrelated_error is None


def test_a_blocking_connection_reopens_after_the_peer_drops_it(
    connection_params: dict[str, Any],
) -> None:
    """``connect()`` must reopen a socket whose peer has gone away.

    The socket object is still there after the peer drops the connection, so
    ``connect()`` saw "already connected" and returned - leaving the connection
    permanently wedged, with every later request failing on the dead socket and
    the documented way to reopen one silently refusing to. The async transport
    already noticed this through its reader task; the blocking one has no
    reader, so the socket's own state is what says so.

    Driven by closing the socket underneath the connection rather than by
    restarting a server: same resulting state, no second server needed, and no
    dependence on restart timing.
    """
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(f"""
        from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

        connection = BlockingWsSurrealConnection({connection_params["ws_url"]!r})
        connection.signin({connection_params["vars_params"]!r})
        connection.use({connection_params["namespace"]!r}, {connection_params["database_name"]!r})
        assert connection.query("RETURN 1").first() == 1

        # The peer goes away underneath us: not `close()`, which the SDK knows
        # about and which clears the reference.
        connection.socket.close_socket()

        connection.connect()
        assert connection.socket is not None
        connection.signin({connection_params["vars_params"]!r})
        connection.use({connection_params["namespace"]!r}, {connection_params["database_name"]!r})
        print(connection.query("RETURN 2").first(), flush=True)
        connection.close()
    """)

    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=90
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2"


def test_a_healthy_blocking_socket_is_not_replaced(
    connection_params: dict[str, Any],
) -> None:
    """The liveness check must not tear down a working connection.

    ``connect()`` on an open connection is a no-op, and it has to stay one:
    reconnecting starts a fresh, anonymous server-side session, so replacing a
    live socket would silently undo a completed ``signin()``.
    """
    from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    try:
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        socket = connection.socket

        connection.connect()

        assert connection.socket is socket, "a live socket was replaced"
        # No signin() in between - the session has to still be there.
        assert connection.query(f"RETURN {uuid.uuid4().int % 100}").first() is not None
    finally:
        connection.close()
