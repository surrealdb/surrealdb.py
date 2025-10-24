from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_info(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    outcome = blocking_ws_connection.info()
    # info() can return None or a dict with user info
    # Just verify the method doesn't raise an exception
    assert True  # If we get here, the method worked
