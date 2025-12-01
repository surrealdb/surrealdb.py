from collections.abc import Generator
from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def merge_data() -> dict[str, Any]:
    return {
        "name": "Jaime",
        "email": "jaime@example.com",
        "password": "password456",
        "enabled": True,
    }


@pytest.fixture(autouse=True)
def setup_user(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> Generator[None, None, None]:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield
    blocking_http_connection.query("DELETE user;")


def test_merge_string(
    blocking_http_connection: BlockingHttpSurrealConnection, setup_user: None
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = blocking_http_connection.merge("user:tobie")
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"
    result = blocking_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"


def test_merge_string_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    merge_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    first_outcome = blocking_http_connection.merge("user:tobie", merge_data)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Jaime"
    assert first_outcome["email"] == "jaime@example.com"
    assert first_outcome["enabled"] is True
    result = blocking_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


def test_merge_record_id(
    blocking_http_connection: BlockingHttpSurrealConnection, setup_user: None
) -> None:
    record_id = RecordID("user", "tobie")
    first_outcome = blocking_http_connection.merge(record_id)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Tobie"
    result = blocking_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"


def test_merge_record_id_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    merge_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = blocking_http_connection.merge(record_id, merge_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is True
    result = blocking_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


def test_merge_table(
    blocking_http_connection: BlockingHttpSurrealConnection, setup_user: None
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    first_outcome = blocking_http_connection.merge(table)
    assert first_outcome[0]["id"] == record_id
    assert first_outcome[0]["name"] == "Tobie"
    result = blocking_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"


def test_merge_table_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    merge_data: dict[str, Any],
    setup_user: None,
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    outcome = blocking_http_connection.merge(table, merge_data)
    assert outcome[0]["id"] == record_id
    assert outcome[0]["name"] == "Jaime"
    assert outcome[0]["email"] == "jaime@example.com"
    assert outcome[0]["enabled"] is True
    result = blocking_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True
