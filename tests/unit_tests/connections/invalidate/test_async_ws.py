import os

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


@pytest.fixture
async def main_connection():
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
    connection = AsyncWsSurrealConnection(url)
    await connection.signin(vars_params)
    await connection.use(namespace=namespace, database=database_name)
    await connection.query("DELETE user;")
    await connection.query_raw(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password123', enabled = true;"
    )
    yield connection
    await connection.query("DELETE user;")
    await connection.close()


@pytest.mark.asyncio
async def test_invalidate_with_guest_mode_on(main_connection, async_ws_connection):
    outcome = await async_ws_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    await async_ws_connection.invalidate()

    try:
        outcome = await async_ws_connection.query("SELECT * FROM user;")
        assert len(outcome) == 0
    except Exception as err:
        assert "IAM error: Not enough permissions" in str(err)
    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1


@pytest.mark.asyncio
async def test_invalidate_test_for_no_guest_mode(main_connection, async_ws_connection):
    outcome = await async_ws_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    await async_ws_connection.invalidate()

    # Try to query after invalidation - behavior depends on guest mode setting
    try:
        outcome = await async_ws_connection.query("SELECT * FROM user;")
        # If guest mode is enabled, we get empty results instead of an exception
        assert len(outcome) == 0
    except Exception as err:
        # If guest mode is disabled, we get an exception
        assert "IAM error: Not enough permissions" in str(err)

    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
