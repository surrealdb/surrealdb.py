"""
Integration tests for structured server errors (SurrealDB >= 3.0.0).

Mirrors the JS SDK's ``structured-errors.test.ts`` — each test exercises a
real error path against a live server and verifies that the Python SDK parses
it into the correct ``ServerError`` subclass with the right kind, code,
details, and convenience properties.
"""

from __future__ import annotations

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import (
    AlreadyExistsError,
    NotAllowedError,
    ServerError,
    ThrownError,
    ValidationError,
    parse_query_error,
)


class TestStructuredServerErrors:
    # --------------------------------------------------------- #
    # Invalid credentials -> NotAllowed + Auth details           #
    # --------------------------------------------------------- #

    def test_invalid_credentials(self, v3_ws: dict) -> None:
        url = v3_ws["url"]
        conn = BlockingWsSurrealConnection(url)
        try:
            with pytest.raises(NotAllowedError) as exc_info:
                conn.signin({"username": "invalid", "password": "invalid"})

            err = exc_info.value
            assert isinstance(err, ServerError)
            assert err.kind == "NotAllowed"
            assert err.code == -32002
            assert (
                "authentication" in err.args[0].lower()
                or "problem" in err.args[0].lower()
            )
            assert err.details is not None
            assert err.details["kind"] == "Auth"
            assert err.details["details"]["kind"] == "InvalidAuth"
            assert err.is_invalid_auth is True
            assert err.is_token_expired is False
        finally:
            if conn.socket:
                conn.socket.close()

    # --------------------------------------------------------- #
    # Invalid SurrealQL syntax -> Validation                     #
    # --------------------------------------------------------- #

    def test_invalid_syntax(self, conn: BlockingWsSurrealConnection) -> None:
        with pytest.raises(ServerError) as exc_info:
            conn.query("SEL ECT * FORM person")

        err = exc_info.value
        assert isinstance(err, ValidationError)
        assert err.kind == "Validation"
        assert "Parse error" in str(err) or "Unexpected token" in str(err)

    # --------------------------------------------------------- #
    # Schema violation (type mismatch on field)                  #
    # --------------------------------------------------------- #

    def test_schema_violation(self, conn: BlockingWsSurrealConnection) -> None:
        conn.query("DEFINE TABLE IF NOT EXISTS se_person SCHEMALESS")
        conn.query("DEFINE FIELD IF NOT EXISTS age ON se_person TYPE int")
        conn.query_raw("DELETE se_person:1")

        raw = conn.query_raw('CREATE se_person:1 SET age = "not a number"')
        result = raw["result"][0]

        assert result["status"] == "ERR"
        err = parse_query_error(result)
        assert isinstance(err, ServerError)
        assert err.kind == "Internal"
        assert err.code == 0
        assert (
            "age" in str(err)
            or "coerce" in str(err).lower()
            or "int" in str(err).lower()
        )

    # --------------------------------------------------------- #
    # Non-existent function                                      #
    # --------------------------------------------------------- #

    def test_nonexistent_function(self, conn: BlockingWsSurrealConnection) -> None:
        raw = conn.query_raw("RETURN fn::does_not_exist()")
        result = raw["result"][0]

        assert result["status"] == "ERR"
        err = parse_query_error(result)
        assert isinstance(err, ServerError)
        assert "does_not_exist" in str(err)

    # --------------------------------------------------------- #
    # User THROW statement -> Thrown                             #
    # --------------------------------------------------------- #

    def test_user_throw(self, conn: BlockingWsSurrealConnection) -> None:
        raw = conn.query_raw('THROW "custom user error"')
        result = raw["result"][0]

        assert result["status"] == "ERR"
        err = parse_query_error(result)
        assert isinstance(err, ThrownError)
        assert err.kind == "Thrown"
        assert err.code == 0
        assert "custom user error" in str(err)
        assert err.details is None

    # --------------------------------------------------------- #
    # Duplicate record -> AlreadyExists + Record details         #
    # --------------------------------------------------------- #

    def test_duplicate_record(self, conn: BlockingWsSurrealConnection) -> None:
        conn.query("DEFINE TABLE IF NOT EXISTS se_dup_person SCHEMALESS")
        conn.query_raw("DELETE se_dup_person")
        conn.query('CREATE se_dup_person:dup SET name = "first"')

        raw = conn.query_raw('CREATE se_dup_person:dup SET name = "second"')
        result = raw["result"][0]

        assert result["status"] == "ERR"
        err = parse_query_error(result)
        assert isinstance(err, AlreadyExistsError)
        assert err.kind == "AlreadyExists"
        assert err.code == 0
        assert "se_dup_person:dup" in str(err)
        assert err.record_id == "se_dup_person:dup"

    # --------------------------------------------------------- #
    # query() throws ServerError directly                        #
    # --------------------------------------------------------- #

    def test_query_throws_server_error(self, conn: BlockingWsSurrealConnection) -> None:
        with pytest.raises(ServerError) as exc_info:
            conn.query('THROW "direct throw error"')

        err = exc_info.value
        assert isinstance(err, ThrownError)
        assert err.kind == "Thrown"
        assert err.code == 0
        assert "direct throw error" in str(err)

    # --------------------------------------------------------- #
    # Multi-statement: mix of success and failure                #
    # --------------------------------------------------------- #

    def test_multi_statement_responses(self, conn: BlockingWsSurrealConnection) -> None:
        raw = conn.query_raw('RETURN 1; THROW "fail"; RETURN 3')
        results = raw["result"]

        assert len(results) == 3

        assert results[0]["status"] == "OK"
        assert results[0]["result"] == 1

        assert results[1]["status"] == "ERR"
        err = parse_query_error(results[1])
        assert isinstance(err, ThrownError)
        assert err.kind == "Thrown"
        assert "fail" in str(err)

        assert results[2]["status"] == "OK"
        assert results[2]["result"] == 3

    # --------------------------------------------------------- #
    # RPC-level error: invalid credentials via signin            #
    # --------------------------------------------------------- #

    def test_rpc_level_not_allowed_error(self, v3_ws: dict) -> None:
        url = v3_ws["url"]
        conn = BlockingWsSurrealConnection(url)
        try:
            with pytest.raises(ServerError) as exc_info:
                conn.signin({"username": "wrong", "password": "wrong"})

            err = exc_info.value
            assert isinstance(err, NotAllowedError)
            assert err.kind == "NotAllowed"
            assert err.code != 0
            assert err.is_invalid_auth is True
        finally:
            if conn.socket:
                conn.socket.close()
