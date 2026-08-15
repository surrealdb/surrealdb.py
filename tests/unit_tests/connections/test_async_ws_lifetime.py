"""An async websocket connection is bound to one loop, and releases what it holds.

Two failures of the same object's lifetime.

**Bound to a loop.** Every awaiting caller's future is created on the loop the
socket was opened on, and the reader that resolves them runs there. Used from a
second loop - two ``asyncio.run`` calls is enough, since each builds and
destroys one - the first ``await`` failed deep inside asyncio with
``ValueError: The future belongs to a different loop than the one specified as
the loop argument``, a message with nothing in it about connections or event
loops. The request then stayed in ``qry`` and every later call failed the same
way, so the connection was wedged as well as unexplained.

**Releases what it holds.** ``asyncio.create_task(self._recv_task())`` gave the
running loop a strong reference to the connection: loop -> task -> coroutine ->
``self``. A connection whose last user reference was dropped was therefore never
collected, so no finaliser could run and its socket, file descriptor, reader
task and keepalive task stayed for the life of the process. The reader now holds
a weak reference, so dropping a connection collects it and ``__del__`` releases
the socket.
"""

import asyncio
import gc
import os
import warnings
from typing import Any

import pytest
from websockets.protocol import State

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.errors import ConnectionUnavailableError


def _open_fds() -> int:
    return len(os.listdir("/dev/fd"))


async def _signed_in(params: dict[str, Any]) -> AsyncWsSurrealConnection:
    connection = AsyncWsSurrealConnection(params["ws_url"])
    await connection.signin(params["vars_params"])
    await connection.use(params["namespace"], params["database_name"])
    await connection.query("RETURN 1").first()
    return connection


# ------------------------------------------------------------- loop binding


def test_using_a_connection_from_a_second_loop_is_refused(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])

    first = asyncio.new_event_loop()
    second = asyncio.new_event_loop()
    try:
        assert first.run_until_complete(_run_first(connection, connection_params)) == 1

        with pytest.raises(ConnectionUnavailableError) as caught:
            second.run_until_complete(connection.query("RETURN 2").first())

        message = str(caught.value)
        assert "event loop" in message
        assert "build a new one" in message
    finally:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            for loop in (first, second):
                loop.close()
            del connection
            gc.collect()


async def _run_first(
    connection: AsyncWsSurrealConnection, params: dict[str, Any]
) -> Any:
    await connection.signin(params["vars_params"])
    await connection.use(params["namespace"], params["database_name"])
    return await connection.query("RETURN 1").first()


def test_close_works_from_a_different_loop(
    connection_params: dict[str, Any],
) -> None:
    """Otherwise the advice the error gives - build a new connection - leaves
    the old one with no way to release its socket.

    The descriptor is what this asserts on, not the two attributes. Checking
    only that ``socket`` and ``recv_task`` are ``None`` is satisfied by an
    implementation that forgets the socket without closing it, which is the
    failure this branch exists to prevent: gutting the branch body down to
    ``self.socket = None`` left all nine tests in this file green while the
    connection leaked its descriptor.

    ``state`` is no use here - it is the websocket protocol's own state, and a
    socket closed underneath the protocol still reports ``OPEN``. ``fileno()``
    returning ``-1`` is what says the descriptor is gone.
    """
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    first = asyncio.new_event_loop()
    try:
        first.run_until_complete(_run_first(connection, connection_params))
    finally:
        first.close()

    raw = connection.socket.transport._sock  # pyright: ignore[reportPrivateUsage]
    assert raw.fileno() != -1, "precondition: the descriptor is open to begin with"

    asyncio.run(connection.close())

    assert connection.socket is None
    assert connection.recv_task is None
    assert raw.fileno() == -1, "close() forgot the socket instead of releasing it"


async def test_one_loop_is_unaffected(connection_params: dict[str, Any]) -> None:
    """The ordinary case: many operations, one loop, no complaint."""
    connection = await _signed_in(connection_params)
    try:
        for _ in range(3):
            assert await connection.query("RETURN 1").first() == 1
    finally:
        await connection.close()


# ------------------------------------------------------------- release on drop


async def test_a_dropped_connection_is_collected(
    connection_params: dict[str, Any],
) -> None:
    """The precondition for any finaliser to run at all."""
    import weakref

    connection = await _signed_in(connection_params)
    ref = weakref.ref(connection)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        del connection
        gc.collect()

    assert ref() is None, "the reader task is still holding the connection alive"


async def test_dropping_a_connection_releases_its_tasks_and_socket(
    connection_params: dict[str, Any],
) -> None:
    before = set(asyncio.all_tasks())
    connection = await _signed_in(connection_params)
    socket = connection.socket

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        del connection
        gc.collect()
        await asyncio.sleep(0.3)
        gc.collect()

    leaked = [t for t in asyncio.all_tasks() if t not in before and not t.done()]
    assert leaked == [], f"leaked tasks: {[t.get_name() for t in leaked]}"
    # The enum member, not its ``str``: ``State`` is an ``IntEnum``, and from
    # Python 3.11 those render as the bare integer.
    assert socket.state is State.CLOSED


async def test_dropping_connections_does_not_accumulate_descriptors(
    connection_params: dict[str, Any],
) -> None:
    """A counter, because the leak only shows as a program stays up.

    Each connection used to keep its file descriptor for the life of the
    process, so a loop that built and discarded them ran out.

    The settle before the baseline is load-bearing, not hygiene. Without it
    this test passed against the *unfixed* reader whenever the file ran in its
    normal order: the tests above leave collectable garbage, the ``gc.collect()``
    calls inside the loop below released those descriptors, and the credit
    cancelled out the eight this loop was leaking - measured delta 7 against a
    bound of 8. Alone, the same test failed at 10. A guard that only holds when
    it runs first is not a guard, and the bound was loose enough to hide half a
    leak on top.
    """
    # Whatever ran before this has to be finished releasing before the
    # measurement starts, or its descriptors are counted as this loop's.
    for _ in range(3):
        gc.collect()
        await asyncio.sleep(0.1)

    connections = 8
    baseline = _open_fds()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        for _ in range(connections):
            connection = await _signed_in(connection_params)
            del connection
            gc.collect()
        await asyncio.sleep(0.3)
        gc.collect()

    leaked = _open_fds() - baseline
    # Held descriptors must not scale with the number of connections. Fixed,
    # this is 0-2 whatever the order; unfixed it is one per connection.
    assert leaked < connections // 2, (
        f"{leaked} descriptors held after {connections} dropped connections"
    )


async def test_dropping_an_open_connection_warns(
    connection_params: dict[str, Any],
) -> None:
    """A ``ResourceWarning``, like an unclosed file: off by default, on in tests."""
    connection = await _signed_in(connection_params)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        del connection
        gc.collect()

    assert any(
        issubclass(entry.category, ResourceWarning)
        and "unclosed connection" in str(entry.message)
        for entry in caught
    ), [str(entry.message) for entry in caught]


async def test_a_closed_connection_does_not_warn(
    connection_params: dict[str, Any],
) -> None:
    """Nothing to complain about once the caller has done the right thing."""
    connection = await _signed_in(connection_params)
    await connection.close()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        del connection
        gc.collect()

    assert not [
        entry for entry in caught if issubclass(entry.category, ResourceWarning)
    ]


async def test_a_never_connected_connection_does_not_warn(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        del connection
        gc.collect()

    assert not [
        entry for entry in caught if issubclass(entry.category, ResourceWarning)
    ]
