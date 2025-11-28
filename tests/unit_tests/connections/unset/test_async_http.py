import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


@pytest.mark.asyncio
async def test_unset(async_http_connection: AsyncHttpSurrealConnection) -> None:
    await async_http_connection.query("DELETE person;")
    outcome = await async_http_connection.let(
        "name",
        {
            "first": "Tobie",
            "last": "Morgan Hitchcock",
        },
    )
    assert outcome is None
    await async_http_connection.query("CREATE person SET name = $name")
    outcome = await async_http_connection.query(
        "SELECT * FROM person WHERE name.first = $name.first"
    )
    assert len(outcome) == 1
    assert outcome[0]["name"] == {"first": "Tobie", "last": "Morgan Hitchcock"}

    await async_http_connection.unset(key="name")

    # because the key was unset then $name.first is None returning []
    outcome = await async_http_connection.query(
        "SELECT * FROM person WHERE name.first = $name.first"
    )
    assert outcome == []

    await async_http_connection.query("DELETE person;")
