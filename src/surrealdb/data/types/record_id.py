"""
Defines the data type for the record ID.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Union, cast

from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo

from surrealdb.data.types.table import Table

if TYPE_CHECKING:
    from pydantic import GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue

RecordIdType = Union[str, "RecordID", Table]


class RecordID:
    """
    An identifier of the record. This class houses the ID of the row, and the table name.

    Attributes:
        table_name: The table name associated with the record ID
        identifier: The ID of the row
    """

    def __init__(self, table_name: str, identifier: Any) -> None:
        """
        The constructor for the RecordID class.

        Args:
            table_name: The table name associated with the record ID
            identifier: The ID of the row
        """
        from surrealdb.types import Value  # imported here to prevent circular import

        self.table_name: str = table_name
        self.id: Value = cast(Value, identifier)

    @staticmethod
    def _escape_identifier(identifier: str) -> str:
        """
        Escapes a string identifier if needed, following SurrealDB's EscapeRid logic.

        Identifiers need escaping if:
        - Empty string
        - Contains non-alphanumeric characters (except underscore)
        - Contains only digits and underscores (no alphabetic characters)

        Args:
            identifier: The string identifier to potentially escape

        Returns:
            The escaped identifier with angle brackets if needed, or the original if not
        """
        # Empty string needs escaping
        if not identifier:
            return f"⟨{identifier}⟩"

        # Check if contains any non-alphanumeric character (excluding underscore)
        has_special_chars = any(not c.isalnum() and c != "_" for c in identifier)

        # Check if all characters are digits or underscores (no alphabetic characters)
        # This means it needs escaping to distinguish from numeric IDs
        has_no_alpha = not any(c.isalpha() for c in identifier)

        # Apply escaping if any condition is met
        if has_special_chars or has_no_alpha:
            # Escape any angle brackets in the identifier itself
            escaped = identifier.replace("⟩", "\\⟩")
            return f"⟨{escaped}⟩"

        return identifier

    def __str__(self) -> str:
        # Only escape if the identifier is a string
        if isinstance(self.id, str):
            escaped_id = self._escape_identifier(self.id)
            return f"{self.table_name}:{escaped_id}"
        if isinstance(self.id, bytes):
            escaped_id = self._escape_identifier(self.id.decode())
            return f"{self.table_name}:{escaped_id}"
        return f"{self.table_name}:{self.id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(table_name={self.table_name}, record_id={self.id!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecordID):
            return self.table_name == other.table_name and self.id == other.id
        return False

    @staticmethod
    def parse(record_str: str) -> RecordID:
        """
        Converts a string to a RecordID object.

        Args:
            record_str: The string representation of the record ID

        Returns: A RecordID object.

        """
        if ":" not in record_str:
            raise ValueError(
                'invalid string provided for parse. the expected string format is "table_name:record_id"'
            )

        table, record_id = record_str.split(":")
        return RecordID(table, record_id)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,  # pyright: ignore[reportExplicitAny, reportAny]
        _handler: Callable[[Any], core_schema.CoreSchema],  # pyright: ignore[reportExplicitAny]
    ) -> core_schema.CoreSchema:
        def validate_from_str(value: str, _info: ValidationInfo) -> RecordID:
            return RecordID.parse(value)

        from_str_schema = core_schema.str_schema()
        from_chain_schema = core_schema.chain_schema(
            [
                from_str_schema,
                core_schema.with_info_plain_validator_function(validate_from_str),
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=from_chain_schema,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(RecordID),
                    from_chain_schema,
                ]
            ),
            serialization=core_schema.wrap_serializer_function_ser_schema(
                lambda value, _handler, info: value
                if info.mode == "python"
                else str(value),
                info_arg=True,
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.str_schema())
