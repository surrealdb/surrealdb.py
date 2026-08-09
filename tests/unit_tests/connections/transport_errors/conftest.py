from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _require_surrealdb_server() -> Generator[None, None, None]:
    """Override the parent fixture: these tests are fully mocked.

    The transport-error tests stub the HTTP transport with
    ``responses``/``aioresponses`` and point the websocket transports at a
    closed port, so they never touch a real SurrealDB server.
    """
    yield
