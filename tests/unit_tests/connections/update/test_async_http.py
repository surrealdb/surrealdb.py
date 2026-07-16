from typing import Any, cast

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
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


def check_no_change(data: dict[str, Any], record_id: RecordID) -> None:
    assert record_id == data["id"]
    assert "Tobie" == data["name"]


def check_change(data: dict[str, Any], record_id: RecordID) -> None:
    assert record_id == data["id"]
    assert "Jaime" == data["name"]
    # No age field assertion


@pytest.mark.asyncio
async def test_update_string(
    async_http_connection: AsyncHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id: RecordID,
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    outcome = await async_http_connection.update("user:tobie")
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"
    rows = cast(
        list[dict[str, Any]],
        await async_http_connection.query("SELECT * FROM user;").first(),
    )
    check_no_change(rows[0], record_id)
    await async_http_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_update_string_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id: RecordID,
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    first_outcome = await async_http_connection.update("user:tobie", update_data)
    check_change(cast(dict[str, Any], first_outcome), record_id)
    rows = cast(
        list[dict[str, Any]],
        await async_http_connection.query("SELECT * FROM user;").first(),
    )
    check_change(rows[0], record_id)
    await async_http_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_update_record_id(
    async_http_connection: AsyncHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id: RecordID,
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    first_outcome = await async_http_connection.update(record_id)
    check_no_change(first_outcome, record_id)
    rows = cast(
        list[dict[str, Any]],
        await async_http_connection.query("SELECT * FROM user;").first(),
    )
    check_no_change(rows[0], record_id)
    await async_http_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_update_record_id_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id: RecordID,
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    outcome = await async_http_connection.update(record_id, update_data)
    check_change(outcome, record_id)
    rows = cast(
        list[dict[str, Any]],
        await async_http_connection.query("SELECT * FROM user;").first(),
    )
    check_change(rows[0], record_id)
    await async_http_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_update_table(
    async_http_connection: AsyncHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id: RecordID,
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    table = Table("user")
    first_outcome = await async_http_connection.update(table)
    check_no_change(cast(dict[str, Any], first_outcome[0]), record_id)
    rows = cast(
        list[dict[str, Any]],
        await async_http_connection.query("SELECT * FROM user;").first(),
    )
    check_no_change(rows[0], record_id)
    await async_http_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_update_table_with_data(
    async_http_connection: AsyncHttpSurrealConnection,
    update_data: dict[str, Any],
    record_id: RecordID,
) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )

    table = Table("user")
    outcome = await async_http_connection.update(table, update_data)
    check_change(cast(dict[str, Any], outcome[0]), record_id)
    rows = cast(
        list[dict[str, Any]],
        await async_http_connection.query("SELECT * FROM user;").first(),
    )
    check_change(rows[0], record_id)
    await async_http_connection.query("DELETE user;")
