import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


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
