import pytest


@pytest.fixture(scope="session", autouse=True)
def _require_surrealdb_server() -> None:
    """Embedded tests don't need a SurrealDB server."""
    pass
