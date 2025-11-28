import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


@pytest.mark.asyncio
async def test_let(async_ws_connection: AsyncWsSurrealConnection) -> None:
    await async_ws_connection.query("DELETE person;")
    outcome = await async_ws_connection.let(
        "name",
        {
            "first": "Tobie",
            "last": "Morgan Hitchcock",
        },
    )
    assert outcome is None
    await async_ws_connection.query("CREATE person SET name = $name")
    outcome = await async_ws_connection.query(
        "SELECT * FROM person WHERE name.first = $name.first"
    )
    assert outcome[0]["name"] == {"first": "Tobie", "last": "Morgan Hitchcock"}

    await async_ws_connection.query("DELETE person;")
