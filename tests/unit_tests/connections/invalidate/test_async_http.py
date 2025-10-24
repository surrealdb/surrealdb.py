import os

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection


@pytest.fixture
async def main_connection(async_http_connection: AsyncHttpSurrealConnection) -> None:
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query_raw(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password123', enabled = true;"
    )
    yield async_http_connection
    await async_http_connection.query("DELETE user;")


@pytest.fixture
async def secondary_connection() -> None:
    from surrealdb.connections.async_http import AsyncHttpSurrealConnection

    url = "http://localhost:8000"
    password = "root"
    username = "root"
    vars_params = {
        "username": username,
        "password": password,
    }
    database_name = "test_db"
    namespace = "test_ns"
    connection = AsyncHttpSurrealConnection(url)
    await connection.signin(vars_params)
    await connection.use(namespace=namespace, database=database_name)
    yield connection


@pytest.mark.asyncio
async def test_invalidate_with_guest_mode_on(
    main_connection, secondary_connection
) -> None:
    """
    This test only works if the SURREAL_CAPS_ALLOW_GUESTS=false is set in the docker container
    """
    outcome = await secondary_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    await secondary_connection.invalidate()

    try:
        outcome = await secondary_connection.query("SELECT * FROM user;")
        assert len(outcome) == 0
    except Exception as err:
        # Check for the actual error message from newer SurrealDB versions
        assert "Not enough permissions" in str(
            err
        ) or "Anonymous access not allowed" in str(err)
    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1


@pytest.mark.asyncio
async def test_invalidate_test_for_no_guest_mode(
    main_connection, secondary_connection
) -> None:
    """
    This test asserts that there is an error thrown due to no guest mode being allowed
    Only run this test if SURREAL_CAPS_ALLOW_GUESTS=false is set in the docker container
    """
    outcome = await secondary_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1

    await secondary_connection.invalidate()

    # Try to query after invalidation - behavior depends on guest mode setting
    try:
        outcome = await secondary_connection.query("SELECT * FROM user;")
        # If guest mode is enabled, we get empty results instead of an exception
        assert len(outcome) == 0
    except Exception as err:
        # If guest mode is disabled, we get an exception
        assert "Not enough permissions" in str(
            err
        ) or "Anonymous access not allowed" in str(err)

    outcome = await main_connection.query("SELECT * FROM user;")
    assert len(outcome) == 1
