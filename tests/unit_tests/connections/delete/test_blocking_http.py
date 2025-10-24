from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def record_id() -> RecordID:
    return RecordID("user", "tobie")


def check_no_change(data: dict[str, Any], record_id) -> None:
    assert record_id == data["id"]
    assert "Tobie" == data["name"]


def check_change(data: dict[str, Any], record_id) -> None:
    assert record_id == data["id"]
    assert "Jaime" == data["name"]
    assert 35 == data["age"]


def test_debug_delete(blocking_http_connection: BlockingHttpSurrealConnection) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query("CREATE user:tobie SET name = 'Tobie';")

    # Debug: Check what delete actually returns
    outcome = blocking_http_connection.delete("user:tobie")
    print(f"DEBUG: Delete outcome: {outcome}")
    print(f"DEBUG: Type: {type(outcome)}")

    # Verify the record was actually deleted
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    assert outcome == []


def test_delete_string(
    blocking_http_connection: BlockingHttpSurrealConnection, record_id: RecordID
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query("CREATE user:tobie SET name = 'Tobie';")

    # Delete operation returns the deleted record
    outcome = blocking_http_connection.delete("user:tobie")
    assert outcome is not None
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"

    # Verify the record was actually deleted
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    assert outcome == []


def test_delete_record_id(
    blocking_http_connection: BlockingHttpSurrealConnection, record_id: RecordID
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query("CREATE user:tobie SET name = 'Tobie';")

    # Delete operation returns the deleted record
    outcome = blocking_http_connection.delete(record_id)
    assert outcome is not None
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"

    # Verify the record was actually deleted
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    assert outcome == []


def test_delete_table(blocking_http_connection: BlockingHttpSurrealConnection) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query("CREATE user:tobie SET name = 'Tobie';")
    blocking_http_connection.query("CREATE user:jaime SET name = 'Jaime';")

    # Delete all users in the table
    table = Table("user")
    outcome = blocking_http_connection.delete(table)
    # Table delete returns list of deleted records
    assert len(outcome) == 2
    assert any(record["name"] == "Tobie" for record in outcome)
    assert any(record["name"] == "Jaime" for record in outcome)

    # Verify all records were deleted
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    assert outcome == []
