"""The server's streaming support is what CI expects it to be, and falls back.

``SURREALDB_EXPECT_STREAMING`` is set by CI from the server version under test -
``1`` for v3.3.0 and later, ``0`` for everything before it - and these tests
hold the SDK to it from both sides:

* where the server must stream, asking for streaming outright works and the
  connection learns that it can;
* where it must not, asking outright is refused with
  :class:`~surrealdb.errors.UnsupportedFeatureError`, the connection learns
  that once, and everything a caller does *without* asking outright - ``query()``,
  ``.rows()``, a streamed ``select()`` - still returns the right answer by the
  buffered route.

The fallback tests run on every server, including the ones that do stream, so
they stay honest about the answer being the same either way.
"""

from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.table import Table
from surrealdb.errors import UnsupportedFeatureError
from tests.unit_tests.connections.query_stream.expectation import (
    ENV,
    streaming_expected,
)

pytestmark = pytest.mark.skipif(
    streaming_expected() is None,
    reason=f"{ENV} is not set; CI sets it from the SurrealDB version under test",
)

SEED = (
    "DEFINE TABLE OVERWRITE gate_rows; DELETE gate_rows; "
    "CREATE |gate_rows:5| SET n = 1 RETURN NONE"
)


def _ids(rows: Any) -> list[str]:
    return sorted(str(row["id"]) for row in rows)


# ------------------------------------------------------------------- blocking


def test_blocking_ws_streams_exactly_where_it_is_expected_to(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    connection = blocking_ws_connection

    if streaming_expected():
        assert list(connection.query("RETURN 1").rows(require_streaming=True)) == [1]
        assert connection._streaming_supported is True  # pyright: ignore[reportPrivateUsage]
        return

    with pytest.raises(UnsupportedFeatureError):
        for _ in connection.query("RETURN 1").rows(require_streaming=True):
            pass
    assert connection._streaming_supported is False  # pyright: ignore[reportPrivateUsage]


def test_blocking_ws_falls_back_to_the_same_answer(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    connection = blocking_ws_connection
    connection.query(SEED).execute()
    sql = "SELECT * FROM gate_rows"

    buffered: Any = connection.query(sql).execute()[0]
    assert len(buffered) == 5
    assert _ids(list(connection.query(sql).rows())) == _ids(buffered)
    assert _ids(list(connection.select(Table("gate_rows")).rows())) == _ids(buffered)
    assert _ids(connection.select(Table("gate_rows")).execute()) == _ids(buffered)
    assert connection.query("RETURN 1 + 1").execute() == [2]


def test_blocking_ws_does_not_ask_again_once_refused(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    if streaming_expected():
        pytest.skip("only a server that refuses has anything to remember")
    connection = blocking_ws_connection
    with pytest.raises(UnsupportedFeatureError):
        for _ in connection.query("RETURN 1").rows(require_streaming=True):
            pass

    connection.query("RETURN 1").execute()
    list(connection.query("RETURN 1").rows())

    assert connection._streaming_supported is False  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------- async


async def test_async_ws_streams_exactly_where_it_is_expected_to(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    connection = async_ws_connection

    if streaming_expected():
        rows = [
            r async for r in connection.query("RETURN 1").rows(require_streaming=True)
        ]
        assert rows == [1]
        assert connection._streaming_supported is True  # pyright: ignore[reportPrivateUsage]
        return

    with pytest.raises(UnsupportedFeatureError):
        async for _ in connection.query("RETURN 1").rows(require_streaming=True):
            pass
    assert connection._streaming_supported is False  # pyright: ignore[reportPrivateUsage]


async def test_async_ws_falls_back_to_the_same_answer(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    connection = async_ws_connection
    await connection.query(SEED)
    sql = "SELECT * FROM gate_rows"

    buffered: Any = (await connection.query(sql))[0]
    assert len(buffered) == 5
    assert _ids([r async for r in connection.query(sql).rows()]) == _ids(buffered)
    selected = [r async for r in connection.select(Table("gate_rows")).rows()]
    assert _ids(selected) == _ids(buffered)
    assert _ids(await connection.select(Table("gate_rows"))) == _ids(buffered)
    assert await connection.query("RETURN 1 + 1") == [2]
