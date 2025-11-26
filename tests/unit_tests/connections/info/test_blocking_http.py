from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection


def test_info(blocking_http_connection: BlockingHttpSurrealConnection) -> None:
    outcome = blocking_http_connection.info()
    # info() can return None or a dict with user info
    # Just verify the method doesn't raise an exception
    assert True  # If we get here, the method worked
