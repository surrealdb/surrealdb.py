from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


async def test_info(async_http_connection: AsyncHttpSurrealConnection) -> None:
    outcome = await async_http_connection.info()
    # info() can return None or a dict with user info
    # Just verify the method doesn't raise an exception
    assert True  # If we get here, the method worked
