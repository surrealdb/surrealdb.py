from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


@pytest.fixture
def connection_params() -> dict[str, Any]:
    """Shared connection parameters for all tests"""
    return {
        "url": "http://localhost:8000",
        "ws_url": "ws://localhost:8000",
        "password": "root",
        "username": "root",
        "vars_params": {
            "username": "root",
            "password": "root",
        },
        "database_name": "test_db",
        "namespace": "test_ns",
    }


@pytest.fixture
async def async_http_connection(
    connection_params: dict[str, Any],
) -> AsyncGenerator[AsyncHttpSurrealConnection, None]:
    """Async HTTP connection fixture"""
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    yield connection


@pytest.fixture
async def async_ws_connection(
    connection_params: dict[str, Any],
) -> AsyncGenerator[AsyncWsSurrealConnection, None]:
    """Async WebSocket connection fixture"""
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    try:
        await connection.signin(connection_params["vars_params"])
        await connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        yield connection
    finally:
        # Ensure connection is always closed
        try:
            await connection.close()
        except Exception:
            # Ignore any exceptions during cleanup
            pass


@pytest.fixture
def blocking_http_connection(
    connection_params: dict[str, Any],
) -> Generator[BlockingHttpSurrealConnection, None, None]:
    """Blocking HTTP connection fixture"""
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    connection.signin(connection_params["vars_params"])
    connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    yield connection


@pytest.fixture
def blocking_ws_connection(
    connection_params: dict[str, Any],
) -> Generator[BlockingWsSurrealConnection, None, None]:
    """Blocking WebSocket connection fixture"""
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    connection.signin(connection_params["vars_params"])
    connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    yield connection
    if connection.socket:
        connection.socket.close()


@pytest.fixture
async def async_http_connection_with_user(
    async_http_connection: AsyncHttpSurrealConnection,
) -> AsyncGenerator[AsyncHttpSurrealConnection, None]:
    """Async HTTP connection with a test user created"""
    await async_http_connection.query("DELETE user;")
    await async_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield async_http_connection


@pytest.fixture
async def async_ws_connection_with_user(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[AsyncWsSurrealConnection, None]:
    """Async WebSocket connection with a test user created"""
    await async_ws_connection.query("DELETE user;")
    await async_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield async_ws_connection


@pytest.fixture
def blocking_http_connection_with_user(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> Generator[BlockingHttpSurrealConnection, None, None]:
    """Blocking HTTP connection with a test user created"""
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield blocking_http_connection


@pytest.fixture
def blocking_ws_connection_with_user(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[BlockingWsSurrealConnection, None, None]:
    """Blocking WebSocket connection with a test user created"""
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    yield blocking_ws_connection
