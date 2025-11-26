import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


@pytest.mark.asyncio
async def test_version(async_http_connection: AsyncHttpSurrealConnection) -> None:
    assert str == type(await async_http_connection.version())
