from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def record_id() -> RecordID:
    return RecordID("user", "tobie")


def test_delete_string(
    blocking_ws_connection: BlockingWsSurrealConnection, record_id
) -> None:
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query("CREATE user:tobie SET name = 'Tobie';")

    # Delete operation returns the deleted record
    outcome = blocking_ws_connection.delete("user:tobie")
    assert outcome is not None
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"

    # Verify the record was actually deleted
    outcome = blocking_ws_connection.query("SELECT * FROM user;")
    assert outcome == []


def test_delete_record_id(
    blocking_ws_connection: BlockingWsSurrealConnection, record_id
) -> None:
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query("CREATE user:tobie SET name = 'Tobie';")

    # Delete operation returns the deleted record
    outcome = blocking_ws_connection.delete(record_id)
    assert outcome is not None
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"

    # Verify the record was actually deleted
    outcome = blocking_ws_connection.query("SELECT * FROM user;")
    assert outcome == []


def test_delete_table(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query("CREATE user:tobie SET name = 'Tobie';")
    blocking_ws_connection.query("CREATE user:jaime SET name = 'Jaime';")

    # Delete all users in the table
    table = Table("user")
    outcome = blocking_ws_connection.delete(table)
    # Table delete returns list of deleted records
    assert len(outcome) == 2
    assert any(record["name"] == "Tobie" for record in outcome)
    assert any(record["name"] == "Jaime" for record in outcome)

    # Verify all records were deleted
    outcome = blocking_ws_connection.query("SELECT * FROM user;")
    assert outcome == []
