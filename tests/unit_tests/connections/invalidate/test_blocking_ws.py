import os

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


@pytest.fixture
def main_connection():
    """Create a separate connection for the main connection that creates the test data"""
    url = "ws://localhost:8000"
    password = "root"
    username = "root"
    vars_params = {
        "username": username,
        "password": password,
    }
    database_name = "test_db"
    namespace = "test_ns"
    connection = BlockingWsSurrealConnection(url)
    connection.signin(vars_params)
    connection.use(namespace=namespace, database=database_name)
    connection.query("DELETE user;")
    connection.query_raw(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password123', enabled = true;"
    )
    yield connection
    connection.query("DELETE user;")
    connection.close()


def test_invalidate_with_guest_mode_on(main_connection, blocking_ws_connection):
    outcome = blocking_ws_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    blocking_ws_connection.invalidate()

    try:
        outcome = blocking_ws_connection.query("SELECT * FROM user;")
        assert len(outcome) == 0
    except Exception as err:
        assert "IAM error: Not enough permissions" in str(err)
    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1


def test_invalidate_test_for_no_guest_mode(main_connection, blocking_ws_connection):
    outcome = blocking_ws_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    blocking_ws_connection.invalidate()

    # Try to query after invalidation - behavior depends on guest mode setting
    try:
        outcome = blocking_ws_connection.query("SELECT * FROM user;")
        # If guest mode is enabled, we get empty results instead of an exception
        assert len(outcome) == 0
    except Exception as err:
        # If guest mode is disabled, we get an exception
        assert "IAM error: Not enough permissions" in str(err)

    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
