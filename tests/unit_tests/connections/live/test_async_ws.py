from uuid import UUID

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


async def test_query(async_ws_connection_with_user: AsyncWsSurrealConnection) -> None:
    outcome = await async_ws_connection_with_user.live("user")
    assert isinstance(outcome, UUID)
    await async_ws_connection_with_user.query("DELETE user;")
