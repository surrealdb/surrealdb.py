from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def record_id() -> RecordID:
    return RecordID("user", "tobie")


@pytest.mark.asyncio
async def test_delete_string(
    async_http_connection: AsyncHttpSurrealConnection, record_id: RecordID
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query("CREATE user:tobie SET name = 'Tobie';")

    # Delete operation returns the deleted record
    outcome = await async_http_connection.delete("user:tobie")
    assert outcome is not None
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"

    # Verify the record was actually deleted
    remaining = await async_http_connection.query("SELECT * FROM user;").first()
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_record_id(
    async_http_connection: AsyncHttpSurrealConnection, record_id: RecordID
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query("CREATE user:tobie SET name = 'Tobie';")

    # Delete operation returns the deleted record
    outcome = await async_http_connection.delete(record_id)
    assert outcome is not None
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"

    # Verify the record was actually deleted
    remaining = await async_http_connection.query("SELECT * FROM user;").first()
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_record_id_absent(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query("DELETE user;")

    # Deleting an absent record returns None (matching select).
    outcome = await async_http_connection.delete(RecordID("user", "missing"))
    assert outcome is None


@pytest.mark.asyncio
async def test_delete_string_absent(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query("DELETE user;")

    # Deleting an absent "table:id" record returns None (matching select).
    outcome = await async_http_connection.delete("user:missing")
    assert outcome is None


@pytest.mark.asyncio
async def test_delete_table(async_http_connection: AsyncHttpSurrealConnection) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query("CREATE user:tobie SET name = 'Tobie';")
    await async_http_connection.query("CREATE user:jaime SET name = 'Jaime';")

    # Delete all users in the table
    table = Table("user")
    outcome = await async_http_connection.delete(table)
    # Table delete returns list of deleted records
    assert len(outcome) == 2
    assert any(record["name"] == "Tobie" for record in outcome)
    assert any(record["name"] == "Jaime" for record in outcome)

    # Verify all records were deleted
    remaining = await async_http_connection.query("SELECT * FROM user;").first()
    assert remaining == []
