import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection


def test_version(blocking_http_connection: BlockingHttpSurrealConnection) -> None:
    assert str == type(blocking_http_connection.version())
