"""Reading a record and writing it back does not delete its NULL fields.

SurrealDB has two ways for a field to hold nothing. NONE means the field is not
there - an unset ``option<T>`` column is NONE, and a NONE field does not appear
in a record at all. NULL means the field is there and its value is null.

Python has one ``None``, and the SDK used it for both: a NULL field decoded to
``None``, and ``None`` encoded to NONE. That made the most ordinary operation
there is destructive:

    row = db.select(rec)      # {"nickname": None}   <- NULL in the table
    row["name"] = "new name"
    db.update(rec, row)       # nickname is now GONE, not NULL

No error, no warning, and the field is not merely null afterwards - it is
absent. A read-modify-write loop over a table with nullable columns stripped
them one record at a time.

``Null`` is now a distinct value: a NULL field decodes to ``Null``, and ``Null``
encodes back to NULL, so the round trip is lossless. ``None`` still means NONE,
which is what keeps ``option<T>`` columns working - they accept NONE and
*reject* NULL, so mapping ``None`` to NULL instead would have broken every
schema that uses one.
"""

from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.null import Null
from surrealdb.data.types.record_id import RecordID

TABLE = "null_round_trip"
OPTION_TABLE = "null_round_trip_opt"


def _record(name: str) -> RecordID:
    return RecordID(TABLE, name)


@pytest.fixture(autouse=True)
def _empty_tables(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    """Start every test from empty tables.

    These tests ``create()`` fixed record ids, which is an error if the record
    survives from an earlier run - and the whole suite shares one namespace.
    Without this the file passes once and then fails with ``AlreadyExistsError``
    on every run after, which looks exactly like the defect coming back.

    ``REMOVE ... IF EXISTS`` rather than ``DELETE``: the schema defined below
    has to go too, and ``DELETE`` on a table that does not exist yet raises.
    """
    blocking_ws_connection.query(
        f"REMOVE TABLE IF EXISTS {TABLE}; REMOVE TABLE IF EXISTS {OPTION_TABLE};"
    ).execute()


# ------------------------------------------------- the read-modify-write path


def test_blocking_ws_read_modify_write_keeps_a_null_field(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    record = _record("bws")
    blocking_ws_connection.query(
        f"CREATE {TABLE}:bws SET name = 'ada', nickname = NULL;"
    ).execute()

    row = blocking_ws_connection.select(record)
    assert row["nickname"] is Null, "a NULL field must decode to Null, not None"

    row["name"] = "ada l."
    blocking_ws_connection.update(record, row)

    after = blocking_ws_connection.select(record)
    assert "nickname" in after, "the NULL field was deleted by writing the record back"
    assert after["nickname"] is Null
    assert (
        blocking_ws_connection.query(f"RETURN {TABLE}:bws.nickname IS NULL;").first()
        is True
    )


def test_blocking_http_read_modify_write_keeps_a_null_field(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    record = _record("bhttp")
    blocking_http_connection.query(
        f"CREATE {TABLE}:bhttp SET name = 'ada', nickname = NULL;"
    ).execute()

    row = blocking_http_connection.select(record)
    row["name"] = "ada l."
    blocking_http_connection.update(record, row)

    after = blocking_http_connection.select(record)
    assert "nickname" in after
    assert after["nickname"] is Null


async def test_async_ws_read_modify_write_keeps_a_null_field(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    record = _record("aws")
    await async_ws_connection.query(
        f"CREATE {TABLE}:aws SET name = 'ada', nickname = NULL;"
    ).execute()

    row = await async_ws_connection.select(record)
    row["name"] = "ada l."
    await async_ws_connection.update(record, row)

    after = await async_ws_connection.select(record)
    assert "nickname" in after
    assert after["nickname"] is Null


async def test_async_http_read_modify_write_keeps_a_null_field(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    record = _record("ahttp")
    await async_http_connection.query(
        f"CREATE {TABLE}:ahttp SET name = 'ada', nickname = NULL;"
    ).execute()

    row = await async_http_connection.select(record)
    row["name"] = "ada l."
    await async_http_connection.update(record, row)

    after = await async_http_connection.select(record)
    assert "nickname" in after
    assert after["nickname"] is Null


# ------------------------------------------------- writing each value directly


def test_writing_null_stores_null(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    created = blocking_ws_connection.create(
        _record("explicit_null"), {"name": "bob", "nickname": Null}
    )

    assert created["nickname"] is Null
    assert (
        blocking_ws_connection.query(
            f"RETURN {TABLE}:explicit_null.nickname IS NULL;"
        ).first()
        is True
    )


def test_writing_none_stores_none(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """``None`` still means NONE, so the field is not set to anything.

    Asserted against the server rather than against the returned record:
    SurrealDB 2.x echoes a NONE key back in the record it returns while 3.x
    omits it, and that difference says nothing about what was stored. What
    matters is that the value is NONE and specifically *not* NULL.
    """
    blocking_ws_connection.create(
        _record("explicit_none"), {"name": "bob", "nickname": None}
    )

    assert (
        blocking_ws_connection.query(
            f"RETURN {TABLE}:explicit_none.nickname IS NONE;"
        ).first()
        is True
    )
    assert (
        blocking_ws_connection.query(
            f"RETURN {TABLE}:explicit_none.nickname IS NULL;"
        ).first()
        is False
    )


def test_none_is_still_accepted_by_an_option_field(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The case that rules out simply making ``None`` mean NULL.

    ``option<T>`` is how a SurrealDB schema spells a nullable column, and it
    accepts NONE but *rejects* NULL. If ``None`` were encoded as NULL, every
    ``create(rec, {"age": None})` against such a schema would start failing
    with a coercion error.
    """
    blocking_ws_connection.query(
        f"DEFINE TABLE {OPTION_TABLE} SCHEMAFULL; "
        f"DEFINE FIELD age ON {OPTION_TABLE} TYPE option<int>;"
    ).execute()

    # No exception is the assertion: NULL here is a coercion error.
    created = blocking_ws_connection.create(OPTION_TABLE, {"age": None})

    assert created["id"] is not None
    assert created.get("age") is None, "an option<int> set to NONE is not a value"


def test_null_is_rejected_by_an_option_field(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The other half: the two values are genuinely different to the server."""
    blocking_ws_connection.query(
        f"DEFINE TABLE {OPTION_TABLE} SCHEMAFULL; "
        f"DEFINE FIELD age ON {OPTION_TABLE} TYPE option<int>;"
    ).execute()

    with pytest.raises(Exception, match="(?i)coerce|expected"):
        blocking_ws_connection.create(OPTION_TABLE, {"age": Null})


def test_null_survives_nested_in_containers(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Not just top-level fields: inside a list or an object too."""
    payload: dict[str, Any] = {
        "items": [1, Null, 3],
        "nested": {"inner": Null},
    }
    created = blocking_ws_connection.create(_record("nested"), payload)

    assert created["items"] == [1, Null, 3]
    assert created["nested"] == {"inner": Null}


@pytest.mark.parametrize(
    ("label", "value"),
    [
        pytest.param("null", Null, id="null"),
        pytest.param("zero", 0, id="zero"),
        pytest.param("false", False, id="false"),
        pytest.param("empty_string", "", id="empty-string"),
        pytest.param("empty_list", [], id="empty-list"),
        pytest.param("empty_object", {}, id="empty-object"),
    ],
)
def test_falsy_values_are_all_preserved(
    blocking_ws_connection: BlockingWsSurrealConnection, label: str, value: Any
) -> None:
    """``Null`` is not the only value that could be mistaken for "absent"."""
    created = blocking_ws_connection.create(_record(f"falsy_{label}"), {"v": value})

    assert "v" in created, f"{value!r} was dropped from the record"
    assert created["v"] == value
