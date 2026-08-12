"""A ``RecordID`` whose id is a ``Range`` targets every record in the range.

``RecordID("person", Range(BoundIncluded(1), BoundIncluded(3)))`` is how the SDK
spells ``person:1..=3``. Every supported server returns all three records for
it, but the SDK classified any ``RecordID`` as a single-record target and
unwrapped the answer to the first row - so three records were read, one was
returned, and nothing said the other two had been dropped. ``delete()`` was the
same shape: it reported deleting one record while deleting all of them.

The equivalent ``"person:1..=3"`` *string* was always treated as multi-record,
so the two spellings of one target disagreed about how much of the answer the
caller saw. These tests assert on the string form alongside the ``RecordID``
form, because agreeing with each other is the property that matters.

A bare ``Range`` is a separate case: it names no table, so it cannot be a
resource target at all. It used to reach a ``":" in resource`` test and come
back as ``TypeError: argument of type 'Range' is not iterable`` - and the
catch-all error next to that test told callers to "pass a RecordID, Table, or
Range instance", which is how they got there.
"""

import uuid
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.range import BoundExcluded, BoundIncluded, Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.errors import SurrealError


def _rows(connection: BlockingWsSurrealConnection) -> str:
    table = f"rng_{uuid.uuid4().hex[:8]}"
    connection.query(
        f"CREATE {table}:1 SET n=1; CREATE {table}:2 SET n=2; CREATE {table}:3 SET n=3;"
    ).execute()
    return table


def _ids(result: object) -> list[object]:
    assert isinstance(result, list), f"expected every matching record, got {result!r}"
    return sorted(row["id"].id for row in result)


# --------------------------------------------------------------- select


def test_select_returns_every_record_in_the_range(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)

    result = blocking_ws_connection.select(
        RecordID(table, Range(BoundIncluded(1), BoundIncluded(3)))
    )

    assert _ids(result) == [1, 2, 3]


def test_the_record_id_and_string_spellings_agree(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)

    typed = blocking_ws_connection.select(
        RecordID(table, Range(BoundIncluded(1), BoundIncluded(3)))
    )
    spelled = blocking_ws_connection.select(f"{table}:1..=3")

    assert typed == spelled


def test_an_excluded_end_bound_is_honoured(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)

    result = blocking_ws_connection.select(
        RecordID(table, Range(BoundIncluded(1), BoundExcluded(3)))
    )

    assert _ids(result) == [1, 2]


def test_an_open_range_covers_the_whole_table(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)

    result = blocking_ws_connection.select(RecordID(table, Range(None, None)))

    assert _ids(result) == [1, 2, 3]


def test_a_range_that_matches_nothing_is_an_empty_list(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Not ``None``: an empty range is an empty multi-record answer, the same
    as a ``Table`` target with no rows. ``None`` is what an absent *single*
    record returns, and conflating the two is what the unwrap did.

    Held as ``Any`` because the ``@overload``s resolve on the static type
    ``RecordID``, which says nothing about the id - the documented caveat that
    a range target is narrower on paper than it is at runtime.
    """
    table = _rows(blocking_ws_connection)

    result: Any = blocking_ws_connection.select(
        RecordID(table, Range(BoundIncluded(90), BoundIncluded(99)))
    )

    assert result == []


def test_a_plain_record_id_still_unwraps(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The neighbouring behaviour this must not disturb."""
    table = _rows(blocking_ws_connection)

    row = blocking_ws_connection.select(RecordID(table, 1))

    assert isinstance(row, dict)
    assert row["n"] == 1
    assert blocking_ws_connection.select(RecordID(table, 404)) is None


# --------------------------------------------------------------- write paths


def test_delete_returns_every_record_it_removed(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)

    removed = blocking_ws_connection.delete(
        RecordID(table, Range(BoundIncluded(1), BoundIncluded(3)))
    )

    assert _ids(removed) == [1, 2, 3]
    assert blocking_ws_connection.select(Table(table)) == []


def test_update_returns_every_record_it_wrote(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)

    written = blocking_ws_connection.update(
        RecordID(table, Range(BoundIncluded(1), BoundIncluded(3))), {"n": 9}
    )

    assert _ids(written) == [1, 2, 3]
    assert [row["n"] for row in blocking_ws_connection.select(Table(table))] == [
        9,
        9,
        9,
    ]


def test_into_maps_every_record_in_the_range(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """``into=`` follows the runtime shape, so a range maps element-wise."""
    from dataclasses import dataclass

    @dataclass
    class Row:
        id: RecordID
        n: int

    table = _rows(blocking_ws_connection)

    rows = blocking_ws_connection.select(
        RecordID(table, Range(BoundIncluded(1), BoundIncluded(3))), into=Row
    )

    assert isinstance(rows, list)
    assert sorted(row.n for row in rows) == [1, 2, 3]


# --------------------------------------------------------------- other transports


def test_the_http_transport_agrees(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    table = f"rng_{uuid.uuid4().hex[:8]}"
    blocking_http_connection.query(
        f"CREATE {table}:1 SET n=1; CREATE {table}:2 SET n=2;"
    ).execute()

    result = blocking_http_connection.select(
        RecordID(table, Range(BoundIncluded(1), BoundIncluded(2)))
    )

    assert _ids(result) == [1, 2]


async def test_the_async_transport_agrees(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    table = f"rng_{uuid.uuid4().hex[:8]}"
    await async_ws_connection.query(
        f"CREATE {table}:1 SET n=1; CREATE {table}:2 SET n=2;"
    ).execute()

    result = await async_ws_connection.select(
        RecordID(table, Range(BoundIncluded(1), BoundIncluded(2)))
    )

    assert _ids(result) == [1, 2]


# --------------------------------------------------------------- a bare Range


@pytest.mark.parametrize(
    "operation",
    ["select", "delete"],
)
def test_a_bare_range_is_refused_with_an_explanation(
    blocking_ws_connection: BlockingWsSurrealConnection, operation: str
) -> None:
    with pytest.raises(SurrealError) as caught:
        getattr(blocking_ws_connection, operation)(
            Range(BoundIncluded(1), BoundIncluded(3))
        )

    message = str(caught.value)
    assert "names no table" in message
    assert "RecordID(table, range)" in message
    # The old failure, and the shape of it: an unhandled builtin from a
    # containment test, naming nothing the caller passed.
    assert not isinstance(caught.value, TypeError)


def test_the_string_advice_no_longer_recommends_a_bare_range(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The message that sent callers into the failure above."""
    with pytest.raises(SurrealError) as caught:
        blocking_ws_connection.select("not a valid target!")

    assert "Range instance" not in str(caught.value)
