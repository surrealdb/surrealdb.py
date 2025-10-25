"""
Defines the data type for the record ID.
"""

from typing import Any, Union

from surrealdb.data.types.table import Table

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
        self.table_name = table_name
        self.id = identifier

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
        return f"{self.table_name}:{self.id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(table_name={self.table_name}, record_id={self.id!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecordID):
            return self.table_name == other.table_name and self.id == other.id
        return False

    @staticmethod
    def parse(record_str: str) -> "RecordID":
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
