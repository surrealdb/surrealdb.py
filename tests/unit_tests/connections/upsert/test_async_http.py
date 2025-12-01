from collections.abc import AsyncGenerator
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
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
async def setup_user(
    async_http_connection: AsyncHttpSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield
    await async_http_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_upsert_string(
    async_http_connection: AsyncHttpSurrealConnection, setup_user: None, existing_data
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = await async_http_connection.upsert("user:tobie", existing_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"
    assert outcome["email"] == "tobie@example.com"
    assert outcome["enabled"] is True
    result = await async_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"
    assert result[0]["email"] == "tobie@example.com"
    assert result[0]["enabled"] is True


@pytest.mark.asyncio
async def test_upsert_string_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    upsert_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    first_outcome = await async_http_connection.upsert("user:tobie", upsert_data)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Jaime"
    assert first_outcome["email"] == "jaime@example.com"
    assert first_outcome["enabled"] is True
    result = await async_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


@pytest.mark.asyncio
async def test_upsert_record_id(
    async_http_connection: AsyncHttpSurrealConnection, setup_user: None, existing_data
) -> None:
    record_id = RecordID("user", "tobie")
    first_outcome = await async_http_connection.upsert(record_id, existing_data)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Tobie"
    assert first_outcome["email"] == "tobie@example.com"
    assert first_outcome["enabled"] is True
    result = await async_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"
    assert result[0]["email"] == "tobie@example.com"
    assert result[0]["enabled"] is True


@pytest.mark.asyncio
async def test_upsert_record_id_with_data(
    async_http_connection, upsert_data: dict[str, Any], setup_user
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = await async_http_connection.upsert(record_id, upsert_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is True
    result = await async_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


@pytest.mark.asyncio
async def test_upsert_table(
    async_http_connection: AsyncHttpSurrealConnection, setup_user: None, existing_data
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    first_outcome = await async_http_connection.upsert(table, existing_data)
    result = await async_http_connection.query("SELECT * FROM user;")
    # SurrealDB may create a new record or not, depending on version
    assert any(r["id"] == record_id for r in result)
    assert any(r["name"] == "Tobie" for r in result)


@pytest.mark.asyncio
async def test_upsert_table_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    upsert_data: dict[str, Any],
    setup_user: None,
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    outcome = await async_http_connection.upsert(table, upsert_data)
    # At least one record should match the upserted data
    assert any(
        r["name"] == "Jaime"
        and r["email"] == "jaime@example.com"
        and r["enabled"] is True
        for r in outcome
    )
    result = await async_http_connection.query("SELECT * FROM user;")
    assert any(
        r["name"] == "Jaime"
        and r["email"] == "jaime@example.com"
        and r["enabled"] is True
        for r in result
    )
