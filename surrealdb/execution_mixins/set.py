"""
This file defines the interface between python and the Rust SurrealDB library for setting a key value.
"""
import json

from surrealdb.rust_surrealdb import blocking_set
from surrealdb.errors import SurrealDbError


class SetMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """
    def set(self: "SurrealDB", key: str, value: dict) -> None:
        """
        Creates a new document in the database.

        :param name: the name of the document to create
        :param data: the data to store in the document

        :return: None
        """
        json_str = None
        try:
            json_str = json.dumps(value)
        except json.JSONEncodeError as e:
            print(f"cannot serialize value {type(value)} to json")
            SurrealDbError(e)
        if json_str is not None:
            try:
                blocking_set(self._connection, key, json_str)
            except Exception as e:
                SurrealDbError(e)
