"""
Bearer access method tests for TYPE BEARER FOR USER (SurrealDB 3.x only).

Mirrors behavior documented in surrealdb.go contrib/testenv:
- Bearer access for system users: DEFINE USER, DEFINE ACCESS TYPE BEARER FOR USER,
  GRANT, then signin with key. In v3 bearer access is enabled by default.
- SignIn with bearer key returns a JWT (Tokens with access set).
- Authenticate does NOT work with bearer-obtained JWT tokens (server limitation).
"""

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.types import Tokens


def test_bearer_access_system_user(bearer_v3_root_ws: dict) -> None:
    """
    TYPE BEARER FOR USER: define user, define bearer access, grant, signin with key.
    """
    root = bearer_v3_root_ws["connection"]
    url = bearer_v3_root_ws["url"]
    namespace = bearer_v3_root_ws["namespace"]
    database_name = bearer_v3_root_ws["database_name"]

    root.query("DEFINE USER testuser ON DATABASE PASSWORD 'testpass' ROLES EDITOR")
    root.query("DEFINE ACCESS bearer_api ON DATABASE TYPE BEARER FOR USER")

    grant_result = root.query("ACCESS bearer_api GRANT FOR USER testuser")
    assert grant_result is not None
    assert isinstance(grant_result, dict)
    grant_info = grant_result.get("grant")
    assert grant_info is not None
    assert isinstance(grant_info, dict)
    bearer_key = grant_info.get("key")
    assert bearer_key is not None
    assert isinstance(bearer_key, str)
    assert bearer_key.startswith("surreal-bearer-")

    conn = BlockingWsSurrealConnection(url)
    try:
        tokens = conn.signin(
            {
                "namespace": namespace,
                "database": database_name,
                "access": "bearer_api",
                "key": bearer_key,
            }
        )
        assert isinstance(tokens, Tokens)
        assert tokens.access is not None
        assert tokens.access != ""

        result = conn.query("RETURN 1")
        assert result == 1
    finally:
        if conn.socket:
            conn.socket.close()


def test_bearer_signin_token_not_usable_with_authenticate(
    bearer_v3_root_ws: dict,
) -> None:
    """
    Authenticate does NOT work with bearer-obtained JWT (server behavior).
    Bearer keys are for SignIn only.
    """
    root = bearer_v3_root_ws["connection"]
    url = bearer_v3_root_ws["url"]
    namespace = bearer_v3_root_ws["namespace"]
    database_name = bearer_v3_root_ws["database_name"]

    root.query("DEFINE USER auth_testuser ON DATABASE PASSWORD 'testpass' ROLES EDITOR")
    root.query("DEFINE ACCESS bearer_auth_test ON DATABASE TYPE BEARER FOR USER")
    grant_result = root.query("ACCESS bearer_auth_test GRANT FOR USER auth_testuser")
    bearer_key = grant_result["grant"]["key"]

    conn = BlockingWsSurrealConnection(url)
    try:
        tokens = conn.signin(
            {
                "namespace": namespace,
                "database": database_name,
                "access": "bearer_auth_test",
                "key": bearer_key,
            }
        )
        assert tokens.access is not None

        conn2 = BlockingWsSurrealConnection(url)
        try:
            conn2.use(namespace=namespace, database=database_name)
            with pytest.raises(Exception):
                conn2.authenticate(tokens.access)
        finally:
            if conn2.socket:
                conn2.socket.close()
    finally:
        if conn.socket:
            conn.socket.close()
