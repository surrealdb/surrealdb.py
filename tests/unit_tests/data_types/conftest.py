import socket

import pytest


def _server_reachable(host: str = "127.0.0.1", port: int = 8000) -> bool:
    """Best-effort TCP probe so we can skip cleanly when no server is up."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(autouse=True)
def _require_surrealdb_server(request: pytest.FixtureRequest) -> None:
    """Skip DB round-trip data-type tests when no SurrealDB is reachable.

    The round-trip tests in this suite request the locally defined
    ``surrealdb_connection`` fixture, which opens a real connection to a
    server on ``localhost:8000``. Without this gate a missing server
    surfaces as a wall of cryptic ``ConnectionRefusedError`` failures
    (reported as ERROR) inside each connection fixture. With it those
    tests are skipped with a single, actionable message.

    The pure encode/decode and value-type unit tests in the same files do
    not request ``surrealdb_connection``, so they keep running serverless.
    """
    if "surrealdb_connection" not in request.fixturenames:
        return
    if not _server_reachable():
        pytest.skip(
            "No SurrealDB server reachable on 127.0.0.1:8000. Start one with "
            "`surreal start -u root -p root memory --bind 127.0.0.1:8000` "
            "(or via docker-compose) to run these DB round-trip tests."
        )
