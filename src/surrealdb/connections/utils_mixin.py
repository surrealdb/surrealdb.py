from typing import Any

from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table


class UtilsMixin:
    @staticmethod
    def check_response_for_error(response: dict[str, Any], process: str) -> None:
        if response.get("error") is not None:
            raise Exception(response.get("error"))

    @staticmethod
    def check_response_for_result(response: dict[str, Any], process: str) -> None:
        if "result" not in response.keys():
            raise Exception(f"no result {process}: {response}")

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
        """
        Converts a resource (Table, RecordID, or string) into a variable reference for SQL queries.
        Similar to Rust SDK's for_sql_query method.

        Args:
            resource: The resource to convert (Table, RecordID, or string)
            variables: Dictionary to store the variable value
            var_name: Name of the variable to use

        Returns:
            Variable reference string (e.g., "$_table") or raw string for complex queries
        """
        if isinstance(resource, Table):
            # Table objects should use their table_name directly in SQL
            # since they don't have CBOR serialization
            return resource.table_name
        elif isinstance(resource, RecordID):
            variables[var_name] = resource
            return f"${var_name}"
        else:
            # For strings, use them directly in SQL without converting to variables
            # This avoids issues with SurrealDB not properly handling RecordID/Table variables
            # in certain contexts (like DELETE)
            return resource
