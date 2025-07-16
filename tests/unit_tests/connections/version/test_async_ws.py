import pytest


@pytest.mark.asyncio
async def test_version(async_ws_connection):
    assert str == type(await async_ws_connection.version())
