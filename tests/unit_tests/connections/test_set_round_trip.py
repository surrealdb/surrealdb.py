"""A record with a set field survives being read and written back.

SurrealDB's ``set<T>`` is a deduplicated sequence that holds any value. Neither
builtin models it, and each wrong choice broke something different:

* decoding into a Python ``set`` raised ``unhashable type: 'dict'`` on a
  ``set<object>`` column, which killed the whole response - the record could not
  be read at all;
* decoding into a plain ``list`` made it readable but lost the type. A list goes
  back out as a CBOR array, so reading a record and writing it back either
  failed outright on a schemafull field::

      InternalError: Couldn't coerce value for field `nums`:
                     Expected `set` but found `[1, 2]`

  or, on a schemaless one, silently turned the field into an array and took its
  deduplication with it.

:class:`~surrealdb.data.types.set.SurrealSet` is a ``list`` subclass that
encodes back under the set tag, so both hold.
"""

import uuid
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.set import SurrealSet


def _fresh(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _supports_cbor_sets(version: str) -> bool:
    """Whether this server has a CBOR set representation at all.

    SurrealDB 2.x has none: it returns a SurrealQL set as a plain array and
    answers anything carrying the set tag with "unknown CBOR tag". That is
    documented in the README's 2.x compatibility section, so there is nothing
    for these tests to assert there.
    """
    text = (version or "").strip().lower()
    for prefix in ("surrealdb-", "v"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    try:
        return int(text.split(".")[0]) >= 3
    except (ValueError, IndexError):
        return False


@pytest.fixture(autouse=True)
def _needs_cbor_sets(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    if not _supports_cbor_sets(blocking_ws_connection.version()):
        pytest.skip("SurrealDB 2.x has no CBOR set representation")


# ------------------------------------------------------------ the round trip


def test_a_schemafull_set_field_can_be_written_back(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _fresh("sf")
    blocking_ws_connection.query(
        f"DEFINE TABLE {table} SCHEMAFULL; DEFINE FIELD nums ON {table} TYPE set<int>;"
    ).execute()
    blocking_ws_connection.query(f"CREATE {table}:1 SET nums = <set>[1,2]").execute()

    row = blocking_ws_connection.select(RecordID(table, 1))
    assert isinstance(row["nums"], SurrealSet)

    # The whole point: this used to raise a coercion error.
    blocking_ws_connection.update(RecordID(table, 1), row)

    after = blocking_ws_connection.select(RecordID(table, 1))
    assert after["nums"] == [1, 2]


def test_a_schemaless_set_field_stays_a_set(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The silent half: no error, the field just stopped being a set."""
    table = _fresh("sl")
    blocking_ws_connection.query(
        f"CREATE {table}:1 SET tags = <set>['a','b']"
    ).execute()

    blocking_ws_connection.update(
        RecordID(table, 1), blocking_ws_connection.select(RecordID(table, 1))
    )

    # Asked of the server, not of the decoded value: what matters is the type
    # the field now has in the database.
    blocking_ws_connection.query(f"UPDATE {table}:1 SET tags += 'a'").execute()
    stored = blocking_ws_connection.query(f"RETURN {table}:1.tags").first()
    assert isinstance(stored, list)
    assert sorted(stored) == ["a", "b"], (
        "the field lost its set semantics: a duplicate was accepted"
    )


async def test_async_set_round_trip(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    table = _fresh("as")
    await async_ws_connection.query(
        f"DEFINE TABLE {table} SCHEMAFULL; DEFINE FIELD nums ON {table} TYPE set<int>;"
    ).execute()
    await async_ws_connection.query(f"CREATE {table}:1 SET nums = <set>[1,2]").execute()

    row = await async_ws_connection.select(RecordID(table, 1))
    await async_ws_connection.update(RecordID(table, 1), row)

    after = await async_ws_connection.select(RecordID(table, 1))
    assert after["nums"] == [1, 2]


# ------------------------------------------------- what a set decodes to now


def test_a_set_of_objects_is_readable(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The original defect: a Python ``set`` cannot hold these at all."""
    assert blocking_ws_connection.query("RETURN <set>[{a:1},{a:2}];").first() == [
        {"a": 1},
        {"a": 2},
    ]
    assert blocking_ws_connection.query("RETURN <set>[[1,2]];").first() == [[1, 2]]


def test_a_set_reads_as_a_sequence(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """``SurrealSet`` is a ``list``, so it indexes and compares like one.

    The order is the server's, not the order written: SurrealDB normalises a
    set, so ``<set>[3,1,2]`` comes back ``[1,2,3]``. The SDK preserves whatever
    it receives rather than imposing an order of its own.
    """
    value = blocking_ws_connection.query("RETURN <set>[3,1,2];").first()

    assert isinstance(value, SurrealSet)
    assert isinstance(value, list)
    assert value == [1, 2, 3]
    assert value[0] == 1
    assert len(value) == 3


def test_writing_a_python_set_still_works(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The path that always worked, unchanged."""
    table = _fresh("ps")
    created = blocking_ws_connection.create(RecordID(table, "a"), {"tags": {"x", "y"}})

    tags = created["tags"]
    assert isinstance(tags, list)
    assert sorted(tags) == ["x", "y"]
    blocking_ws_connection.query(f"UPDATE {table}:a SET tags += 'x'").execute()
    after = blocking_ws_connection.query(f"RETURN {table}:a.tags").first()
    assert isinstance(after, list)
    assert sorted(after) == ["x", "y"]


# --------------------------------------------------------- encoding, offline


def test_a_surreal_set_encodes_under_the_set_tag() -> None:
    """Tag 56, not a plain array - a `list` subclass would otherwise match
    `list`'s encoder through the generic subclass lookup."""
    assert cbor.encode(SurrealSet([1, 2]))[:2] == b"\xd8\x38"
    assert cbor.encode({1, 2})[:2] == b"\xd8\x38"
    assert cbor.encode([1, 2])[:2] != b"\xd8\x38"


def test_a_surreal_set_round_trips_offline() -> None:
    decoded = cbor.decode(cbor.encode(SurrealSet([{"k": "a"}, [1, 2]])))

    assert isinstance(decoded, SurrealSet)
    assert decoded == [{"k": "a"}, [1, 2]]
    # And re-encoding is stable, so a value can be written back repeatedly.
    assert cbor.encode(decoded) == cbor.encode(SurrealSet([{"k": "a"}, [1, 2]]))


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"a": SurrealSet([1])}, id="in-an-object"),
        pytest.param([SurrealSet([1])], id="in-an-array"),
        pytest.param({"a": {"b": SurrealSet([1])}}, id="nested"),
    ],
)
def test_a_set_keeps_its_type_in_any_position(payload: Any) -> None:
    decoded = cbor.decode(cbor.encode(payload))

    found = decoded["a"] if isinstance(decoded, dict) else decoded[0]
    if isinstance(found, dict):
        found = found["b"]
    assert isinstance(found, SurrealSet)
