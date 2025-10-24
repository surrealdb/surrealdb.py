import os

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection


@pytest.fixture
def main_connection() -> None:
    """Create a separate connection for the main connection that creates the test data"""
    url = "http://localhost:8000"
    password = "root"
    username = "root"
    vars_params = {
        "username": username,
        "password": password,
    }
    database_name = "test_db"
    namespace = "test_ns"
    connection = BlockingHttpSurrealConnection(url)
    connection.signin(vars_params)
    connection.use(namespace=namespace, database=database_name)
    connection.query("DELETE user;")
    connection.query_raw(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password123', enabled = true;"
    )
    yield connection
    connection.query("DELETE user;")


def test_invalidate_test_for_no_guest_mode(
    main_connection, blocking_http_connection: BlockingHttpSurrealConnection
) -> None:
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    blocking_http_connection.invalidate()

    try:
        outcome = blocking_http_connection.query("SELECT * FROM user;")
        assert len(outcome) == 0
    except Exception as err:
        assert "Not enough permissions" in str(
            err
        ) or "Anonymous access not allowed" in str(err)
    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1


def test_invalidate_with_guest_mode_on(
    main_connection, blocking_http_connection: BlockingHttpSurrealConnection
) -> None:
    outcome = blocking_http_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    blocking_http_connection.invalidate()

    try:
        outcome = blocking_http_connection.query("SELECT * FROM user;")
        assert len(outcome) == 0
    except Exception as err:
        assert "Not enough permissions" in str(
            err
        ) or "Anonymous access not allowed" in str(err)

    outcome = main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
