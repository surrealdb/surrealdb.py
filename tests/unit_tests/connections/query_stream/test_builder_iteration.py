"""Iterating a blocking builder, against a real server.

``for row in db.select(...)`` is a terminator that streams, and leaving the
loop early has to give the stream back. The unit tests pin that against fake
sockets; what only a live server can show is the part that matters to a caller:
the query really stops, the connection's stream slots really come back, and the
connection carries on working.

Nothing here closes the stream by hand. A bare ``for ... break`` leaves the
iterator to be finalised, so these tests are what shows that finalising it is
enough - the stream-closing ``with`` inside ``__iter__`` is pinned separately,
by a unit test that can see it directly.
"""

import time
from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.table import Table
from surrealdb.errors import UnsupportedFeatureError
from tests.unit_tests.connections.query_stream.expectation import (
    skip_unless_streaming_is_expected,
)

ROWS = 120


def _seed(connection: Any) -> None:
    connection.query(
        "DEFINE TABLE OVERWRITE iter_wide; DELETE iter_wide; "
        f"CREATE |iter_wide:{ROWS}| SET n = 1 RETURN NONE"
    ).execute()


def _ids(rows: Any) -> list[str]:
    return sorted(str(row["id"]) for row in rows)


@pytest.mark.parametrize(
    "fixture", ["blocking_ws_connection", "blocking_http_connection"]
)
def test_iterating_a_select_gives_every_row_the_buffered_answer_has(
    fixture: str, request: pytest.FixtureRequest
) -> None:
    connection: BlockingWsSurrealConnection | BlockingHttpSurrealConnection = (
        request.getfixturevalue(fixture)
    )
    _seed(connection)

    iterated = list(connection.select(Table("iter_wide")))

    assert len(iterated) == ROWS
    assert _ids(iterated) == _ids(connection.select(Table("iter_wide")).execute())


def test_leaving_a_select_loop_early_leaves_no_stream_open(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    connection = blocking_ws_connection
    _seed(connection)

    for _ in connection.select(Table("iter_wide")):
        break

    assert connection._streams == {}  # pyright: ignore[reportPrivateUsage]
    assert connection.query("RETURN 'alive'").execute() == ["alive"]


def test_many_early_exits_do_not_leak_stream_slots(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """A leak would show as a refusal at the server's concurrency cap."""
    connection = blocking_ws_connection
    _seed(connection)

    for _ in range(100):
        for _row in connection.select(Table("iter_wide")):
            break

    assert connection._streams == {}  # pyright: ignore[reportPrivateUsage]
    assert len(list(connection.select(Table("iter_wide")))) == ROWS


def test_leaving_a_query_loop_early_cancels_it_on_the_server(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The trailing SLEEP is what a cancel that never arrives would cost."""
    connection = blocking_ws_connection
    _seed(connection)
    try:
        for _ in connection.query("RETURN 1").rows(require_streaming=True):
            pass
    except UnsupportedFeatureError as exc:
        if connection._streaming_supported is not False:  # pyright: ignore[reportPrivateUsage]
            raise
        skip_unless_streaming_is_expected(exc)

    started = time.monotonic()
    seen = 0
    for _ in connection.query("SELECT * FROM iter_wide; SLEEP 10s;"):
        seen += 1
        if seen == 3:
            break
    elapsed = time.monotonic() - started

    assert seen == 3
    assert elapsed < 2.5, f"leaving the loop took {elapsed:.1f}s"
    assert connection._streams == {}  # pyright: ignore[reportPrivateUsage]
    assert connection.query("RETURN 'alive'").execute() == ["alive"]
