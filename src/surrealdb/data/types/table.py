"""
Defines a Table class to represent a database table by its name.
"""

from typing import Union

TableType = Union[str, "Table"]


class Table:
    """
    Represents a database table by its name.

    Attributes:
        table_name: The name of the table.
    """

    def __init__(self, table_name: str) -> None:
        """
        Initializes a Table object with a specific table name.

        Args:
            table_name: The name of the table.
        """
        self.table_name = table_name

    def __str__(self) -> str:
        """
        Returns a string representation of the table.

        Returns:
            The name of the table as a string.
        """
        return f"{self.table_name}"

    def __repr__(self) -> str:
        """
        Returns a string representation of the table for debugging purposes.

        Returns:
            The name of the table as a string.
        """
        return f"{self.table_name}"

    def __eq__(self, other: object) -> bool:
        """
        Compares two Table objects for equality.

        Args:
            other: The object to compare against.

        Returns:
            True if the table names are equal, False otherwise.
        """
        if isinstance(other, Table):
            return self.table_name == other.table_name
        return False
