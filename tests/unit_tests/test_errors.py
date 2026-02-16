"""Comprehensive tests for the SurrealDB SDK error hierarchy and parsing."""

import pytest

from surrealdb.errors import (
    AlreadyExistsError,
    ConfigurationError,
    ConnectionUnavailableError,
    ErrorKind,
    InternalError,
    InvalidDurationError,
    InvalidGeometryError,
    InvalidRecordIdError,
    InvalidTableError,
    NotAllowedError,
    NotFoundError,
    QueryError,
    SerializationError,
    ServerError,
    SurrealDBMethodError,
    SurrealError,
    ThrownError,
    UnexpectedResponseError,
    UnsupportedEngineError,
    UnsupportedFeatureError,
    ValidationError,
    parse_query_error,
    parse_rpc_error,
)

# ================================================================= #
#  Error parsing: new format (kind present)                          #
# ================================================================= #


class TestParseRpcErrorNewFormat:
    def test_not_allowed_with_token_expired_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32002,
                "kind": "NotAllowed",
                "message": "Token has expired",
                "details": {"Auth": "TokenExpired"},
            }
        )

        assert isinstance(err, ServerError)
        assert isinstance(err, NotAllowedError)
        assert err.kind == "NotAllowed"
        assert err.code == -32002
        assert str(err) == "Token has expired"
        assert err.details == {"Auth": "TokenExpired"}
        assert err.server_cause is None

        assert err.is_token_expired is True
        assert err.is_invalid_auth is False
        assert err.is_scripting_blocked is False
        assert err.method_name is None
        assert err.function_name is None

    def test_not_allowed_with_invalid_auth_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32002,
                "kind": "NotAllowed",
                "message": "Invalid credentials",
                "details": {"Auth": "InvalidAuth"},
            }
        )
        assert isinstance(err, NotAllowedError)
        assert err.is_invalid_auth is True
        assert err.is_token_expired is False

    def test_not_allowed_with_method_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32602,
                "kind": "NotAllowed",
                "message": "Method not allowed",
                "details": {"Method": {"name": "begin"}},
            }
        )
        assert isinstance(err, NotAllowedError)
        assert err.method_name == "begin"
        assert err.is_token_expired is False

    def test_not_allowed_with_scripting_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32602,
                "kind": "NotAllowed",
                "message": "Scripting is blocked",
                "details": {"Scripting": {}},
            }
        )
        assert isinstance(err, NotAllowedError)
        assert err.is_scripting_blocked is True

    def test_not_allowed_with_function_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32602,
                "kind": "NotAllowed",
                "message": "Function not allowed",
                "details": {"Function": {"name": "fn::custom"}},
            }
        )
        assert isinstance(err, NotAllowedError)
        assert err.function_name == "fn::custom"

    def test_not_found_with_table_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "Table not found",
                "details": {"Table": {"name": "users"}},
            }
        )

        assert isinstance(err, NotFoundError)
        assert err.kind == "NotFound"
        assert err.table_name == "users"
        assert err.record_id is None
        assert err.method_name is None

    def test_not_found_with_record_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "Record not found",
                "details": {"Record": {"id": "users:123"}},
            }
        )
        assert isinstance(err, NotFoundError)
        assert err.record_id == "users:123"
        assert err.table_name is None

    def test_not_found_with_method_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32601,
                "kind": "NotFound",
                "message": "Method not found",
                "details": {"Method": {"name": "unknown_method"}},
            }
        )
        assert isinstance(err, NotFoundError)
        assert err.method_name == "unknown_method"

    def test_not_found_with_namespace_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "Namespace not found",
                "details": {"Namespace": {"name": "test"}},
            }
        )
        assert isinstance(err, NotFoundError)
        assert err.namespace_name == "test"

    def test_not_found_with_database_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "Database not found",
                "details": {"Database": {"name": "test"}},
            }
        )
        assert isinstance(err, NotFoundError)
        assert err.database_name == "test"

    def test_already_exists_with_record_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "AlreadyExists",
                "message": "Record already exists",
                "details": {"Record": {"id": "users:123"}},
            }
        )
        assert isinstance(err, AlreadyExistsError)
        assert err.record_id == "users:123"
        assert err.table_name is None

    def test_already_exists_with_table_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "AlreadyExists",
                "message": "Table already exists",
                "details": {"Table": {"name": "users"}},
            }
        )
        assert isinstance(err, AlreadyExistsError)
        assert err.table_name == "users"

    def test_validation_with_parse_string_variant(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32700,
                "kind": "Validation",
                "message": "Parse error",
                "details": "Parse",
            }
        )
        assert isinstance(err, ValidationError)
        assert err.is_parse_error is True
        assert err.parameter_name is None

    def test_validation_with_invalid_parameter_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32603,
                "kind": "Validation",
                "message": "Invalid parameter",
                "details": {"InvalidParameter": {"name": "limit"}},
            }
        )
        assert isinstance(err, ValidationError)
        assert err.parameter_name == "limit"
        assert err.is_parse_error is False

    def test_query_not_executed(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32003,
                "kind": "Query",
                "message": "Query not executed",
                "details": {"NotExecuted": {}},
            }
        )
        assert isinstance(err, QueryError)
        assert err.is_not_executed is True
        assert err.is_timed_out is False
        assert err.is_cancelled is False
        assert err.timeout is None

    def test_query_timed_out(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32004,
                "kind": "Query",
                "message": "Query timed out",
                "details": {"TimedOut": {"duration": {"secs": 5, "nanos": 0}}},
            }
        )
        assert isinstance(err, QueryError)
        assert err.is_timed_out is True
        assert err.timeout == {"secs": 5, "nanos": 0}

    def test_query_cancelled(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32005,
                "kind": "Query",
                "message": "Query cancelled",
                "details": {"Cancelled": {}},
            }
        )
        assert isinstance(err, QueryError)
        assert err.is_cancelled is True

    def test_configuration_live_query_not_supported(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32604,
                "kind": "Configuration",
                "message": "Live queries not supported",
                "details": {"LiveQueryNotSupported": {}},
            }
        )
        assert isinstance(err, ConfigurationError)
        assert err.is_live_query_not_supported is True

    def test_serialization_deserialization(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32008,
                "kind": "Serialization",
                "message": "Deserialization failed",
                "details": {"Deserialization": {}},
            }
        )
        assert isinstance(err, SerializationError)
        assert err.is_deserialization is True

    def test_thrown_error(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32006,
                "kind": "Thrown",
                "message": "Custom user error",
            }
        )
        assert isinstance(err, ThrownError)
        assert err.kind == "Thrown"
        assert str(err) == "Custom user error"

    def test_internal_error(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "Internal",
                "message": "Something went wrong",
            }
        )
        assert isinstance(err, InternalError)

    def test_error_with_no_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "Not found",
            }
        )
        assert isinstance(err, NotFoundError)
        assert err.details is None
        assert err.table_name is None
        assert err.record_id is None

    def test_error_with_null_details(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "Internal",
                "message": "Error",
                "details": None,
            }
        )
        assert err.details is None


# ================================================================= #
#  Error parsing: old format (kind absent, derive from code)         #
# ================================================================= #


class TestParseRpcErrorOldFormat:
    @pytest.mark.parametrize(
        "code, expected_kind, expected_class",
        [
            (-32700, "Validation", ValidationError),
            (-32600, "Validation", ValidationError),
            (-32603, "Validation", ValidationError),
            (-32601, "NotFound", NotFoundError),
            (-32602, "NotAllowed", NotAllowedError),
            (-32002, "NotAllowed", NotAllowedError),
            (-32604, "Configuration", ConfigurationError),
            (-32605, "Configuration", ConfigurationError),
            (-32606, "Configuration", ConfigurationError),
            (-32000, "Internal", InternalError),
            (-32003, "Query", QueryError),
            (-32004, "Query", QueryError),
            (-32005, "Query", QueryError),
            (-32006, "Thrown", ThrownError),
            (-32007, "Serialization", SerializationError),
            (-32008, "Serialization", SerializationError),
        ],
    )
    def test_legacy_code_mapping(
        self,
        code: int,
        expected_kind: str,
        expected_class: type[ServerError],
    ) -> None:
        err = parse_rpc_error({"code": code, "message": "test"})
        assert isinstance(err, expected_class)
        assert err.kind == expected_kind

    def test_connection_code_creates_base_server_error(self) -> None:
        err = parse_rpc_error({"code": -32001, "message": "Client error"})
        assert isinstance(err, ServerError)
        assert err.kind == "Connection"

    def test_unknown_code_maps_to_internal(self) -> None:
        err = parse_rpc_error({"code": -99999, "message": "Unknown"})
        assert isinstance(err, InternalError)
        assert err.kind == "Internal"

    def test_old_format_preserves_code_and_message(self) -> None:
        err = parse_rpc_error({"code": -32002, "message": "Invalid credentials"})
        assert err.code == -32002
        assert str(err) == "Invalid credentials"
        assert err.details is None
        assert err.server_cause is None


# ================================================================= #
#  Error parsing: query result errors                                #
# ================================================================= #


class TestParseQueryError:
    def test_new_format_with_kind_and_details(self) -> None:
        err = parse_query_error(
            {
                "status": "ERR",
                "time": "1ms",
                "result": "Table not found",
                "kind": "NotFound",
                "details": {"Table": {"name": "users"}},
            }
        )
        assert isinstance(err, NotFoundError)
        assert err.kind == "NotFound"
        assert err.code == 0
        assert str(err) == "Table not found"
        assert err.table_name == "users"

    def test_old_format_message_only(self) -> None:
        err = parse_query_error(
            {
                "status": "ERR",
                "time": "1ms",
                "result": "There was a problem with the database: Table not found",
            }
        )
        assert isinstance(err, InternalError)
        assert err.kind == "Internal"
        assert err.code == 0
        assert str(err) == "There was a problem with the database: Table not found"
        assert err.details is None

    def test_with_cause_chain(self) -> None:
        err = parse_query_error(
            {
                "status": "ERR",
                "time": "1ms",
                "result": "Permission denied",
                "kind": "NotAllowed",
                "details": {"Auth": "TokenExpired"},
                "cause": {
                    "code": -32000,
                    "kind": "Internal",
                    "message": "Session expired",
                },
            }
        )
        assert isinstance(err, NotAllowedError)
        cause = err.server_cause
        assert cause is not None
        assert isinstance(cause, InternalError)
        assert str(cause) == "Session expired"


# ================================================================= #
#  Cause chain traversal                                             #
# ================================================================= #


class TestCauseChain:
    def test_deep_cause_chain_parsed_recursively(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotAllowed",
                "message": "Top level",
                "cause": {
                    "code": -32000,
                    "kind": "NotFound",
                    "message": "Middle",
                    "cause": {
                        "code": -32000,
                        "kind": "Internal",
                        "message": "Root cause",
                    },
                },
            }
        )
        assert isinstance(err, NotAllowedError)
        assert err.server_cause is not None
        assert isinstance(err.server_cause, NotFoundError)
        root = err.server_cause.server_cause
        assert root is not None
        assert isinstance(root, InternalError)
        assert str(root) == "Root cause"
        assert root.server_cause is None

    def test_has_kind_traverses_chain(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotAllowed",
                "message": "Top",
                "cause": {
                    "code": -32000,
                    "kind": "NotFound",
                    "message": "Nested",
                },
            }
        )
        assert err.has_kind("NotAllowed") is True
        assert err.has_kind("NotFound") is True
        assert err.has_kind("Internal") is False

    def test_find_cause_returns_matching_error(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotAllowed",
                "message": "Top",
                "cause": {
                    "code": -32000,
                    "kind": "NotFound",
                    "message": "Nested not found",
                    "details": {"Table": {"name": "users"}},
                },
            }
        )
        found = err.find_cause("NotFound")
        assert found is not None
        assert isinstance(found, NotFoundError)
        assert str(found) == "Nested not found"
        assert found.table_name == "users"

    def test_find_cause_returns_self_if_kind_matches(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "Self",
            }
        )
        assert err.find_cause("NotFound") is err

    def test_find_cause_returns_none_when_not_found(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "No match",
            }
        )
        assert err.find_cause("AlreadyExists") is None

    def test_python_cause_chain_works(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotAllowed",
                "message": "Top",
                "cause": {
                    "code": -32000,
                    "kind": "Internal",
                    "message": "Bottom",
                },
            }
        )
        assert err.__cause__ is not None
        assert isinstance(err.__cause__, InternalError)


# ================================================================= #
#  Forward compatibility: unknown kinds                              #
# ================================================================= #


class TestUnknownKinds:
    def test_unknown_kind_creates_base_server_error(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "FutureErrorKind",
                "message": "Some new error",
                "details": {"SomeNewDetail": {"foo": "bar"}},
            }
        )
        assert isinstance(err, ServerError)
        assert not isinstance(err, InternalError)
        assert err.kind == "FutureErrorKind"
        assert str(err) == "Some new error"
        assert err.details == {"SomeNewDetail": {"foo": "bar"}}

    def test_unknown_kind_does_not_lose_information(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "BrandNew",
                "message": "Details preserved",
            }
        )
        assert err.kind == "BrandNew"


# ================================================================= #
#  ErrorKind constants                                               #
# ================================================================= #


class TestErrorKind:
    def test_all_constants(self) -> None:
        assert ErrorKind.VALIDATION == "Validation"
        assert ErrorKind.CONFIGURATION == "Configuration"
        assert ErrorKind.THROWN == "Thrown"
        assert ErrorKind.QUERY == "Query"
        assert ErrorKind.SERIALIZATION == "Serialization"
        assert ErrorKind.NOT_ALLOWED == "NotAllowed"
        assert ErrorKind.NOT_FOUND == "NotFound"
        assert ErrorKind.ALREADY_EXISTS == "AlreadyExists"
        assert ErrorKind.CONNECTION == "Connection"
        assert ErrorKind.INTERNAL == "Internal"

    def test_can_be_used_for_comparison(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "NotFound",
                "message": "Test",
            }
        )
        assert err.kind == ErrorKind.NOT_FOUND


# ================================================================= #
#  ServerError class properties                                      #
# ================================================================= #


class TestServerErrorProperties:
    def test_extends_surreal_error(self) -> None:
        err = ServerError(kind="Internal", message="test")
        assert isinstance(err, Exception)
        assert isinstance(err, SurrealError)
        assert isinstance(err, ServerError)

    def test_defaults_code_to_zero(self) -> None:
        err = ServerError(kind="Internal", message="test")
        assert err.code == 0

    def test_defaults_details_to_none(self) -> None:
        err = ServerError(kind="Internal", message="test")
        assert err.details is None

    def test_message_in_str(self) -> None:
        err = ServerError(kind="Internal", message="test error message")
        assert "test error message" in str(err)

    def test_repr_includes_kind_and_message(self) -> None:
        err = ServerError(kind="NotFound", message="not here")
        r = repr(err)
        assert "ServerError" in r
        assert "NotFound" in r

    def test_subclass_isinstance(self) -> None:
        err = NotFoundError(kind="NotFound", message="test")
        assert isinstance(err, ServerError)
        assert isinstance(err, SurrealError)
        assert isinstance(err, NotFoundError)


# ================================================================= #
#  Backward compatibility: SurrealDBMethodError                      #
# ================================================================= #


class TestBackwardCompat:
    def test_surreal_db_method_error_is_server_error(self) -> None:
        assert SurrealDBMethodError is ServerError

    def test_isinstance_works(self) -> None:
        err = parse_rpc_error(
            {
                "code": -32000,
                "kind": "Internal",
                "message": "test",
            }
        )
        assert isinstance(err, SurrealDBMethodError)


# ================================================================= #
#  SDK-side error hierarchy                                          #
# ================================================================= #


class TestSdkSideErrors:
    def test_all_extend_surreal_error(self) -> None:
        sdk_classes: list[type[SurrealError]] = [
            ConnectionUnavailableError,
            UnsupportedEngineError,
            UnsupportedFeatureError,
            UnexpectedResponseError,
            InvalidRecordIdError,
            InvalidDurationError,
            InvalidGeometryError,
            InvalidTableError,
        ]
        for cls in sdk_classes:
            if cls is UnsupportedEngineError:
                err = cls("ws://bad")
            else:
                err = cls("test message")
            assert isinstance(err, SurrealError), f"{cls.__name__} not SurrealError"
            assert isinstance(err, Exception), f"{cls.__name__} not Exception"

    def test_not_server_errors(self) -> None:
        sdk_classes: list[type[SurrealError]] = [
            ConnectionUnavailableError,
            UnsupportedFeatureError,
            UnexpectedResponseError,
            InvalidRecordIdError,
            InvalidDurationError,
            InvalidGeometryError,
            InvalidTableError,
        ]
        for cls in sdk_classes:
            err = cls("test")
            assert not isinstance(err, ServerError), (
                f"{cls.__name__} should not be ServerError"
            )

    def test_unsupported_engine_stores_url(self) -> None:
        err = UnsupportedEngineError("ftp://localhost")
        assert err.url == "ftp://localhost"
        assert "ftp://localhost" in str(err)

    def test_connection_unavailable(self) -> None:
        err = ConnectionUnavailableError("WebSocket connection is not established")
        assert str(err) == "WebSocket connection is not established"

    def test_unsupported_feature(self) -> None:
        err = UnsupportedFeatureError("Multi-session not supported")
        assert str(err) == "Multi-session not supported"

    def test_unexpected_response(self) -> None:
        err = UnexpectedResponseError("Response ID mismatch")
        assert str(err) == "Response ID mismatch"

    def test_invalid_record_id(self) -> None:
        err = InvalidRecordIdError("bad format")
        assert str(err) == "bad format"

    def test_invalid_duration(self) -> None:
        err = InvalidDurationError("Invalid duration format: xyz")
        assert "xyz" in str(err)

    def test_invalid_geometry(self) -> None:
        err = InvalidGeometryError("ring not closed")
        assert str(err) == "ring not closed"

    def test_invalid_table(self) -> None:
        err = InvalidTableError("invalid table")
        assert str(err) == "invalid table"


# ================================================================= #
#  SurrealError catch-all                                            #
# ================================================================= #


class TestSurrealErrorCatchAll:
    def test_catches_server_errors(self) -> None:
        err = parse_rpc_error({"code": -32000, "kind": "Internal", "message": "boom"})
        with pytest.raises(SurrealError):
            raise err

    def test_catches_sdk_errors(self) -> None:
        with pytest.raises(SurrealError):
            raise ConnectionUnavailableError("no connection")

    def test_catches_all_subclasses(self) -> None:
        errors: list[SurrealError] = [
            InternalError(kind="Internal", message="a"),
            NotFoundError(kind="NotFound", message="b"),
            ConnectionUnavailableError("c"),
            InvalidRecordIdError("d"),
        ]
        for err in errors:
            with pytest.raises(SurrealError):
                raise err
