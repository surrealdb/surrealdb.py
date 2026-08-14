"""Table and record-id names the server accepts survive being written.

``db.insert(Table("héllo"), rows)`` failed with ``Parse error: Invalid token
`é``` while ``db.create`` into the same table worked. ``INSERT`` is the one
statement whose target the SDK *inlines* rather than binds - SurrealDB rejects
``INSERT INTO type::table($x)`` - so it is the only operation that depends on
``escape_identifier`` getting the quoting right, and the only one that broke.

The rule was ``any(not c.isalnum() and c != "_")``. Python calls a letter or
digit of *any* script alphanumeric - ``é``, ``α``, ``表``, ``таблица``, and the
superscript ``²`` - while SurrealDB's parser rejects every one of them in a
bare identifier, so they were judged safe and left unquoted. The same rule
passed ``1tbl`` through, which the parser also refuses: by the time it reaches
the letters it has committed to reading a number.

Emoji and punctuation were never affected - they are symbols, so ``isalnum()``
already returned False and they were already being wrapped. They are covered
below anyway, as a guard that the new rule did not lose them.

Wrapping in ``⟨...⟩`` works for all of them, on 2.0.5, 2.3.10 and 3.2.3 alike,
which is why the fix is to quote more rather than to reject anything.
"""

import uuid
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table

# Every one of these is rejected by the parser unquoted and accepted quoted.
# `tbl²` is here because `"²".isalnum()` and `"²".isdigit()` are both True in
# Python, so the old rule mis-classified a digit as well as letters. The last
# three were already handled correctly and are kept as guards.
AWKWARD_NAMES = [
    pytest.param("héllo", id="accented"),
    pytest.param("表格", id="cjk"),
    pytest.param("αβγ", id="greek"),
    pytest.param("таблица", id="cyrillic"),
    pytest.param("tbl🙂", id="emoji"),
    pytest.param("tbl²", id="superscript-digit"),
    pytest.param("has space", id="space"),
    pytest.param("1tbl", id="leading-digit"),
    pytest.param("kebab-case", id="hyphen"),
]


def _fresh(name: str) -> str:
    """A unique table name that keeps the awkward part."""
    return f"{name}_{uuid.uuid4().hex[:8]}"


@pytest.mark.parametrize("name", AWKWARD_NAMES)
def test_insert_into_an_awkward_table_name_round_trips(
    blocking_ws_connection: BlockingWsSurrealConnection, name: str
) -> None:
    """The reported failure, asserted by reading the row back.

    Not just "it did not raise": the point is that the row is retrievable from
    the table it was aimed at.
    """
    table = _fresh(name)
    marker = uuid.uuid4().hex[:12]

    written = blocking_ws_connection.insert(Table(table), [{"marker": marker}])

    assert isinstance(written, list) and written
    assert written[0]["id"].table_name == table

    back = blocking_ws_connection.select(Table(table))
    assert isinstance(back, list)
    assert [row["marker"] for row in back] == [marker]


@pytest.mark.parametrize("name", AWKWARD_NAMES)
def test_create_and_select_agree_with_insert(
    blocking_ws_connection: BlockingWsSurrealConnection, name: str
) -> None:
    """``create`` always worked because it binds its target. Both spellings of
    the same intent must now reach the same table."""
    table = _fresh(name)

    blocking_ws_connection.create(RecordID(table, "a"), {"n": 1})
    blocking_ws_connection.insert(Table(table), [{"n": 2}])

    rows: Any = blocking_ws_connection.select(Table(table))
    assert isinstance(rows, list)
    assert sorted(row["n"] for row in rows) == [1, 2]


@pytest.mark.parametrize("name", AWKWARD_NAMES)
def test_str_of_a_record_id_is_parseable_surrealql(
    blocking_ws_connection: BlockingWsSurrealConnection, name: str
) -> None:
    """``str(record_id)`` is what the docstring recommends for composing query
    text where binding is impossible, so the server has to accept it.

    The table half was never escaped, only the id, so this produced
    unparseable text for exactly the names above.
    """
    table = _fresh(name)
    record = RecordID(table, name)

    blocking_ws_connection.query(f"CREATE {record} SET n = 1").execute()

    read = blocking_ws_connection.query(f"SELECT * FROM {record}").first()
    assert isinstance(read, list) and len(read) == 1
    assert read[0]["id"] == record


def test_a_plain_name_is_still_not_quoted() -> None:
    """The optimisation the rule exists for - and the pinned rendering that
    everything else in the SDK depends on."""
    from surrealdb.data.types.record_id import escape_identifier

    assert escape_identifier("users") == "users"
    assert escape_identifier("user_table") == "user_table"
    assert escape_identifier("_private") == "_private"
    assert str(RecordID("users", "john")) == "users:john"


@pytest.mark.parametrize("name", AWKWARD_NAMES)
def test_the_http_transport_agrees(
    blocking_http_connection: BlockingHttpSurrealConnection, name: str
) -> None:
    table = _fresh(name)
    marker = uuid.uuid4().hex[:12]

    blocking_http_connection.insert(Table(table), [{"marker": marker}])

    back = blocking_http_connection.select(Table(table))
    assert isinstance(back, list)
    assert [row["marker"] for row in back] == [marker]


async def test_the_async_transport_agrees(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    table = _fresh("héllo")
    marker = uuid.uuid4().hex[:12]

    await async_ws_connection.insert(Table(table), [{"marker": marker}])

    back = await async_ws_connection.select(Table(table))
    assert isinstance(back, list)
    assert [row["marker"] for row in back] == [marker]
