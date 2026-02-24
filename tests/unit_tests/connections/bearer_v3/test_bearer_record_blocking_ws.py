"""
Bearer access method tests for TYPE BEARER FOR RECORD (SurrealDB 3.x only).

Mirrors behavior documented in surrealdb.go contrib/testenv:
- Bearer access for record users: DEFINE TABLE, CREATE record, DEFINE ACCESS
  TYPE BEARER FOR RECORD, GRANT FOR RECORD, then signin with key.
- SignIn with bearer key returns a JWT (Tokens with access set).
- Authenticate does NOT work with bearer-obtained JWT for record users.
"""

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.types import Tokens


def test_bearer_access_record_user(bearer_v3_root_ws: dict) -> None:
    """
    TYPE BEARER FOR RECORD: define table, create record, define bearer access,
    grant for record, signin with key.
    """
    root = bearer_v3_root_ws["connection"]
    url = bearer_v3_root_ws["url"]
    namespace = bearer_v3_root_ws["namespace"]
    database_name = bearer_v3_root_ws["database_name"]

    root.query("DEFINE TABLE IF NOT EXISTS users SCHEMAFULL")
    root.query("DEFINE FIELD IF NOT EXISTS name ON users TYPE string")
    root.query_raw("DELETE users:testrecord")
    root.query("CREATE users:testrecord SET name = 'Test Record User'")
    root.query(
        "DEFINE ACCESS IF NOT EXISTS bearer_record_api ON DATABASE TYPE BEARER FOR RECORD"
    )

    grant_result = root.query(
        "ACCESS bearer_record_api GRANT FOR RECORD users:testrecord"
    )
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
                "access": "bearer_record_api",
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


def test_bearer_record_signin_token_not_usable_with_authenticate(
    bearer_v3_root_ws: dict,
) -> None:
    """
    Authenticate does NOT work with bearer-obtained JWT for record users.
    Bearer keys are for SignIn only.
    """
    root = bearer_v3_root_ws["connection"]
    url = bearer_v3_root_ws["url"]
    namespace = bearer_v3_root_ws["namespace"]
    database_name = bearer_v3_root_ws["database_name"]

    root.query("DEFINE TABLE IF NOT EXISTS auth_records SCHEMAFULL")
    root.query("DEFINE FIELD IF NOT EXISTS name ON auth_records TYPE string")
    root.query_raw("DELETE auth_records:auth_test")
    root.query("CREATE auth_records:auth_test SET name = 'Auth Test Record'")
    root.query(
        "DEFINE ACCESS IF NOT EXISTS bearer_record_auth ON DATABASE TYPE BEARER FOR RECORD"
    )
    grant_result = root.query(
        "ACCESS bearer_record_auth GRANT FOR RECORD auth_records:auth_test"
    )
    bearer_key = grant_result["grant"]["key"]

    conn = BlockingWsSurrealConnection(url)
    try:
        tokens = conn.signin(
            {
                "namespace": namespace,
                "database": database_name,
                "access": "bearer_record_auth",
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
