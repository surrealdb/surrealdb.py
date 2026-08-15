from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_version(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    assert isinstance(blocking_ws_connection.version(), str)
