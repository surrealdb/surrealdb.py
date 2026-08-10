from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _require_surrealdb_server() -> Generator[None, None, None]:
    """Override the parent fixture: these tests need no SurrealDB server.

    The transport-error tests stub the blocking HTTP transport with
    ``responses``, point the async HTTP transport at a throwaway local
    ``aiohttp`` test server, and point the websocket transports at a closed
    port, so they never touch a real SurrealDB server.
    """
    yield
