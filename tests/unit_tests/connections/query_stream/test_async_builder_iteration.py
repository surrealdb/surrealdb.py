"""``async for row in builder`` against a real server.

The unit tests pin the iteration against fake sockets. What only a live server
can show is what matters to a caller: the rows are the buffered answer's rows,
leaving a loop early really gives the connection's stream slots back, and - on a
server that streams - the query really stops instead of running on.

Nothing here closes a stream by hand. A bare ``async for ... break`` leaves the
iterator to be finalised on the event loop's later passes, so these tests are
what shows that is enough.
"""

import asyncio
import gc
import time
from typing import Any

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.table import Table
from surrealdb.errors import UnsupportedFeatureError
from tests.unit_tests.connections.query_stream.expectation import (
    skip_unless_streaming_is_expected,
)

ROWS = 120


async def _seed(connection: Any) -> None:
    await connection.query(
        "DEFINE TABLE OVERWRITE aiter_wide; DELETE aiter_wide; "
        f"CREATE |aiter_wide:{ROWS}| SET n = 1 RETURN NONE"
    )


def _ids(rows: Any) -> list[str]:
    return sorted(str(row["id"]) for row in rows)


async def _settle(connection: AsyncWsSurrealConnection) -> None:
    """Async cleanup runs on the loop's later passes; give it them."""
    for _ in range(50):
        gc.collect()
        await asyncio.sleep(0.02)
        if connection._streams == {}:  # pyright: ignore[reportPrivateUsage]
            return


async def _iterating_a_select_matches_the_buffered_answer(
    connection: AsyncWsSurrealConnection | AsyncHttpSurrealConnection,
) -> None:
    await _seed(connection)

    iterated = [row async for row in connection.select(Table("aiter_wide"))]

    assert len(iterated) == ROWS
    assert _ids(iterated) == _ids(await connection.select(Table("aiter_wide")))


async def test_iterating_a_select_over_the_websocket_gives_the_buffered_rows(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await _iterating_a_select_matches_the_buffered_answer(async_ws_connection)


async def test_iterating_a_select_over_http_gives_the_buffered_rows(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await _iterating_a_select_matches_the_buffered_answer(async_http_connection)


async def test_leaving_a_select_loop_early_leaves_no_stream_open(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """Twenty-five exits, so a leak would reach a cap rather than hide."""
    connection = async_ws_connection
    await _seed(connection)

    for _ in range(25):
        async for _row in connection.select(Table("aiter_wide")):
            break
    await _settle(connection)

    assert connection._streams == {}  # pyright: ignore[reportPrivateUsage]
    assert await connection.query("RETURN 'alive'") == ["alive"]


async def test_leaving_a_query_loop_early_cancels_it_on_the_server(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """The trailing SLEEP is what a cancel that never arrives would cost."""
    connection = async_ws_connection
    await _seed(connection)
    try:
        async for _ in connection.query("RETURN 1").rows(require_streaming=True):
            pass
    except UnsupportedFeatureError as exc:
        if connection._streaming_supported is not False:  # pyright: ignore[reportPrivateUsage]
            raise
        skip_unless_streaming_is_expected(exc)

    started = time.monotonic()
    seen = 0
    async for _ in connection.query("SELECT * FROM aiter_wide; SLEEP 10s;"):
        seen += 1
        if seen == 3:
            break
    await _settle(connection)
    elapsed = time.monotonic() - started

    assert seen == 3
    assert elapsed < 2.5, f"leaving the loop took {elapsed:.1f}s"
    assert connection._streams == {}  # pyright: ignore[reportPrivateUsage]
    assert await connection.query("RETURN 'alive'") == ["alive"]
