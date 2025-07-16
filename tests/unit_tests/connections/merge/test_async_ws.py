import pytest

from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def merge_data():
    return {
        "name": "Jaime",
        "email": "jaime@example.com",
        "password": "password456",
        "enabled": True,
    }


@pytest.fixture(autouse=True)
async def setup_user(async_ws_connection):
    await async_ws_connection.query("DELETE user;")
    await async_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield
    await async_ws_connection.query("DELETE user;")


@pytest.mark.asyncio
async def test_merge_string(async_ws_connection, setup_user):
    record_id = RecordID("user", "tobie")
    outcome = await async_ws_connection.merge("user:tobie")
    assert outcome["id"] == record_id
    assert outcome["name"] == "Tobie"
    result = await async_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"


@pytest.mark.asyncio
async def test_merge_string_with_data(async_ws_connection, merge_data, setup_user):
    record_id = RecordID("user", "tobie")
    first_outcome = await async_ws_connection.merge("user:tobie", merge_data)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Jaime"
    assert first_outcome["email"] == "jaime@example.com"
    assert first_outcome["enabled"] is True
    result = await async_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


@pytest.mark.asyncio
async def test_merge_record_id(async_ws_connection, setup_user):
    record_id = RecordID("user", "tobie")
    first_outcome = await async_ws_connection.merge(record_id)
    assert first_outcome["id"] == record_id
    assert first_outcome["name"] == "Tobie"
    result = await async_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"


@pytest.mark.asyncio
async def test_merge_record_id_with_data(async_ws_connection, merge_data, setup_user):
    record_id = RecordID("user", "tobie")
    outcome = await async_ws_connection.merge(record_id, merge_data)
    assert outcome["id"] == record_id
    assert outcome["name"] == "Jaime"
    assert outcome["email"] == "jaime@example.com"
    assert outcome["enabled"] is True
    result = await async_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True


@pytest.mark.asyncio
async def test_merge_table(async_ws_connection, setup_user):
    table = Table("user")
    record_id = RecordID("user", "tobie")
    first_outcome = await async_ws_connection.merge(table)
    assert first_outcome[0]["id"] == record_id
    assert first_outcome[0]["name"] == "Tobie"
    result = await async_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Tobie"


@pytest.mark.asyncio
async def test_merge_table_with_data(async_ws_connection, merge_data, setup_user):
    table = Table("user")
    record_id = RecordID("user", "tobie")
    outcome = await async_ws_connection.merge(table, merge_data)
    assert outcome[0]["id"] == record_id
    assert outcome[0]["name"] == "Jaime"
    assert outcome[0]["email"] == "jaime@example.com"
    assert outcome[0]["enabled"] is True
    result = await async_ws_connection.query("SELECT * FROM user;")
    assert result[0]["id"] == record_id
    assert result[0]["name"] == "Jaime"
    assert result[0]["email"] == "jaime@example.com"
    assert result[0]["enabled"] is True
