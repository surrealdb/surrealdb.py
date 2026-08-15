"""``select(fields=[...])`` narrows the projection without opening a hole.

The capability was always reachable through ``query("SELECT a, b FROM $r")``;
what this adds is the discoverable spelling on the method that already binds
the resource for you, and composes with ``into=``.

A field list is the one part of the statement that cannot be parameter-bound -
SurrealQL has no ``SELECT $f`` - so it has to be inlined, which is exactly why
it has to be escaped. Joining the caller's strings straight into the query, as
the original proposal did, turns a field list into arbitrary SurrealQL:

    ", ".join(["a", "b FROM other; --"])  ->  SELECT a, b FROM other; --

Two escaping traps are covered below because getting either wrong is silent
rather than loud:

* escaping a whole ``"address.city"`` yields ``⟨address.city⟩``, which the
  server reads as one field of that literal name and answers with ``None`` -
  no error, just a null where the value should be;
* a bare string spreads per character, so ``fields="name"`` would project
  ``n, a, m, e``. That is the same shape as the ``run("fn::f", "ab")`` bug that
  called ``f("a", "b")``.
"""

import uuid
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.utils_mixin import render_projection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table

_SETUP = (
    'CREATE {t}:1 SET a = 1, b = 2, blob = "not wanted", '
    'address = {{ city: "Paris", zip: "75001" }}, '
    "⟨my field⟩ = 3, ⟨héllo⟩ = 4"
)


def _rows(connection: Any) -> str:
    table = f"fld_{uuid.uuid4().hex[:8]}"
    connection.query(_SETUP.format(t=table)).execute()
    return table


# --------------------------------------------------------------- the projection


def test_only_the_named_fields_come_back(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)

    row = blocking_ws_connection.select(RecordID(table, 1), fields=["a", "b"])

    assert row == {"a": 1, "b": 2}


def test_the_default_is_unchanged(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """``fields=None`` has to emit exactly what it emitted before this existed."""
    table = _rows(blocking_ws_connection)

    row: Any = blocking_ws_connection.select(RecordID(table, 1))

    assert set(row) == {"a", "b", "blob", "address", "my field", "héllo", "id"}
    assert render_projection(None) == "*"


def test_a_table_target_projects_every_row(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    table = _rows(blocking_ws_connection)
    blocking_ws_connection.query(f"CREATE {table}:2 SET a = 9, b = 8").execute()

    rows: Any = blocking_ws_connection.select(Table(table), fields=["a"])

    assert sorted(row["a"] for row in rows) == [1, 9]
    assert all(set(row) == {"a"} for row in rows)


def test_id_is_not_included_unless_asked_for(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Documented, and the thing most likely to surprise an ``into=`` user."""
    table = _rows(blocking_ws_connection)

    assert "id" not in blocking_ws_connection.select(RecordID(table, 1), fields=["a"])
    assert "id" in blocking_ws_connection.select(RecordID(table, 1), fields=["id", "a"])


def test_it_composes_with_into(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    from dataclasses import dataclass

    @dataclass
    class Partial:
        a: int
        b: int

    table = _rows(blocking_ws_connection)

    row = blocking_ws_connection.select(
        RecordID(table, 1), fields=["a", "b"], into=Partial
    )

    assert row == Partial(a=1, b=2)


# --------------------------------------------------------------- escaping


def test_a_dotted_name_walks_into_the_nested_object(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The trap: escaping the whole string returns ``None`` rather than raising.

    ``⟨address.city⟩`` is a field literally named ``address.city``, which does
    not exist, so the server answers with a null and nothing anywhere says the
    projection was misread.
    """
    table = _rows(blocking_ws_connection)

    row = blocking_ws_connection.select(RecordID(table, 1), fields=["address.city"])

    assert row == {"address": {"city": "Paris"}}
    assert render_projection(["address.city"]) == "address.city"


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        pytest.param("my field", 3, id="space"),
        pytest.param("héllo", 4, id="unicode"),
    ],
)
def test_a_name_needing_quotes_is_quoted(
    blocking_ws_connection: BlockingWsSurrealConnection, field: str, expected: int
) -> None:
    table = _rows(blocking_ws_connection)

    row = blocking_ws_connection.select(RecordID(table, 1), fields=[field])

    assert row == {field: expected}


def test_a_field_list_cannot_smuggle_in_surrealql(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The defect in the original proposal, asserted against a live server.

    Joined raw this reads ``SELECT a, b FROM other_table; --``. Escaped, the
    whole thing is one (absent) field name, so the statement stays a
    projection of the table that was asked for.
    """
    table = _rows(blocking_ws_connection)
    hostile = "b FROM other_table; --"

    row: Any = blocking_ws_connection.select(RecordID(table, 1), fields=["a", hostile])

    assert row["a"] == 1
    assert row[hostile] is None, "the injected text was not treated as a field name"
    assert "⟨" in render_projection([hostile])


# --------------------------------------------------------------- refusals


def test_a_bare_string_is_refused_not_spread() -> None:
    with pytest.raises(TypeError) as caught:
        render_projection("name")  # pyright: ignore[reportArgumentType]

    assert "not a single string" in str(caught.value)


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        pytest.param([], ValueError, id="empty-list"),
        pytest.param([""], ValueError, id="empty-name"),
        pytest.param(["a..b"], ValueError, id="empty-segment"),
        pytest.param([".a"], ValueError, id="leading-dot"),
        pytest.param([1], TypeError, id="not-a-string"),
    ],
)
def test_unusable_field_lists_are_refused(
    fields: Any, expected: type[Exception]
) -> None:
    with pytest.raises(expected):
        render_projection(fields)


def test_the_refusal_happens_before_any_io(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """A caller mistake is decided locally, and the connection is untouched."""
    table = _rows(blocking_ws_connection)

    with pytest.raises(TypeError):
        blocking_ws_connection.select(RecordID(table, 1), fields="a")  # pyright: ignore[reportArgumentType]

    assert blocking_ws_connection.query("RETURN 1").first() == 1


# --------------------------------------------------------------- every transport


def test_the_blocking_http_transport_agrees(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    table = _rows(blocking_http_connection)

    assert blocking_http_connection.select(RecordID(table, 1), fields=["a"]) == {"a": 1}


async def test_the_async_ws_transport_agrees(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    table = f"fld_{uuid.uuid4().hex[:8]}"
    await async_ws_connection.query(_SETUP.format(t=table)).execute()

    row = await async_ws_connection.select(RecordID(table, 1), fields=["a", "b"])

    assert row == {"a": 1, "b": 2}


async def test_the_async_http_transport_agrees(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    table = f"fld_{uuid.uuid4().hex[:8]}"
    await async_http_connection.query(_SETUP.format(t=table))

    row = await async_http_connection.select(RecordID(table, 1), fields=["b"])

    assert row == {"b": 2}
