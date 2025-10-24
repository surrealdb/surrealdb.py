from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def update_data() -> dict[str, Any]:
    return {
        "name": "Jaime",
        "email": "jaime@example.com",
        "enabled": True,
        "password": "root",
    }


@pytest.fixture
def record_id() -> RecordID:
    return RecordID("user", "tobie")


def check_no_change(data: dict[str, Any], record_id) -> None:
    assert record_id == data["id"]
    assert "Tobie" == data["name"]


def check_change(data: dict[str, Any], record_id) -> None:
    assert record_id == data["id"]
    assert "Jaime" == data["name"]
    # No age field assertion


def test_update_string(
    blocking_http_connection: BlockingHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id,
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    outcome = blocking_http_connection.update("user:tobie")
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    check_no_change(outcome[0], record_id)
    blocking_http_connection.query("DELETE user;")


def test_update_string_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id,
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    first_outcome = blocking_http_connection.update("user:tobie", update_data)
    print("DEBUG update_string_with_data result:", first_outcome)
    check_change(first_outcome, record_id)
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    print("DEBUG update_string_with_data query result:", outcome)
    check_change(outcome[0], record_id)
    blocking_http_connection.query("DELETE user;")


def test_update_record_id(
    blocking_http_connection: BlockingHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id,
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    first_outcome = blocking_http_connection.update(record_id)
    check_no_change(first_outcome, record_id)
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    check_no_change(outcome[0], record_id)
    blocking_http_connection.query("DELETE user;")


def test_update_record_id_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id,
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    outcome = blocking_http_connection.update(record_id, update_data)
    print("DEBUG update_record_id_with_data result:", outcome)
    check_change(outcome, record_id)
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    print("DEBUG update_record_id_with_data query result:", outcome)
    check_change(outcome[0], record_id)
    blocking_http_connection.query("DELETE user;")


def test_update_table(
    blocking_http_connection: BlockingHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id,
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    table = Table("user")
    first_outcome = blocking_http_connection.update(table)
    check_no_change(first_outcome[0], record_id)
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    check_no_change(outcome[0], record_id)
    blocking_http_connection.query("DELETE user;")


def test_update_table_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id,
) -> None:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    table = Table("user")
    outcome = blocking_http_connection.update(table, update_data)
    print("DEBUG update_table_with_data result:", outcome)
    check_change(outcome[0], record_id)
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    print("DEBUG update_table_with_data query result:", outcome)
    check_change(outcome[0], record_id)
    blocking_http_connection.query("DELETE user;")
