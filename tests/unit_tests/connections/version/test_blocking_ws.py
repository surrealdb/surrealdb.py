import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_version(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    assert str == type(blocking_ws_connection.version())
