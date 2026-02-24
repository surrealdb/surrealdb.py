"""
Fixtures for structured server error tests (SurrealDB >= 3.0.0 only).

These tests require a running SurrealDB 3.x instance.
They are skipped when the server is unreachable or version is < 3.0.0.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def _is_surrealdb_v3_or_later(version_str: str) -> bool:
    version_str = (version_str or "").strip().lower()
    if not version_str:
        return False
    for prefix in ("surrealdb-", "v"):
        if version_str.startswith(prefix):
            version_str = version_str[len(prefix) :]
    try:
        major = int(version_str.split(".")[0])
        return major >= 3
    except (ValueError, IndexError):
        return False


@pytest.fixture(scope="module")
def v3_ws() -> Generator[dict[str, Any], None, None]:
    """Root-authenticated WS connection, skipped if server is not >= 3.0.0."""
    url = "ws://localhost:8000"
    namespace = "test_structured_errors_ns"
    database = "test_structured_errors_db"
    conn = BlockingWsSurrealConnection(url)
    try:
        try:
            conn.signin({"username": "root", "password": "root"})
        except (OSError, ConnectionError) as exc:
            pytest.skip(f"Requires a running SurrealDB server at {url}: {exc}")
        conn.use(namespace=namespace, database=database)
        version = conn.version()
        if not _is_surrealdb_v3_or_later(version):
            pytest.skip(
                f"Structured error tests require SurrealDB >= 3.0.0 (got {version})"
            )
        yield {"url": url, "namespace": namespace, "database": database, "conn": conn}
    finally:
        if conn.socket:
            conn.socket.close()


@pytest.fixture()
def conn(v3_ws: dict[str, Any]) -> BlockingWsSurrealConnection:
    """Fresh connection for each test (reuses the module-scoped session)."""
    return v3_ws["conn"]
