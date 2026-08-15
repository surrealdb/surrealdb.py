from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection


def test_version(blocking_http_connection: BlockingHttpSurrealConnection) -> None:
    assert isinstance(blocking_http_connection.version(), str)
