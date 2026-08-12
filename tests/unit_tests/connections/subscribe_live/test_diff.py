"""``live(table, diff=True)`` really does deliver JSON Patch.

The flag never reached the wire - ``prep_live`` encoded only the table - so the
server stayed on its default and sent whole records. The call was accepted,
typed and documented the whole time, which is exactly why nothing noticed: the
only observable difference is the *shape* of a notification nobody asserted on.

Asserted through the server rather than against the request bytes alone (that
is covered in ``request_message/descriptors/test_cbor_ws.py``), because the
promise is about what comes back, not about what goes out.
"""

from typing import Any
from uuid import UUID

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def _is_json_patch(result: Any) -> bool:
    """A JSON Patch notification is a list of ``{"op": ..., "path": ...}``."""
    return (
        isinstance(result, list)
        and len(result) > 0
        and all(isinstance(entry, dict) and "op" in entry for entry in result)
    )


def test_blocking_ws_diff_notifications_are_patches(
    blocking_ws_connection_with_user: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    query_uuid = blocking_ws_connection_with_user.live("user", diff=True)
    assert isinstance(query_uuid, UUID)

    subscription = blocking_ws_connection_with_user.subscribe_live(query_uuid)
    blocking_ws_connection_secondary.query(
        "CREATE user:diffie SET name = 'Diffie', enabled = true;"
    ).execute()

    for update in subscription:
        assert _is_json_patch(update["result"]), (
            f"diff=True delivered a whole record, not a patch: {update['result']!r}"
        )
        break
    else:  # pragma: no cover - only on a subscription that ends with nothing
        pytest.fail("no notification arrived")

    blocking_ws_connection_secondary.kill(query_uuid)


def test_blocking_ws_without_diff_notifications_are_records(
    blocking_ws_connection_with_user: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    """The other half of the contract: the default must not change.

    Without this, sending ``diff`` unconditionally could have flipped every
    existing subscriber to patches and this file would still be green.
    """
    query_uuid = blocking_ws_connection_with_user.live("user")

    subscription = blocking_ws_connection_with_user.subscribe_live(query_uuid)
    blocking_ws_connection_secondary.query(
        "CREATE user:wholey SET name = 'Wholey', enabled = true;"
    ).execute()

    for update in subscription:
        assert isinstance(update["result"], dict)
        assert update["result"]["name"] == "Wholey"
        break
    else:  # pragma: no cover
        pytest.fail("no notification arrived")

    blocking_ws_connection_secondary.kill(query_uuid)


async def test_async_ws_diff_notifications_are_patches(
    async_ws_connection: AsyncWsSurrealConnection,
    async_ws_connection_secondary: AsyncWsSurrealConnection,
) -> None:
    query_uuid = await async_ws_connection.live("user", diff=True)

    subscription = await async_ws_connection.subscribe_live(query_uuid)
    await async_ws_connection_secondary.query(
        "CREATE user:asyncdiff SET name = 'AsyncDiff', enabled = true;"
    ).execute()

    async for update in subscription:
        assert _is_json_patch(update["result"]), (
            f"diff=True delivered a whole record, not a patch: {update['result']!r}"
        )
        break
    else:  # pragma: no cover
        pytest.fail("no notification arrived")

    await async_ws_connection_secondary.kill(query_uuid)
