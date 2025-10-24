import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


async def test_authenticate(async_ws_connection: AsyncWsSurrealConnection) -> None:
    outcome = await async_ws_connection.authenticate(token=async_ws_connection.token)
