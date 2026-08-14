"""
Defines a Table class to represent a database table by its name.
"""

from typing import Any, Union

TableType = Union[str, "Table"]


def table_name_type_error(
    owner: str,
    table_name: Any,
    argument: str = "name",
    identifier: Any = None,
) -> TypeError:
    """Build the message for a table name that is not a string.

    Shared with :class:`~surrealdb.data.types.record_id.RecordID`, and it lives
    here rather than there because ``record_id`` already imports this module
    and the reverse would be a cycle.

    Only the *type* is checked, never the content: SurrealDB accepts any string
    as a table name - empty, spaces, unicode, a leading digit, all digits, even
    one containing a colon - so there is nothing else to be sure of.

    *identifier*, when given, is the other argument to ``RecordID``. It is used
    only to spot swapped arguments, which is much the likeliest way a non-string
    table name gets here.
    """
    got = type(table_name).__name__
    hint = ""
    if isinstance(identifier, str) and not isinstance(table_name, str):
        hint = (
            f" The arguments look swapped - did you mean"
            f" {owner}({identifier!r}, {table_name!r})?"
        )
    elif isinstance(table_name, Table):
        hint = f" Pass the name itself: {owner}(table.table_name, ...)."
    elif table_name is None:
        hint = (
            " A table name is always a string, so there is no table this could"
            " have meant."
        )
    return TypeError(
        f"{owner}() {argument} must be a str, got {got}: {table_name!r}.{hint}"
    )


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

        Raises:
            TypeError: if *table_name* is not a string.

        A non-string name is refused here because nothing downstream refused
        it. ``Table(None)`` reached the server as the *table named* ``None``
        and the write succeeded: ``db.insert(Table(None), [row])`` returned a
        plausible-looking record, ``SELECT * FROM ⟨None⟩`` found it, and
        ``INFO FOR DB`` listed a table called ``None`` - on both SurrealDB 2.x
        and 3.x. The row was really written, just nowhere any query against the
        intended table would ever look. ``Table(123)`` failed differently and
        no better, with ``TypeError: 'int' object is not iterable`` raised from
        inside the SDK's identifier escaping, naming neither the argument nor
        the mistake.
        """
        if not isinstance(table_name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise table_name_type_error("Table", table_name)
        self.table_name: str = table_name

    @classmethod
    def _unchecked(cls, table_name: Any) -> "Table":
        """Build a ``Table`` without validating, for the CBOR decoder.

        See :meth:`RecordID._unchecked` for why the decode path bypasses the
        check rather than sharing it.
        """
        table = object.__new__(cls)
        table.table_name = table_name
        return table

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

    def __hash__(self) -> int:
        """
        Returns a hash of the table, consistent with ``__eq__``.

        Returns:
            The hash of the table name.
        """
        return hash(self.table_name)
