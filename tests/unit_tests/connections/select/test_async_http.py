import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.mark.asyncio
async def test_select(async_http_connection: AsyncHttpSurrealConnection) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query("DELETE users;")

    # Create users with required fields
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )
    await async_http_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', enabled = true, password = 'root';"
    )

    await async_http_connection.query("CREATE users:one SET name = 'one';")
    await async_http_connection.query("CREATE users:two SET name = 'two';")

    outcome = await async_http_connection.select("user")
    assert outcome[0]["name"] == "Jaime"
    assert outcome[1]["name"] == "Tobie"
    assert 2 == len(outcome)

    await async_http_connection.query("DELETE user;")
    await async_http_connection.query("DELETE users;")


@pytest.mark.asyncio
async def test_select_record_id_present(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query("DELETE user;").execute()
    await async_http_connection.query("CREATE user:tobie SET name = 'Tobie';").execute()

    outcome = await async_http_connection.select(RecordID("user", "tobie"))
    assert isinstance(outcome, dict)
    assert outcome["name"] == "Tobie"

    await async_http_connection.query("DELETE user;").execute()


@pytest.mark.asyncio
async def test_select_record_id_absent(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query("DELETE user;").execute()

    outcome = await async_http_connection.select(RecordID("user", "missing"))
    assert outcome is None


@pytest.mark.asyncio
async def test_select_string_record_id_present(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query("DELETE user;").execute()
    await async_http_connection.query("CREATE user:tobie SET name = 'Tobie';").execute()

    outcome = await async_http_connection.select("user:tobie")
    assert isinstance(outcome, dict)
    assert outcome["name"] == "Tobie"

    await async_http_connection.query("DELETE user;").execute()


@pytest.mark.asyncio
async def test_select_table_returns_list(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query("DELETE user;").execute()
    await async_http_connection.query("CREATE user:tobie SET name = 'Tobie';").execute()
    await async_http_connection.query("CREATE user:jaime SET name = 'Jaime';").execute()

    outcome = await async_http_connection.select(Table("user"))
    assert isinstance(outcome, list)
    assert len(outcome) == 2

    await async_http_connection.query("DELETE user;").execute()
