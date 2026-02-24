"""
SurrealDB SDK error hierarchy.

All errors raised by this SDK extend ``SurrealError`` so that callers can
``except SurrealError`` to catch everything.  Server-originated errors use
the ``ServerError`` sub-tree which mirrors the structured error format
(kind / details / cause) introduced in SurrealDB 3.x while remaining
backward-compatible with the legacy code-only format.
"""

from __future__ import annotations

from typing import Any

# ------------------------------------------------------------------ #
#  Base                                                                #
# ------------------------------------------------------------------ #


class SurrealError(Exception):
    """Base class for every error raised by the SurrealDB Python SDK."""


# ------------------------------------------------------------------ #
#  ErrorKind constants                                                 #
# ------------------------------------------------------------------ #


class ErrorKind:
    """Known error kinds returned by the SurrealDB server.

    Use these constants for matching against ``ServerError.kind``.
    """

    VALIDATION = "Validation"
    CONFIGURATION = "Configuration"
    THROWN = "Thrown"
    QUERY = "Query"
    SERIALIZATION = "Serialization"
    NOT_ALLOWED = "NotAllowed"
    NOT_FOUND = "NotFound"
    ALREADY_EXISTS = "AlreadyExists"
    CONNECTION = "Connection"
    INTERNAL = "Internal"


# ------------------------------------------------------------------ #
#  Detail kind constants (mirrors Rust ``ErrorDetails`` tree)          #
# ------------------------------------------------------------------ #


class AuthDetailKind:
    """Detail kinds for authentication errors (nested inside ``NotAllowed``)."""

    TOKEN_EXPIRED = "TokenExpired"
    SESSION_EXPIRED = "SessionExpired"
    INVALID_AUTH = "InvalidAuth"
    UNEXPECTED_AUTH = "UnexpectedAuth"
    MISSING_USER_OR_PASS = "MissingUserOrPass"
    NO_SIGNIN_TARGET = "NoSigninTarget"
    INVALID_PASS = "InvalidPass"
    TOKEN_MAKING_FAILED = "TokenMakingFailed"
    INVALID_SIGNUP = "InvalidSignup"
    INVALID_ROLE = "InvalidRole"
    NOT_ALLOWED = "NotAllowed"


class ValidationDetailKind:
    """Detail kinds for validation errors."""

    PARSE = "Parse"
    INVALID_REQUEST = "InvalidRequest"
    INVALID_PARAMS = "InvalidParams"
    NAMESPACE_EMPTY = "NamespaceEmpty"
    DATABASE_EMPTY = "DatabaseEmpty"
    INVALID_PARAMETER = "InvalidParameter"
    INVALID_CONTENT = "InvalidContent"
    INVALID_MERGE = "InvalidMerge"


class ConfigurationDetailKind:
    """Detail kinds for configuration errors."""

    LIVE_QUERY_NOT_SUPPORTED = "LiveQueryNotSupported"
    BAD_LIVE_QUERY_CONFIG = "BadLiveQueryConfig"
    BAD_GRAPHQL_CONFIG = "BadGraphqlConfig"


class QueryDetailKind:
    """Detail kinds for query errors."""

    NOT_EXECUTED = "NotExecuted"
    TIMED_OUT = "TimedOut"
    CANCELLED = "Cancelled"


class SerializationDetailKind:
    """Detail kinds for serialization errors."""

    SERIALIZATION = "Serialization"
    DESERIALIZATION = "Deserialization"


class NotAllowedDetailKind:
    """Detail kinds for not-allowed errors."""

    SCRIPTING = "Scripting"
    AUTH = "Auth"
    METHOD = "Method"
    FUNCTION = "Function"
    TARGET = "Target"


class NotFoundDetailKind:
    """Detail kinds for not-found errors."""

    METHOD = "Method"
    SESSION = "Session"
    TABLE = "Table"
    RECORD = "Record"
    NAMESPACE = "Namespace"
    DATABASE = "Database"
    TRANSACTION = "Transaction"


class AlreadyExistsDetailKind:
    """Detail kinds for already-exists errors."""

    SESSION = "Session"
    TABLE = "Table"
    RECORD = "Record"
    NAMESPACE = "Namespace"
    DATABASE = "Database"


class ConnectionDetailKind:
    """Detail kinds for connection errors."""

    UNINITIALISED = "Uninitialised"
    ALREADY_CONNECTED = "AlreadyConnected"


# ------------------------------------------------------------------ #
#  Detail helpers                                                      #
#                                                                      #
#  Server error details use the ``{kind, details?}`` wire format.      #
# ------------------------------------------------------------------ #


def _detail_kind(details: Any) -> str | None:
    """Extract the ``kind`` from a ``{kind, details?}`` detail object."""
    if isinstance(details, dict):
        kind = details.get("kind")
        if isinstance(kind, str):
            return kind
    return None


def _detail_inner(details: Any) -> Any:
    """Extract the ``details`` value from a ``{kind, details?}`` detail object."""
    if isinstance(details, dict):
        return details.get("details")
    return None


def _detail_field(details: Any, kind: str, field: str) -> str | None:
    """Get a named string field from details matching *kind*."""
    if _detail_kind(details) != kind:
        return None
    inner = _detail_inner(details)
    if isinstance(inner, dict) and field in inner:
        value = inner[field]
        return str(value) if value is not None else None
    return None


# ------------------------------------------------------------------ #
#  Server error hierarchy                                              #
# ------------------------------------------------------------------ #


class ServerError(SurrealError):
    """Error received from the SurrealDB server.

    Attributes:
        kind: The structured error kind (e.g. ``"NotAllowed"``, ``"NotFound"``).
        code: Legacy JSON-RPC error code.  ``0`` when unavailable.
        details: Kind-specific structured details.  ``None`` when not provided.
        server_cause: The underlying server error in the chain, if any.
    """

    def __init__(
        self,
        kind: str,
        message: str,
        code: int = 0,
        details: dict[str, Any] | None = None,
        cause: ServerError | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: str = kind
        self.code: int = code
        self.details: dict[str, Any] | None = details
        if cause is not None:
            self.__cause__ = cause

    @property
    def server_cause(self) -> ServerError | None:
        """The server-side cause (typed as ``ServerError``)."""
        if isinstance(self.__cause__, ServerError):
            return self.__cause__
        return None

    def has_kind(self, kind: str) -> bool:
        """Check if this error or any cause in the chain matches *kind*."""
        if self.kind == kind:
            return True
        cause = self.server_cause
        if cause is not None:
            return cause.has_kind(kind)
        return False

    def find_cause(self, kind: str) -> ServerError | None:
        """Find the first error in the cause chain matching *kind*."""
        if self.kind == kind:
            return self
        cause = self.server_cause
        if cause is not None:
            return cause.find_cause(kind)
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(kind={self.kind!r}, message={str(self)!r})"


# -- Subclasses per ErrorKind ---------------------------------------- #


class ValidationError(ServerError):
    """Validation failure (parse error, invalid request/params, bad input)."""

    @property
    def is_parse_error(self) -> bool:
        return _detail_kind(self.details) == "Parse"

    @property
    def parameter_name(self) -> str | None:
        return _detail_field(self.details, "InvalidParameter", "name")


class ConfigurationError(ServerError):
    """Feature or configuration not supported (live queries, GraphQL)."""

    @property
    def is_live_query_not_supported(self) -> bool:
        return _detail_kind(self.details) == "LiveQueryNotSupported"


class ThrownError(ServerError):
    """User-thrown error via ``THROW`` in SurrealQL."""


class QueryError(ServerError):
    """Query execution failure (timeout, cancelled, not executed)."""

    @property
    def is_not_executed(self) -> bool:
        return _detail_kind(self.details) == "NotExecuted"

    @property
    def is_timed_out(self) -> bool:
        return _detail_kind(self.details) == "TimedOut"

    @property
    def is_cancelled(self) -> bool:
        return _detail_kind(self.details) == "Cancelled"

    @property
    def timeout(self) -> dict[str, Any] | None:
        """The timeout duration (``{"secs": ..., "nanos": ...}``) or ``None``."""
        if _detail_kind(self.details) != "TimedOut":
            return None
        inner = _detail_inner(self.details)
        if isinstance(inner, dict):
            duration = inner.get("duration")
            if isinstance(duration, dict):
                return duration
        return None


class SerializationError(ServerError):
    """Serialization or deserialization failure."""

    @property
    def is_deserialization(self) -> bool:
        return _detail_kind(self.details) == "Deserialization"


class NotAllowedError(ServerError):
    """Permission denied, method not allowed, function/scripting blocked."""

    @property
    def is_token_expired(self) -> bool:
        if _detail_kind(self.details) != "Auth":
            return False
        return _detail_kind(_detail_inner(self.details)) == "TokenExpired"

    @property
    def is_invalid_auth(self) -> bool:
        if _detail_kind(self.details) != "Auth":
            return False
        return _detail_kind(_detail_inner(self.details)) == "InvalidAuth"

    @property
    def is_scripting_blocked(self) -> bool:
        return _detail_kind(self.details) == "Scripting"

    @property
    def method_name(self) -> str | None:
        return _detail_field(self.details, "Method", "name")

    @property
    def function_name(self) -> str | None:
        return _detail_field(self.details, "Function", "name")

    @property
    def target_name(self) -> str | None:
        return _detail_field(self.details, "Target", "name")


class NotFoundError(ServerError):
    """Resource not found (table, record, namespace, method, etc.)."""

    @property
    def table_name(self) -> str | None:
        return _detail_field(self.details, "Table", "name")

    @property
    def record_id(self) -> str | None:
        return _detail_field(self.details, "Record", "id")

    @property
    def method_name(self) -> str | None:
        return _detail_field(self.details, "Method", "name")

    @property
    def namespace_name(self) -> str | None:
        return _detail_field(self.details, "Namespace", "name")

    @property
    def database_name(self) -> str | None:
        return _detail_field(self.details, "Database", "name")

    @property
    def session_id(self) -> str | None:
        return _detail_field(self.details, "Session", "id")


class AlreadyExistsError(ServerError):
    """Duplicate resource (record, table, namespace, etc.)."""

    @property
    def record_id(self) -> str | None:
        return _detail_field(self.details, "Record", "id")

    @property
    def table_name(self) -> str | None:
        return _detail_field(self.details, "Table", "name")

    @property
    def session_id(self) -> str | None:
        return _detail_field(self.details, "Session", "id")

    @property
    def namespace_name(self) -> str | None:
        return _detail_field(self.details, "Namespace", "name")

    @property
    def database_name(self) -> str | None:
        return _detail_field(self.details, "Database", "name")


class InternalError(ServerError):
    """Internal or unexpected server error (fallback)."""


# ------------------------------------------------------------------ #
#  SDK-side errors                                                     #
# ------------------------------------------------------------------ #


class ConnectionUnavailableError(SurrealError):
    """No active connection to the database."""


class UnsupportedEngineError(SurrealError):
    """The URL protocol/engine is not supported."""

    def __init__(self, url: str) -> None:
        super().__init__(
            f"Unsupported protocol in URL: {url}. "
            "Use 'memory', 'mem://', 'file://', 'surrealkv://', 'ws://', or 'http://'."
        )
        self.url = url


class UnsupportedFeatureError(SurrealError):
    """Feature not supported by this connection type."""


class UnexpectedResponseError(SurrealError):
    """Server returned an unexpected response format."""


class InvalidRecordIdError(SurrealError):
    """RecordID string could not be parsed."""


class InvalidDurationError(SurrealError):
    """Duration string could not be parsed."""


class InvalidGeometryError(SurrealError):
    """Geometry data is invalid."""


class InvalidTableError(SurrealError):
    """Table or record ID string is invalid."""


# ------------------------------------------------------------------ #
#  Backward compatibility                                              #
# ------------------------------------------------------------------ #

SurrealDBMethodError = ServerError
"""Deprecated alias kept for backward compatibility."""


# ------------------------------------------------------------------ #
#  Error parsing                                                       #
# ------------------------------------------------------------------ #

CODE_TO_KIND: dict[int, str] = {
    -32700: "Validation",
    -32600: "Validation",
    -32603: "Validation",
    -32601: "NotFound",
    -32602: "NotAllowed",
    -32002: "NotAllowed",
    -32604: "Configuration",
    -32605: "Configuration",
    -32606: "Configuration",
    -32000: "Internal",
    -32001: "Connection",
    -32003: "Query",
    -32004: "Query",
    -32005: "Query",
    -32006: "Thrown",
    -32007: "Serialization",
    -32008: "Serialization",
}

KIND_TO_CLASS: dict[str, type[ServerError]] = {
    "Validation": ValidationError,
    "Configuration": ConfigurationError,
    "Thrown": ThrownError,
    "Query": QueryError,
    "Serialization": SerializationError,
    "NotAllowed": NotAllowedError,
    "NotFound": NotFoundError,
    "AlreadyExists": AlreadyExistsError,
    "Internal": InternalError,
}


def _resolve_kind(kind: str | None, code: int | None) -> str:
    """Determine the error kind from *kind* and/or legacy *code*."""
    if kind:
        return kind
    if code is not None:
        return CODE_TO_KIND.get(code, "Internal")
    return "Internal"


def parse_rpc_error(raw: dict[str, Any]) -> ServerError:
    """Parse an RPC-level error response into a ``ServerError``.

    Handles both the new format (``kind`` + ``details`` + ``cause``) and
    the legacy format (``code`` + ``message`` only).
    """
    kind = _resolve_kind(raw.get("kind"), raw.get("code"))
    cause: ServerError | None = None
    if raw.get("cause") is not None:
        cause = parse_rpc_error(raw["cause"])
    cls = KIND_TO_CLASS.get(kind, ServerError)
    return cls(
        kind=kind,
        message=raw.get("message", ""),
        code=raw.get("code", 0),
        details=raw.get("details"),
        cause=cause,
    )


def parse_query_error(raw: dict[str, Any]) -> ServerError:
    """Parse a query result error into a ``ServerError``.

    Query errors use ``result`` as the message field and have no ``code``.
    """
    kind = _resolve_kind(raw.get("kind"), None)
    details = raw.get("details")

    # Workaround: SurrealDB v3.0.0 double-wraps details in query result
    # errors.  Fixed in v3.0.1, but kept for backward compatibility.
    if (
        isinstance(details, dict)
        and details.get("kind") == kind
        and isinstance(details.get("details"), dict)
    ):
        details = details["details"]

    cause: ServerError | None = None
    if raw.get("cause") is not None:
        cause = parse_rpc_error(raw["cause"])
    cls = KIND_TO_CLASS.get(kind, ServerError)
    return cls(
        kind=kind,
        message=raw.get("result", ""),
        code=0,
        details=details,
        cause=cause,
    )
