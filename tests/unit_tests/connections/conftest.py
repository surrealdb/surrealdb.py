import asyncio
import contextlib
import os
import socket
import time
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import QueryError

# Where the integration server is. Defaults to the port `docker-compose up`
# publishes, and honours the same `SURREALDB_PORT` the compose file reads, so a
# second server on another port - a newer build, a version being compared
# against - can be targeted without editing this file.
#
# The two host defaults differ deliberately, and both are the original
# literals: the URLs say `localhost` because a test re-points a connection by
# rewriting exactly that substring, while the reachability probe dials
# `127.0.0.1` so it does not depend on name resolution.
#
# KNOWN LIMITATION. This reaches the tests that take a connection *fixture*,
# which is nearly all of them. Eighteen files under this directory build their
# own connection from a hardcoded `localhost:8000` instead - `signin/`,
# `signup/`, `invalidate/`, `http_lifecycle/`, `transport_errors/` and
# `session_unsupported/` among them. Pointed at another port, those keep
# talking to 8000 while their fixtures define schema on the port you asked
# for, and they fail in ways that look like server bugs: `signup` returns a
# record whose `info()` is None, because the access method was defined
# somewhere else. Eleven tests behave that way today. They are not evidence of
# anything about the server under test - re-run them without SURREALDB_PORT to
# confirm - and making them honour this is tracked separately.
SERVER_HOST = os.environ.get("SURREALDB_HOST", "localhost")
PROBE_HOST = os.environ.get("SURREALDB_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SURREALDB_PORT", "8000"))


def _server_reachable(host: str = PROBE_HOST, port: int = SERVER_PORT) -> bool:
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
            f"No SurrealDB server reachable on {PROBE_HOST}:{SERVER_PORT}. Start "
            "one with `surreal start -u root -p root memory --bind "
            f"{PROBE_HOST}:{SERVER_PORT}` (or via docker-compose) to run these "
            "integration tests.",
            allow_module_level=True,
        )


@pytest.fixture
def connection_params() -> dict[str, Any]:
    """Shared connection parameters for all tests"""
    return {
        "url": f"http://{SERVER_HOST}:{SERVER_PORT}",
        "ws_url": f"ws://{SERVER_HOST}:{SERVER_PORT}",
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

# The DDL above is retried on a write conflict, which the server explicitly
# invites: "Transaction conflict: Write conflict, retry the transaction. This
# transaction can be retried."
#
# Why it conflicts at all, measured rather than assumed. `DEFINE TABLE IF NOT
# EXISTS` against a table that already exists is effectively read-only and never
# collides - zero conflicts in 200 concurrent attempts. What collides is the
# case where the table is genuinely missing and has to be written back, and that
# case is common here: seventeen tests do `REMOVE TABLE user` and two
# `REMOVE TABLE person`, both of which this DDL defines. Two of those rewrites
# overlapping produced roughly one `ERROR at setup of <test>` per full-suite
# run, on whichever test happened to be next.
#
# Defining the tables once per session would be cheaper, and is wrong for the
# same reason: those removals mean the tables are *not* stable for the length of
# a session, so every connection really does have to ensure them. What is safe
# to remove is the failure, not the work.
_DDL_ATTEMPTS = 5
_DDL_RETRY_DELAY = 0.05


def _is_write_conflict(error: BaseException) -> bool:
    """Whether *error* is the conflict the server says may be retried.

    Matched on the structured detail the SDK already exposes rather than on the
    message text, so a reworded server error cannot silently turn the retry off.
    """
    return isinstance(error, QueryError) and error.is_transaction_conflict


def _define_tables(
    connection: BlockingHttpSurrealConnection | BlockingWsSurrealConnection,
) -> None:
    """Ensure the shared tables exist, retrying a write conflict."""
    for attempt in range(_DDL_ATTEMPTS):
        try:
            connection.query(_DEFINE_TABLES).execute()
            return
        except QueryError as error:
            if not _is_write_conflict(error) or attempt == _DDL_ATTEMPTS - 1:
                raise
            time.sleep(_DDL_RETRY_DELAY * (attempt + 1))


async def _adefine_tables(
    connection: AsyncHttpSurrealConnection | AsyncWsSurrealConnection,
) -> None:
    """The async counterpart of :func:`_define_tables`."""
    for attempt in range(_DDL_ATTEMPTS):
        try:
            await connection.query(_DEFINE_TABLES)
            return
        except QueryError as error:
            if not _is_write_conflict(error) or attempt == _DDL_ATTEMPTS - 1:
                raise
            await asyncio.sleep(_DDL_RETRY_DELAY * (attempt + 1))


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
    await _adefine_tables(connection)
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
        await _adefine_tables(connection)
        yield connection
    finally:
        # Ensure connection is always closed; ignore cleanup failures
        with contextlib.suppress(Exception):
            await connection.close()


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
        await _adefine_tables(connection)
        yield connection
    finally:
        with contextlib.suppress(Exception):
            await connection.close()


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
    _define_tables(connection)
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
    _define_tables(connection)
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
    _define_tables(connection)
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
