import socket
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def _server_reachable(host: str = "127.0.0.1", port: int = 8000) -> bool:
    """Best-effort TCP probe so we can skip cleanly when no server is up."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_surrealdb_server() -> None:
    """Skip integration tests when no SurrealDB instance is reachable.

    Connection tests need a running server on ``localhost:8000``. Without
    this fixture, a missing server surfaces as a wall of cryptic
    ``ConnectionRefusedError`` failures inside individual setup paths.
    With it the whole bundle is skipped with a single, actionable
    message.
    """
    if not _server_reachable():
        pytest.skip(
            "No SurrealDB server reachable on 127.0.0.1:8000. Start one with "
            "`surreal start -u root -p root memory --bind 127.0.0.1:8000` "
            "(or via docker-compose) to run these integration tests.",
            allow_module_level=True,
        )


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


_DEFINE_TABLES = """
    DEFINE TABLE IF NOT EXISTS user SCHEMALESS;
    DEFINE TABLE IF NOT EXISTS users SCHEMALESS;
    DEFINE TABLE IF NOT EXISTS person SCHEMALESS;
    DEFINE TABLE IF NOT EXISTS likes SCHEMALESS;
    DEFINE TABLE IF NOT EXISTS document SCHEMALESS;
"""


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
    await connection.query(_DEFINE_TABLES)
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
        await connection.query(_DEFINE_TABLES)
        yield connection
    finally:
        # Ensure connection is always closed
        try:
            await connection.close()
        except Exception:
            # Ignore any exceptions during cleanup
            pass


@pytest.fixture
async def async_ws_connection_secondary(
    connection_params: dict[str, Any],
) -> AsyncGenerator[AsyncWsSurrealConnection, None]:
    """Second independent async WebSocket (same auth/ns/db). Use when a test needs two sockets."""
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    try:
        await connection.signin(connection_params["vars_params"])
        await connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        await connection.query(_DEFINE_TABLES)
        yield connection
    finally:
        try:
            await connection.close()
        except Exception:
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
    connection.query(_DEFINE_TABLES).execute()
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
    connection.query(_DEFINE_TABLES).execute()
    yield connection
    if connection.socket:
        connection.socket.close()


@pytest.fixture
def blocking_ws_connection_secondary(
    connection_params: dict[str, Any],
) -> Generator[BlockingWsSurrealConnection, None, None]:
    """Second independent blocking WebSocket (same auth/ns/db). Use when a test needs two sockets."""
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    connection.signin(connection_params["vars_params"])
    connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    connection.query(_DEFINE_TABLES).execute()
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
    blocking_http_connection.query("DELETE user;").execute()
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    ).execute()
    yield blocking_http_connection


@pytest.fixture
def blocking_ws_connection_with_user(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[BlockingWsSurrealConnection, None, None]:
    """Blocking WebSocket connection with a test user created"""
    blocking_ws_connection.query("DELETE user;").execute()
    blocking_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    ).execute()
    yield blocking_ws_connection
