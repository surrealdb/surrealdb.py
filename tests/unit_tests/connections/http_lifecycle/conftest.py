from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _require_surrealdb_server() -> Generator[None, None, None]:
    """Override the parent fixture: these tests are fully mocked.

    The lifecycle tests in this package stub out the HTTP transport with
    ``aioresponses``/``responses`` and therefore never touch a real
    SurrealDB server, so the server-reachability skip must not apply here.
    """
    yield
