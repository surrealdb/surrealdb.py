import asyncio
from asyncio import TimeoutError
from uuid import UUID

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import RecordID


async def test_live_subscription(
    async_ws_connection_with_user: AsyncWsSurrealConnection,
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
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


async def test_live_subscription_via_query(
    async_ws_connection_with_user, async_ws_connection: AsyncWsSurrealConnection
) -> None:
    # Start the live query using query() method
    query_uuid = await async_ws_connection_with_user.query("LIVE SELECT * FROM user;")
    assert isinstance(query_uuid, UUID)

    # Start the live subscription
    subscription = await async_ws_connection_with_user.subscribe_live(query_uuid)

    # Push an update
    await async_ws_connection.query(
        "CREATE user:john SET name = 'John', email = 'john@example.com', password = 'password123', enabled = true;"
    )

    try:
        update = await asyncio.wait_for(subscription.__anext__(), timeout=10)
        assert update["name"] == "John"
        assert update["id"] == RecordID("user", "john")
    except TimeoutError:
        pytest.fail("Timed out waiting for live subscription update")

    await async_ws_connection.kill(query_uuid)

    # Cleanup the subscription
    await async_ws_connection.query("DELETE user;")
