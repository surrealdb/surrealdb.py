from uuid import UUID

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data import RecordID


def test_live_subscription(
    blocking_ws_connection_with_user: BlockingWsSurrealConnection,
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    # Start the live query
    query_uuid = blocking_ws_connection_with_user.live("user")
    assert isinstance(query_uuid, UUID)

    # Start the live subscription
    subscription = blocking_ws_connection_with_user.subscribe_live(query_uuid)

    # Push an update
    blocking_ws_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password456', enabled = true;"
    )

    # Wait for the live subscription update
    try:
        for update in subscription:
            assert update["name"] == "Jaime"
            assert update["id"] == RecordID("user", "jaime")
            break  # Exit after receiving the first update
    except Exception as e:
        pytest.fail(f"Error waiting for live subscription update: {e}")

    blocking_ws_connection.kill(query_uuid)
