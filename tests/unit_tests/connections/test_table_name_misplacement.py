"""A non-string table name no longer writes real data somewhere unfindable.

This is the half of constructor validation that was a data bug rather than a
message one, so it is asserted against a live server rather than offline.

``Table(None)`` was not rejected anywhere: not by the constructor, not by the
encoder, and not by the server. ``insert(Table(None), [row])`` *succeeded*,
returned a plausible-looking record, and put the row in a table literally named
``None`` - confirmed on SurrealDB 2.0.5 and 3.2.3 alike, with ``INFO FOR DB``
listing the table afterwards. Nothing anywhere said the write had gone
somewhere other than where it was aimed.
"""

import uuid
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.table import Table


@pytest.mark.parametrize("name", [None, 123, b"person"])
def test_a_non_string_table_name_never_reaches_the_server(
    blocking_ws_connection: BlockingWsSurrealConnection, name: Any
) -> None:
    with pytest.raises(TypeError):
        blocking_ws_connection.insert(Table(name), [{"marker": "x"}])


def test_nothing_is_written_to_a_table_named_none(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The observable consequence, asked of the database.

    Not "did it raise" but "is the row anywhere", because the failure mode was
    a successful-looking write that landed in the wrong place.
    """
    marker = uuid.uuid4().hex[:12]

    with pytest.raises(TypeError):
        blocking_ws_connection.insert(Table(None), [{"marker": marker}])

    # ⟨None⟩ is the table the row used to land in. It should not exist at all,
    # but a previous run of the old code could have created it - so search it
    # for this run's marker rather than asserting it is absent.
    blocking_ws_connection.query(
        "DEFINE TABLE IF NOT EXISTS ⟨None⟩ SCHEMALESS"
    ).execute()
    stray = blocking_ws_connection.query(
        "SELECT * FROM ⟨None⟩ WHERE marker = $m", vars={"m": marker}
    ).first()

    assert stray == [], f"the row was written to a table named None: {stray!r}"


def test_a_valid_table_name_still_writes(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The neighbouring behaviour the guard must not disturb.

    ``"has space"`` is here because the guard checks the *type* only - the
    server takes any string, and a name needing escaping must keep working.
    A name with non-ASCII letters is deliberately not exercised: ``insert``
    rejects one today for an unrelated reason (``escape_identifier`` treats
    accented letters as safe and leaves them unquoted, and ``insert`` is the
    one path that inlines the table name), which predates this change and is
    tracked separately.
    """
    for name in (f"tbl_{uuid.uuid4().hex[:8]}", "has space"):
        written = blocking_ws_connection.insert(Table(name), [{"marker": "ok"}])
        assert isinstance(written, list) and written
        assert written[0]["id"].table_name == name
