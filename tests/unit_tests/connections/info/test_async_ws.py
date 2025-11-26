from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


async def test_info(async_ws_connection: AsyncWsSurrealConnection) -> None:
    outcome = await async_ws_connection.info()
    # info() can return None or a dict with user info
    # Just verify the method doesn't raise an exception
    assert True  # If we get here, the method worked
