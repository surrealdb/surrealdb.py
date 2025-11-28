from uuid import UUID

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_query(blocking_ws_connection_with_user: BlockingWsSurrealConnection) -> None:
    outcome = blocking_ws_connection_with_user.live("user")
    assert isinstance(outcome, UUID)
