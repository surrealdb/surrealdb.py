import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID


@pytest.fixture
def insert_bulk_data():
    return [
        {
            "name": "Tobie",
            "email": "tobie@example.com",
            "enabled": True,
            "password": "root",
        },
        {
            "name": "Jaime",
            "email": "jaime@example.com",
            "enabled": True,
            "password": "root",
        },
    ]


@pytest.fixture
def insert_data():
    return [
        {
            "name": "Tobie",
            "email": "tobie@example.com",
            "enabled": True,
            "password": "root",
        },
    ]


@pytest.mark.asyncio
async def test_insert_string_with_data(async_http_connection, insert_bulk_data):
    await async_http_connection.query("DELETE user;")
    outcome = await async_http_connection.insert("user", insert_bulk_data)
    assert 2 == len(outcome)
    assert len(await async_http_connection.query("SELECT * FROM user;")) == 2
    await async_http_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_insert_record_id_result_error(async_http_connection, insert_data):
    await async_http_connection.query("DELETE user;")
    record_id = RecordID("user", "tobie")
    with pytest.raises(Exception) as context:
        _ = await async_http_connection.insert(record_id, insert_data)
    e = str(context.value)
    assert (
        "There was a problem with the database: Can not execute INSERT statement using value"
        in e
        and "user:tobie" in e
    )
    await async_http_connection.query("DELETE user;")
