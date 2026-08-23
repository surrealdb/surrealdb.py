"""The embedded engine answers one response per request, so it cannot stream.

Its RPC entry point returns a single response, and the connection classes
inherit the websocket machinery without a socket for it to work on - so
``query_stream`` here runs the query the buffered way and hands its rows back
one at a time. That keeps the call usable on every transport, which is the
point of the parity; these tests are what makes the parity real rather than
asserted, and pin that ``require_streaming=True`` still tells the truth.
"""

import pytest

from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.errors import SurrealError, UnsupportedFeatureError

MIXED_SQL = "SELECT * FROM stream_emb ORDER BY id LIMIT 2; RETURN 42; RETURN [1, 2, 3];"

SEED = (
    "DEFINE TABLE IF NOT EXISTS stream_emb; DELETE stream_emb; "
    "CREATE |stream_emb:4| SET n = 1 RETURN NONE"
)


@pytest.fixture
def blocking_embedded() -> BlockingEmbeddedSurrealConnection:
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.connect()
    connection.use("test_ns", "test_db")
    return connection


@pytest.fixture
async def async_embedded() -> AsyncEmbeddedSurrealConnection:
    connection = AsyncEmbeddedSurrealConnection("memory")
    await connection.connect()
    await connection.use("test_ns", "test_db")
    return connection


async def test_async_embedded_streams_by_buffering(
    async_embedded: AsyncEmbeddedSurrealConnection,
) -> None:
    await async_embedded.query(SEED)

    buffered = await async_embedded.query(MIXED_SQL)
    statements = [
        statement
        async for statement in async_embedded.query_stream(MIXED_SQL).statements()
    ]
    assert [statement.value for statement in statements] == buffered
    assert [statement.single for statement in statements] == [False, True, False]

    expected: list[object] = []
    for result in buffered:
        expected.extend(result if isinstance(result, list) else [result])
    assert [row async for row in async_embedded.query_stream(MIXED_SQL)] == expected


async def test_async_embedded_says_so_when_streaming_is_required(
    async_embedded: AsyncEmbeddedSurrealConnection,
) -> None:
    with pytest.raises(
        UnsupportedFeatureError, match="embedded engine does not stream"
    ):
        async for _ in async_embedded.query_stream("RETURN 1", require_streaming=True):
            pass


async def test_async_embedded_never_reaches_the_websocket_machinery(
    async_embedded: AsyncEmbeddedSurrealConnection,
) -> None:
    """There is no socket here, so a stream must not try to register one.

    The embedded classes inherit ``_stream_open`` and ``_stream_send`` from the
    websocket transport, both of which assume a socket. Reporting no streaming
    support is what keeps them unreachable, and an empty registry is how that
    shows.
    """
    await async_embedded.query(SEED)
    assert [row async for row in async_embedded.query_stream(MIXED_SQL)] != []
    assert async_embedded._streams == {}
    assert async_embedded.socket is None


async def test_async_embedded_statement_errors_still_raise(
    async_embedded: AsyncEmbeddedSurrealConnection,
) -> None:
    await async_embedded.query(SEED)
    seen = []
    with pytest.raises(SurrealError, match="boom"):
        async for row in async_embedded.query_stream(
            "SELECT * FROM stream_emb LIMIT 2; THROW 'boom';"
        ):
            seen.append(row)
    assert len(seen) == 2


def test_blocking_embedded_streams_by_buffering(
    blocking_embedded: BlockingEmbeddedSurrealConnection,
) -> None:
    blocking_embedded.query(SEED).execute()

    buffered = blocking_embedded.query(MIXED_SQL).execute()
    statements = list(blocking_embedded.query_stream(MIXED_SQL).statements())
    assert [statement.value for statement in statements] == buffered
    assert blocking_embedded._streams == {}


def test_blocking_embedded_says_so_when_streaming_is_required(
    blocking_embedded: BlockingEmbeddedSurrealConnection,
) -> None:
    with pytest.raises(
        UnsupportedFeatureError, match="embedded engine does not stream"
    ):
        list(blocking_embedded.query_stream("RETURN 1", require_streaming=True))
