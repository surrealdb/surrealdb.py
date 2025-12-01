from collections.abc import Generator
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def upsert_data() -> dict[str, Any]:
    return {
        "name": "Jaime",
        "email": "jaime@example.com",
        "password": "password456",
        "enabled": True,
    }


@pytest.fixture
def existing_data() -> dict[str, Any]:
    return {
        "name": "Tobie",
        "email": "tobie@example.com",
        "password": "password123",
        "enabled": True,
    }


@pytest.fixture(autouse=True)
def setup_user(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield
    blocking_ws_connection.query("DELETE user;")


def test_upsert_string(
    blocking_ws_connection: BlockingWsSurrealConnection, setup_user: None, existing_data
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = blocking_ws_connection.upsert("user:tobie", existing_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"
    assert outcome["email"] == "tobie@example.com"
    assert outcome["enabled"] is True
    result = blocking_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"
    assert result[0]["email"] == "tobie@example.com"
    assert result[0]["enabled"] is True


def test_upsert_string_with_data(
    blocking_ws_connection: BlockingWsSurrealConnection,
    upsert_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    first_outcome = blocking_ws_connection.upsert("user:tobie", upsert_data)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Jaime"
    assert first_outcome["email"] == "jaime@example.com"
    assert first_outcome["enabled"] is True
    result = blocking_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


def test_upsert_record_id(
    blocking_ws_connection: BlockingWsSurrealConnection, setup_user: None, existing_data
) -> None:
    record_id = RecordID("user", "tobie")
    first_outcome = blocking_ws_connection.upsert(record_id, existing_data)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Tobie"
    assert first_outcome["email"] == "tobie@example.com"
    assert first_outcome["enabled"] is True
    result = blocking_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"
    assert result[0]["email"] == "tobie@example.com"
    assert result[0]["enabled"] is True


def test_upsert_record_id_with_data(
    blocking_ws_connection: BlockingWsSurrealConnection,
    upsert_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = blocking_ws_connection.upsert(record_id, upsert_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is True
    result = blocking_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


def test_upsert_table(
    blocking_ws_connection: BlockingWsSurrealConnection, setup_user: None, existing_data
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    first_outcome = blocking_ws_connection.upsert(table, existing_data)
    result = blocking_ws_connection.query("SELECT * FROM user;")
    # SurrealDB may create a new record or not, depending on version
    assert any(r["id"] == record_id for r in result)
    assert any(r["name"] == "Tobie" for r in result)


def test_upsert_table_with_data(
    blocking_ws_connection: BlockingWsSurrealConnection,
    upsert_data: dict[str, Any],
    setup_user: None,
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    outcome = blocking_ws_connection.upsert(table, upsert_data)
    # At least one record should match the upserted data
    assert any(
        r["name"] == "Jaime"
        and r["email"] == "jaime@example.com"
        and r["enabled"] is True
        for r in outcome
    )
    result = blocking_ws_connection.query("SELECT * FROM user;")
    assert any(
        r["name"] == "Jaime"
        and r["email"] == "jaime@example.com"
        and r["enabled"] is True
        for r in result
    )
