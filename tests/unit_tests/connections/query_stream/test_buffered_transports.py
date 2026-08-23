"""``query_stream`` on the transports that cannot stream.

HTTP carries one response per request, so these transports answer the buffered
way and hand the rows back one at a time. The point of the parity is that
calling code can change transport without changing shape; the point of these
tests is that the parity is real and that ``require_streaming=True`` still tells
the truth about what happened.
"""

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.errors import UnsupportedFeatureError

MIXED_SQL = (
    "SELECT * FROM stream_http ORDER BY id LIMIT 2; RETURN 42; RETURN [1, 2, 3];"
)

SEED = (
    "DEFINE TABLE IF NOT EXISTS stream_http; DELETE stream_http; "
    "CREATE |stream_http:5| SET n = 1 RETURN NONE"
)


async def test_async_http_streams_by_buffering(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query(SEED)

    buffered = await async_http_connection.query(MIXED_SQL)
    statements = [
        statement
        async for statement in async_http_connection.query_stream(
            MIXED_SQL
        ).statements()
    ]
    assert [statement.value for statement in statements] == buffered
    assert [statement.single for statement in statements] == [False, True, False]

    expected: list[object] = []
    for result in buffered:
        expected.extend(result if isinstance(result, list) else [result])
    assert [row async for row in async_http_connection.query_stream(MIXED_SQL)] == (
        expected
    )


async def test_async_http_says_so_when_streaming_is_required(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="HTTP transport cannot stream"):
        async for _ in async_http_connection.query_stream(
            "RETURN 1", require_streaming=True
        ):
            pass


def test_blocking_http_streams_by_buffering(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    blocking_http_connection.query(SEED).execute()

    buffered = blocking_http_connection.query(MIXED_SQL).execute()
    statements = list(blocking_http_connection.query_stream(MIXED_SQL).statements())
    assert [statement.value for statement in statements] == buffered


def test_blocking_http_says_so_when_streaming_is_required(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="HTTP transport cannot stream"):
        list(blocking_http_connection.query_stream("RETURN 1", require_streaming=True))
