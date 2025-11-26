import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


@pytest.mark.asyncio
async def test_version(async_ws_connection: AsyncWsSurrealConnection) -> None:
    assert str == type(await async_ws_connection.version())
