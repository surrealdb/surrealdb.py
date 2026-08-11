"""Opening one connection from several callers at once opens one socket.

Neither ``connect()`` was serialised, so every caller that arrived before the
first one finished saw ``socket is None`` and opened its own. The object kept
whichever finished last; the rest were leaked with no reference left to close
them, each holding a TCP socket and - on the blocking transport - two
``websockets`` worker threads.

Async was worse than a leak. Each surplus socket also started a ``_recv_task``,
and all of them iterate the same ``self.qry``; the first one to notice its own
socket closing failed every pending future, so callers on the *surviving*
socket were handed ``ConnectionUnavailableError`` for a connection that was
working. Measured before the fix: eight concurrent ``signin()`` calls opened
eight sockets and all eight callers failed.

This is the shape of ordinary code - a thread pool, or an ``asyncio.gather``
over a shared connection - not of a stress test.
"""

import asyncio
import threading
from typing import Any

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

CALLERS = 8


def test_blocking_connect_opens_one_socket_for_concurrent_callers(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    opened: list[Any] = []
    lock = threading.Lock()
    open_socket = connection._connect_socket

    def counting_connect() -> Any:
        socket = open_socket()
        with lock:
            opened.append(socket)
        return socket

    connection._connect_socket = counting_connect  # type: ignore[method-assign]

    # A barrier rather than bare thread starts: without it the first thread
    # usually finishes connecting before the others begin, and the race the
    # lock exists for never happens.
    ready = threading.Barrier(CALLERS)

    def worker() -> None:
        ready.wait()
        connection.connect()

    threads = [threading.Thread(target=worker) for _ in range(CALLERS)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            assert not thread.is_alive(), "a caller never returned from connect()"

        assert len(opened) == 1, (
            f"{CALLERS} concurrent callers opened {len(opened)} sockets; "
            f"{len(opened) - 1} of them are leaked"
        )
        assert connection.socket is opened[0]
        # The one surviving socket is a working connection, not a wedged one.
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        assert connection.query("RETURN 1").first() == 1
    finally:
        connection.close()
        for socket in opened:
            try:
                socket.close_socket()
            except Exception:
                pass


async def test_async_connect_opens_one_socket_for_concurrent_callers(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    opened: list[Any] = []

    # `connect()` calls `websockets.connect` directly, so the count is taken
    # there rather than through a seam on the connection.
    import surrealdb.connections.async_ws as module

    real_connect = module.websockets.connect

    def counting_connect(*args: Any, **kwargs: Any) -> Any:
        awaitable = real_connect(*args, **kwargs)

        async def record() -> Any:
            socket = await awaitable
            opened.append(socket)
            return socket

        return record()

    module.websockets.connect = counting_connect  # type: ignore[misc,assignment]
    try:
        results = await asyncio.gather(
            *[
                connection.signin(connection_params["vars_params"])
                for _ in range(CALLERS)
            ],
            return_exceptions=True,
        )
    finally:
        module.websockets.connect = real_connect  # type: ignore[misc]

    failures = [r for r in results if isinstance(r, BaseException)]
    try:
        assert not failures, (
            f"{len(failures)} of {CALLERS} concurrent callers failed on a "
            f"healthy connection; first was {failures[0]!r}"
        )
        assert len(opened) == 1, (
            f"{CALLERS} concurrent callers opened {len(opened)} sockets; "
            f"{len(opened) - 1} of them are leaked"
        )
        await connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        assert await connection.query("RETURN 1").first() == 1
    finally:
        await connection.close()


async def test_async_connect_survives_a_loop_it_was_not_built_in(
    connection_params: dict[str, Any],
) -> None:
    """The connect lock is per-loop, so a reused connection must not trip on it.

    An ``asyncio.Lock`` binds to the loop it first *waits* on, and stays bound:
    awaiting it from a second loop raises ``RuntimeError``. Keeping one lock
    for the lifetime of the connection would therefore break a connection
    reused across two ``asyncio.run`` calls, each of which builds and discards
    its own loop.

    Both rounds contend the lock on purpose. An uncontended ``acquire()``
    returns without ever looking at the loop, so a single caller per round
    would pass no matter how the lock was built.
    """
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])

    def one_round() -> Any:
        async def run() -> Any:
            await asyncio.gather(
                *[
                    connection.signin(connection_params["vars_params"])
                    for _ in range(CALLERS)
                ]
            )
            await connection.use(
                namespace=connection_params["namespace"],
                database=connection_params["database_name"],
            )
            outcome = await connection.query("RETURN 1").first()
            await connection.close()
            return outcome

        return asyncio.run(run())

    # `asyncio.run` cannot be called from inside a running loop, so both rounds
    # go to a worker thread that has none.
    results: list[Any] = []

    def worker() -> None:
        results.append(one_round())
        results.append(one_round())

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=60)

    assert not thread.is_alive()
    assert results == [1, 1]
