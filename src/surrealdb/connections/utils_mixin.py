import re
from typing import Any

from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import SurrealError, parse_query_error, parse_rpc_error

# See builders._TABLE_ID_PATTERN - kept here as a sibling so both the legacy
# select() path and the new builder pipeline use the exact same safe-binding
# rules for plain string targets.
_TABLE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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

        Parameter binding is used for every code path so user-supplied
        record-id or table-name strings cannot inject SurrealQL. See
        :func:`surrealdb.connections.builders._resource_to_variable` for the
        full rules - this implementation matches it exactly.
        """
        if isinstance(resource, RecordID):
            variables[var_name] = resource
            return f"${var_name}"

        if isinstance(resource, Table):
            variables[var_name] = resource.table_name
            return f"type::table(${var_name})"

        if ":" in resource and ".." not in resource:
            table, _, ident = resource.partition(":")
            if not table or not ident:
                raise SurrealError(
                    f"Invalid record-id string {resource!r} for resource '{var_name}'"
                )
            if ident.lstrip("-").isdigit():
                try:
                    variables[var_name] = RecordID(table, int(ident))
                except ValueError:  # pragma: no cover - defensive
                    variables[var_name] = RecordID(table, ident)
            else:
                variables[var_name] = RecordID(table, ident)
            return f"${var_name}"

        if _TABLE_ID_PATTERN.match(resource):
            variables[var_name] = resource
            return f"type::table(${var_name})"

        if any(c in resource for c in ";\n\r"):
            raise SurrealError(
                "Resource string contains unsafe characters (';', newline). "
                "Use a RecordID or Table instance instead of a raw string."
            )
        return resource
