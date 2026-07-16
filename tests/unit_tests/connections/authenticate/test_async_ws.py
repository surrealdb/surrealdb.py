import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


async def test_authenticate(async_ws_connection: AsyncWsSurrealConnection) -> None:
    await async_ws_connection.authenticate(token=async_ws_connection.token)
