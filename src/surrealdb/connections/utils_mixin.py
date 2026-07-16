from typing import Any

from surrealdb.connections.builders import (
    _resource_to_variable,  # pyright: ignore[reportPrivateUsage]
)
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ErrorKind,
    SurrealError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.types import Value

# Legacy JSON-RPC error code historically returned by the ``info`` RPC when a
# record-authenticated session has no ROOT/NS/DB scope to report (the message
# used to read "No result found"). Newer servers surface this as a structured
# ``NotFound`` error instead; both are handled by :meth:`UtilsMixin.
# _info_needs_auth_fallback`.
_NO_RESULT_RPC_CODE = -32000

# The SurrealQL used to resolve the currently authenticated record for
# record-level ("scope") users when ``info`` reports no result.
AUTH_FALLBACK_QUERY = "SELECT * FROM $auth"

# These are re-exported for backwards compatibility with downstream code
# that imported them via ``surrealdb.connections.utils_mixin``.
__all__ = [
    "RecordID",
    "RecordIdType",
    "SurrealError",
    "Table",
    "UtilsMixin",
]


class UtilsMixin:
    @staticmethod
    def check_response_for_error(response: dict[str, Any], process: str) -> None:
        error = response.get("error")
        if error is not None:
            raise parse_rpc_error(error)

    @staticmethod
    def check_response_for_result(response: dict[str, Any], process: str) -> None:
        if "result" not in response.keys():
            raise SurrealError(f"no result {process}: {response}")

    @staticmethod
    def _info_needs_auth_fallback(response: dict[str, Any]) -> bool:
        """Return ``True`` when an ``info`` response should fall back to ``$auth``.

        Record-level ("scope") authenticated sessions have no ROOT/NS/DB
        identity for the ``info`` RPC to report, so the server returns a
        "no result / not found" error rather than a payload. When that
        happens the caller should re-resolve the authenticated record via
        ``SELECT * FROM $auth`` so record-auth users get a consistent result
        across every transport.

        The decision is keyed on the *structured* error (``kind`` /
        legacy ``code``) rather than the human-readable message text, which
        is not part of any stability contract and varies between server
        versions.
        """
        error = response.get("error")
        if not error:
            return False
        parsed = parse_rpc_error(error)
        # New servers report this as a structured ``NotFound`` error; older
        # ones use the legacy ``-32000`` code. Match either, never the text.
        return (
            parsed.has_kind(ErrorKind.NOT_FOUND) or parsed.code == _NO_RESULT_RPC_CODE
        )

    @staticmethod
    def _extract_auth_record(auth_result: Any) -> Value | None:
        """Extract the single record from a ``SELECT * FROM $auth`` result.

        ``auth_result`` is the statement result produced by the query
        builders (a list of matching records). Returns the single
        authenticated record, or ``None`` when there is no such record so
        the caller can re-raise the original ``info`` error.
        """
        if isinstance(auth_result, list) and len(auth_result) > 0:
            return auth_result[0]
        return None

    @staticmethod
    def _check_query_result(stmt: dict[str, Any]) -> None:
        """Raise if a query statement result has ``status: "ERR"``."""
        if stmt.get("status") == "ERR":
            raise parse_query_error(stmt)

    @staticmethod
    def _is_single_record_operation(resource: RecordIdType) -> bool:
        """
        Determines if a resource refers to a single record operation.

        Args:
            resource: The resource (Table, RecordID, or string)

        Returns:
            True if this is a single record operation, False if it's a table-level operation
        """
        if isinstance(resource, RecordID):
            return True
        elif isinstance(resource, Table):
            return False
        else:
            # Check if it contains a colon (record ID format like "user:tobie")
            # But exclude range syntax like "user:1..10"
            if ":" in resource and ".." not in resource:
                return True
            return False

    @staticmethod
    def _unwrap_result(result: Any, unwrap: bool) -> Any:
        """
        Unwraps a single-item list result if needed.

        Args:
            result: The result from the database (could be a list, dict, or other)
            unwrap: Whether to unwrap single-item lists

        Returns:
            The unwrapped result if unwrap is True and result is a single-item list,
            otherwise returns the result as-is

        Note: Returns Any because the database can return various types (dict, list, str, etc.)
        and we preserve whatever type the database sends.
        """
        # Intentionally returning Any - database results are dynamic and cannot be
        # typed more specifically without runtime schema validation
        if unwrap and isinstance(result, list) and len(result) == 1:
            return result[0]
        return result

    @staticmethod
    def _resource_to_variable(
        resource: RecordIdType, variables: dict[str, Any], var_name: str
    ) -> str:
        """Render *resource* as a variable reference inside generated SurrealQL.

        Single source of truth: this method delegates to
        :func:`surrealdb.connections.builders._resource_to_variable` so the
        legacy ``select()`` code path and the new builder pipeline can never
        diverge in their parameterisation rules.
        """
        return _resource_to_variable(resource, variables, var_name)
