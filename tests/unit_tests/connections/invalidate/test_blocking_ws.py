import os
from collections.abc import Iterator
from typing import cast

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.types import Value


@pytest.fixture
def main_connection() -> Iterator[BlockingWsSurrealConnection]:
    """Create a separate connection for the main connection that creates the test data"""
    url = "ws://localhost:8000"
    password = "root"
    username = "root"
    vars_params: dict[str, Value] = {
        "username": username,
        "password": password,
    }
    database_name = "test_db"
    namespace = "test_ns"
    connection = BlockingWsSurrealConnection(url)
    connection.signin(vars_params)
    connection.use(namespace=namespace, database=database_name)
    connection.query("DEFINE TABLE IF NOT EXISTS user SCHEMALESS;").execute()
    connection.query("DELETE user;").execute()
    connection.query_raw(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password123', enabled = true;"
    )
    yield connection
    connection.query("DELETE user;").execute()
    connection.close()


def test_invalidate_with_guest_mode_on(
    main_connection: BlockingWsSurrealConnection,
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    outcome = blocking_ws_connection.query("SELECT * FROM user;").first()
    assert len(cast(list, outcome)) == 1
    outcome = main_connection.query("SELECT * FROM user;").first()
    assert len(cast(list, outcome)) == 1

    blocking_ws_connection.invalidate()

    try:
        outcome = blocking_ws_connection.query("SELECT * FROM user;").first()
        assert len(cast(list, outcome)) == 0
    except Exception as err:
        assert "Not enough permissions" in str(
            err
        ) or "Anonymous access not allowed" in str(err)
    outcome = main_connection.query("SELECT * FROM user;").first()
    assert len(cast(list, outcome)) == 1


def test_invalidate_test_for_no_guest_mode(
    main_connection: BlockingWsSurrealConnection,
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    outcome = blocking_ws_connection.query("SELECT * FROM user;").first()
    assert len(cast(list, outcome)) == 1
    outcome = main_connection.query("SELECT * FROM user;").first()
    assert len(cast(list, outcome)) == 1

    blocking_ws_connection.invalidate()

    # Try to query after invalidation - behavior depends on guest mode setting
    try:
        outcome = blocking_ws_connection.query("SELECT * FROM user;").first()
        # If guest mode is enabled, we get empty results instead of an exception
        assert len(cast(list, outcome)) == 0
    except Exception as err:
        # If guest mode is disabled, we get an exception
        assert "Not enough permissions" in str(
            err
        ) or "Anonymous access not allowed" in str(err)

    outcome = main_connection.query("SELECT * FROM user;").first()
    assert len(cast(list, outcome)) == 1
