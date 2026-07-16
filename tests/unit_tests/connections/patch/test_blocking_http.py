from collections.abc import Generator
from typing import Any, cast

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.types import Value


@pytest.fixture
def patch_data() -> list[dict[str, Any]]:
    return [
        {"op": "replace", "path": "/name", "value": "Jaime"},
        {"op": "replace", "path": "/email", "value": "jaime@example.com"},
        {"op": "replace", "path": "/enabled", "value": False},
    ]


@pytest.fixture(autouse=True)
def setup_user(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> Generator[None, None, None]:
    blocking_http_connection.query("DELETE user;").execute()
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    ).execute()
    yield
    blocking_http_connection.query("DELETE user;").execute()


def test_patch_string_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    patch_data: list[dict[str, Any]],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = blocking_http_connection.update("user:tobie").patch(
        cast(Value, patch_data)
    )
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is False
    result = blocking_http_connection.query("SELECT * FROM user;").first()
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is False


def test_patch_record_id_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    patch_data: list[dict[str, Any]],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = blocking_http_connection.update(record_id).patch(cast(Value, patch_data))
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is False
    result = blocking_http_connection.query("SELECT * FROM user;").first()
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is False


def test_patch_table_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
    patch_data: list[dict[str, Any]],
    setup_user: None,
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    outcome = blocking_http_connection.update(table).patch(cast(Value, patch_data))
    assert outcome[0]["id"] == record_id
    assert outcome[0]["name"] == "Jaime"
    assert outcome[0]["email"] == "jaime@example.com"
    assert outcome[0]["enabled"] is False
    result = blocking_http_connection.query("SELECT * FROM user;").first()
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is False
