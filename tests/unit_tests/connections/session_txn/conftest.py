"""
Fixtures for multi-session and client-side transaction tests.

These tests require a running SurrealDB 3.x instance with session and
transaction support (e.g. start with SURREALDB_VERSION=v3.0.0-beta.2 or use
docker-compose profile v3). They are skipped when the server version is not 3.x
or when session-scoped create/query return empty.
"""

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

pytestmark = pytest.mark.surrealdb_v3


def _is_surrealdb_v3(version_str: str) -> bool:
    version_str = (version_str or "").strip().lower()
    if not version_str:
        return False
    if version_str.startswith("3.") or version_str.startswith("v3."):
        return True
    if "surrealdb-3." in version_str:
        return True
    return False


@pytest.fixture(autouse=True)
def session_txn_requires_v3(
    blocking_ws_connection: BlockingWsSurrealConnection,
    connection_params: dict,
) -> None:
    try:
        version = blocking_ws_connection.version()
    except (OSError, ConnectionError) as e:
        pytest.skip(
            f"Session/transaction tests require a running SurrealDB server: {e}. "
            "Start with SURREALDB_VERSION=v3.0.0-beta.2 or use docker-compose profile v3."
        )
    if not _is_surrealdb_v3(version):
        pytest.skip(
            f"Multi-session and client-side transactions require SurrealDB 3.x (server: {version}). "
            "Start with SURREALDB_VERSION=v3.0.0-beta.2 or use docker-compose profile v3."
        )
    session = blocking_ws_connection.new_session()
    session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    try:
        blocking_ws_connection.query("REMOVE TABLE IF EXISTS session_txn_probe;")
        blocking_ws_connection.query("DEFINE TABLE session_txn_probe SCHEMALESS;")
        session.create("session_txn_probe:check", {"probe": True})
        result = session.query("SELECT * FROM session_txn_probe;")
    finally:
        session.close_session()
        blocking_ws_connection.query("REMOVE TABLE IF EXISTS session_txn_probe;")
    if not result or not any(
        r.get("probe") is True for r in result if isinstance(r, dict)
    ):
        pytest.skip(
            "Session-scoped create/query returned empty; ensure SurrealDB 3.x with session support."
        )


@pytest.fixture
def ws_url() -> str:
    return "ws://localhost:8000"


@pytest.fixture
def ns_db() -> tuple[str, str]:
    return ("test_ns", "test_db")
