"""
This file defines the interface between python and the Rust SurrealDB library for creating a document.
"""
import json

from surrealdb.rust_surrealdb import blocking_create


class CreateMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """
    def create(self: "SurrealDB", name: str, data: dict) -> None:
        """
        Creates a new document in the database.

        :param name: the name of the document to create
        :param data: the data to store in the document

        :return: None
        """
        try:
            blocking_create(self._connection, name, json.dumps(data), self._daemon.port)
        except Exception as e:
            print(e)
