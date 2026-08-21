"""Gating for the file tests, by *capability* rather than by version.

Buckets are an experimental server feature: the same 3.2.3 build has them or not
depending on whether it was started with

    SURREAL_CAPS_ALLOW_EXPERIMENTAL=files

so a version check would be wrong in both directions - it would skip a server
that does support them, and run against one that does not. This asks the server
to define a bucket instead, and skips if it refuses.
"""

from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

BUCKET = "sdk_test_files"

# The probe needs `connection_params`, which is function scoped, so this fixture
# has to be too - but the answer cannot change while the suite runs, so it is
# resolved once and remembered rather than reconnecting for every test.
_SUPPORTED: bool | None = None


def _probe(connection_params: dict[str, Any]) -> bool:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    try:
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        connection.query(
            f'DEFINE BUCKET IF NOT EXISTS {BUCKET} BACKEND "memory"'
        ).execute()
    except Exception:
        return False
    finally:
        connection.close()
    return True


@pytest.fixture(autouse=True)
def _require_file_support(connection_params: dict[str, Any]) -> None:
    global _SUPPORTED
    if _SUPPORTED is None:
        _SUPPORTED = _probe(connection_params)
    if not _SUPPORTED:
        pytest.skip(
            "server has no bucket support; start it with "
            "SURREAL_CAPS_ALLOW_EXPERIMENTAL=files"
        )


@pytest.fixture
def bucket(blocking_ws_connection: BlockingWsSurrealConnection) -> str:
    """A bucket that exists, emptied of whatever a previous test left in it."""
    blocking_ws_connection.query(
        f'DEFINE BUCKET IF NOT EXISTS {BUCKET} BACKEND "memory"'
    ).execute()
    for entry in blocking_ws_connection.files.list(BUCKET):
        blocking_ws_connection.files.delete(entry.file)
    return BUCKET
