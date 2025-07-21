import pytest


@pytest.mark.asyncio
async def test_version(async_http_connection):
    assert str == type(await async_http_connection.version())
