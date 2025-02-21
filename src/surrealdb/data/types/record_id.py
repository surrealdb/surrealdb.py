"""
Defines the data type for the record ID.
"""


class RecordID:
    """
    An identifier of the record. This class houses the ID of the row, and the table name.

    Attributes:
        table_name: The table name associated with the record ID
        identifier: The ID of the row
    """

    def __init__(self, table_name: str, identifier) -> None:
        """
        The constructor for the RecordID class.

        Args:
            table_name: The table name associated with the record ID
            identifier: The ID of the row
        """
        self.table_name = table_name
        self.id = identifier

    def __str__(self) -> str:
        return f"{self.table_name}:{self.id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(table_name={self.table_name}, record_id={self.id})".format(
            self=self
        )

    def __eq__(self, other):
        if isinstance(other, RecordID):
            return self.table_name == other.table_name and self.id == other.id

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
