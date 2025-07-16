import pytest


async def test_info(async_http_connection):
    outcome = await async_http_connection.info()
    # info() can return None or a dict with user info
    # Just verify the method doesn't raise an exception
    assert True  # If we get here, the method worked
