"""A record access method that issues refresh tokens, for the token tests."""

import uuid
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.features import Features

ACCESS = "tok_acc"

_DEFINE_ACCESS = f"""
    DEFINE TABLE IF NOT EXISTS tok_user SCHEMALESS;
    DEFINE ACCESS OVERWRITE {ACCESS} ON DATABASE TYPE RECORD
        SIGNUP (CREATE tok_user SET name = $name)
        SIGNIN (SELECT * FROM tok_user WHERE name = $name)
        WITH REFRESH
        DURATION FOR TOKEN 1h, FOR SESSION 1h;
"""


@pytest.fixture
def needs_v3(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    if not blocking_ws_connection.is_feature_supported(Features.REFRESH_TOKENS):
        pytest.skip("refresh tokens and sessions need SurrealDB 3.0 or later")


@pytest.fixture
def record_user(
    needs_v3: None,
    blocking_ws_connection: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
) -> dict[str, Any]:
    """Signup parameters for a new record user of an access WITH REFRESH."""
    blocking_ws_connection.query(_DEFINE_ACCESS).execute()
    return {
        "namespace": connection_params["namespace"],
        "database": connection_params["database_name"],
        "access": ACCESS,
        "variables": {"name": f"user-{uuid.uuid4().hex[:8]}"},
    }
