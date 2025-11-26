from collections.abc import AsyncGenerator
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def patch_data() -> dict[str, Any]:
    return [
        {"op": "replace", "path": "/name", "value": "Jaime"},
        {"op": "replace", "path": "/email", "value": "jaime@example.com"},
        {"op": "replace", "path": "/enabled", "value": False},
    ]


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
async def test_patch_string_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    patch_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = await async_http_connection.patch("user:tobie", patch_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is False
    result = await async_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is False


@pytest.mark.asyncio
async def test_patch_record_id_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    patch_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", "tobie")
    outcome = await async_http_connection.patch(record_id, patch_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is False
    result = await async_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is False


@pytest.mark.asyncio
async def test_patch_table_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    patch_data: dict[str, Any],
    setup_user: None,
) -> None:
    table = Table("user")
    record_id = RecordID("user", "tobie")
    outcome = await async_http_connection.patch(table, patch_data)
    assert outcome[0]["id"] == record_id
    assert outcome[0]["name"] == "Jaime"
    assert outcome[0]["email"] == "jaime@example.com"
    assert outcome[0]["enabled"] is False
    result = await async_http_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is False
