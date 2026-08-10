from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _require_surrealdb_server() -> Generator[None, None, None]:
    """Override the parent fixture: these tests need no SurrealDB.

    The lifecycle tests in this package exercise session handling against a
    throwaway local HTTP server (or a stubbed transport) and therefore never
    touch a real SurrealDB server, so the server-reachability skip must not
    apply here.
    """
    yield
