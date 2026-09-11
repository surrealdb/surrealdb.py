import os
import socket

import pytest

# Where the server is, honouring the same variables `connections/conftest.py`
# reads so the whole suite can be pointed at one place. Duplicated rather than
# shared because pytest gives one conftest no import path to another, and these
# two directories have no common parent conftest.
SERVER_HOST = os.environ.get("SURREALDB_HOST", "localhost")
PROBE_HOST = os.environ.get("SURREALDB_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SURREALDB_PORT", "8000"))


@pytest.fixture(scope="session")
def ws_url() -> str:
    """The websocket URL the round-trip fixtures in this directory connect to."""
    return f"ws://{SERVER_HOST}:{SERVER_PORT}/rpc"


def _server_reachable(host: str = PROBE_HOST, port: int = SERVER_PORT) -> bool:
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
    server. Without this gate a missing server
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
            f"No SurrealDB server reachable on {PROBE_HOST}:{SERVER_PORT}. Start "
            "one with `surreal start -u root -p root memory --bind "
            f"{PROBE_HOST}:{SERVER_PORT}` "
            "(or via docker-compose) to run these DB round-trip tests."
        )
