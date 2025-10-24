import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID


@pytest.mark.asyncio
async def test_query(async_http_connection: AsyncHttpSurrealConnection) -> None:
    await async_http_connection.query("DELETE user;")
    result = await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    assert result == [
        {
            "id": RecordID(table_name="user", identifier="tobie"),
            "name": "Tobie",
            "email": "tobie@example.com",
            "password": "password123",
            "enabled": True,
        }
    ]

    result = await async_http_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password456', enabled = true;"
    )
    assert result == [
        {
            "id": RecordID(table_name="user", identifier="jaime"),
            "name": "Jaime",
            "email": "jaime@example.com",
            "password": "password456",
            "enabled": True,
        }
    ]

    result = await async_http_connection.query("SELECT * FROM user;")
    assert result == [
        {
            "id": RecordID(table_name="user", identifier="jaime"),
            "name": "Jaime",
            "email": "jaime@example.com",
            "password": "password456",
            "enabled": True,
        },
        {
            "id": RecordID(table_name="user", identifier="tobie"),
            "name": "Tobie",
            "email": "tobie@example.com",
            "password": "password123",
            "enabled": True,
        },
    ]
    await async_http_connection.query("DELETE user;")
