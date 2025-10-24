from collections.abc import AsyncGenerator
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def create_data() -> dict[str, Any]:
    return {
        "name": "Test User",
        "email": "test@example.com",
        "password": "password123",
        "enabled": True,
    }


@pytest.fixture(autouse=True)
async def setup_user(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query("DELETE user;")
    yield
    await async_ws_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_create_string(
    async_ws_connection: AsyncWsSurrealConnection, setup_user: None
) -> None:
    outcome = await async_ws_connection.create("user")
    assert "user" == outcome["id"].table_name

    assert len(await async_ws_connection.query("SELECT * FROM user;")) == 1


@pytest.mark.asyncio
async def test_create_string_with_data(
    async_ws_connection: AsyncWsSurrealConnection,
    create_data: dict[str, Any],
    setup_user: None,
) -> None:
    outcome = await async_ws_connection.create("user", create_data)
    assert "user" == outcome["id"].table_name
    assert create_data["name"] == outcome["name"]
    assert create_data["email"] == outcome["email"]
    assert create_data["enabled"] == outcome["enabled"]

    result = await async_ws_connection.query("SELECT * FROM user;")
    assert len(result) == 1
    assert "user" == result[0]["id"].table_name
    assert create_data["name"] == result[0]["name"]
    assert create_data["email"] == result[0]["email"]
    assert create_data["enabled"] == result[0]["enabled"]


@pytest.mark.asyncio
async def test_create_string_with_data_and_id(
    async_ws_connection: AsyncWsSurrealConnection,
    create_data: dict[str, Any],
    setup_user: None,
) -> None:
    first_outcome = await async_ws_connection.create("user:tobie", create_data)
    assert "user" == first_outcome["id"].table_name
    assert "tobie" == first_outcome["id"].id
    assert create_data["name"] == first_outcome["name"]
    assert create_data["email"] == first_outcome["email"]
    assert create_data["enabled"] == first_outcome["enabled"]

    result = await async_ws_connection.query("SELECT * FROM user;")
    assert len(result) == 1
    assert "user" == result[0]["id"].table_name
    assert "tobie" == result[0]["id"].id
    assert create_data["name"] == result[0]["name"]
    assert create_data["email"] == result[0]["email"]
    assert create_data["enabled"] == result[0]["enabled"]


@pytest.mark.asyncio
async def test_create_record_id(
    async_ws_connection: AsyncWsSurrealConnection, setup_user: None
) -> None:
    record_id = RecordID("user", 1)
    outcome = await async_ws_connection.create(record_id)
    assert "user" == outcome["id"].table_name
    assert 1 == outcome["id"].id

    assert len(await async_ws_connection.query("SELECT * FROM user;")) == 1


@pytest.mark.asyncio
async def test_create_record_id_with_data(
    async_ws_connection: AsyncWsSurrealConnection,
    create_data: dict[str, Any],
    setup_user: None,
) -> None:
    record_id = RecordID("user", 1)
    outcome = await async_ws_connection.create(record_id, create_data)
    assert "user" == outcome["id"].table_name
    assert 1 == outcome["id"].id
    assert create_data["name"] == outcome["name"]
    assert create_data["email"] == outcome["email"]
    assert create_data["enabled"] == outcome["enabled"]

    result = await async_ws_connection.query("SELECT * FROM user;")
    assert len(result) == 1
    assert "user" == result[0]["id"].table_name
    assert create_data["name"] == result[0]["name"]
    assert create_data["email"] == result[0]["email"]
    assert create_data["enabled"] == result[0]["enabled"]


@pytest.mark.asyncio
async def test_create_table(
    async_ws_connection: AsyncWsSurrealConnection, setup_user: None
) -> None:
    table = Table("user")
    outcome = await async_ws_connection.create(table)
    assert "user" == outcome["id"].table_name

    assert len(await async_ws_connection.query("SELECT * FROM user;")) == 1


@pytest.mark.asyncio
async def test_create_table_with_data(
    async_ws_connection: AsyncWsSurrealConnection,
    create_data: dict[str, Any],
    setup_user: None,
) -> None:
    table = Table("user")
    outcome = await async_ws_connection.create(table, create_data)
    assert "user" == outcome["id"].table_name
    assert create_data["name"] == outcome["name"]
    assert create_data["email"] == outcome["email"]
    assert create_data["enabled"] == outcome["enabled"]

    result = await async_ws_connection.query("SELECT * FROM user;")
    assert len(result) == 1
    assert "user" == result[0]["id"].table_name
    assert create_data["name"] == result[0]["name"]
    assert create_data["email"] == result[0]["email"]
    assert create_data["enabled"] == result[0]["enabled"]
