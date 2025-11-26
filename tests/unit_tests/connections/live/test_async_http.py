from uuid import UUID

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


@pytest.mark.xfail(reason="live method not implemented for HTTP connections")
async def test_query(
    async_http_connection_with_user: AsyncHttpSurrealConnection,
) -> None:
    outcome = await async_http_connection_with_user.live("user")
    assert isinstance(outcome, UUID)
    await async_http_connection_with_user.query("DELETE user;")
