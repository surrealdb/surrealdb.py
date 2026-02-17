"""
Fixtures for bearer access tests (SurrealDB 3.x only).

These tests require a running SurrealDB 3.x instance (e.g. start with
SURREALDB_VERSION=v3.0.0-beta.2 or use docker-compose profile v3).
They are skipped when the server version is not 3.x.
"""

from typing import Any

import pytest

pytestmark = pytest.mark.surrealdb_v3

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def _is_surrealdb_v3(version_str: str) -> bool:
    version_str = (version_str or "").strip().lower()
    if not version_str:
        return False
    if version_str.startswith(("3.", "v3.")):
        return True
    if "surrealdb-3." in version_str:
        return True
    return False


@pytest.fixture(scope="module")
def bearer_v3_root_ws() -> dict[str, Any]:
    """
    Root-authenticated WebSocket connection and version check.

    Skips all bearer_v3 tests when no server is reachable or version is not 3.x.
    Yields url, namespace, database_name, and the root connection for setup.
    """
    url = "ws://localhost:8000"
    namespace = "test_ns"
    database_name = "test_db"
    connection = BlockingWsSurrealConnection(url)
    try:
        try:
            connection.signin({"username": "root", "password": "root"})
        except (OSError, ConnectionError) as e:
            pytest.skip(
                f"Bearer access tests require a running SurrealDB server at {url}: {e}. "
                "Start with SURREALDB_VERSION=v3.0.0-beta.2 or use docker-compose profile v3."
            )
        connection.use(namespace=namespace, database=database_name)
        version = connection.version()
        if not _is_surrealdb_v3(version):
            pytest.skip(
                f"Bearer access tests require SurrealDB 3.x (server version: {version}). "
                "Start with SURREALDB_VERSION=v3.0.0-beta.2 or use docker-compose profile v3."
            )
        yield {
            "url": url,
            "namespace": namespace,
            "database_name": database_name,
            "connection": connection,
        }
    finally:
        if connection.socket:
            connection.socket.close()
