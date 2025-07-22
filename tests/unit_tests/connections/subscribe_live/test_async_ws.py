import asyncio
from asyncio import TimeoutError
from uuid import UUID

import pytest

from surrealdb.data import RecordID


async def test_live_subscription(async_ws_connection_with_user, async_ws_connection):
    # Start the live query
    query_uuid = await async_ws_connection_with_user.live("user")
    assert isinstance(query_uuid, UUID)

    # Start the live subscription
    subscription = await async_ws_connection_with_user.subscribe_live(query_uuid)

    # Push an update
    await async_ws_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password456', enabled = true;"
    )

    try:
        update = await asyncio.wait_for(subscription.__anext__(), timeout=10)
        assert update["name"] == "Jaime"
        assert update["id"] == RecordID("user", "jaime")
    except TimeoutError:
        pytest.fail("Timed out waiting for live subscription update")

    await async_ws_connection.kill(query_uuid)

    # Cleanup the subscription
    await async_ws_connection.query("DELETE user;")
