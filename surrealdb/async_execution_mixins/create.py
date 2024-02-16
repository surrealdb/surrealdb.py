"""
This file defines the interface between python and the Rust SurrealDB library for creating a document.
"""
import json
from typing import List, Union

from surrealdb.rust_surrealdb import rust_create_future
from surrealdb.rust_surrealdb import rust_delete_future

from surrealdb.errors import SurrealDbError


class AsyncCreateMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """
    async def create(self: "SurrealDB", name: str, data: dict) -> None:
        """
        Creates a new document in the database.

        :param name: the name of the document to create
        :param data: the data to store in the document

        :return: None
        """
        try:
            return json.loads(await rust_create_future(self._connection, name, json.dumps(data)))
        except Exception as e:
            raise SurrealDbError(e)

    async def delete(self: "SurrealDB", name: str) -> Union[List[dict], dict]:
        """
        Deletes a document in the database.

        :param name: the name of the document to delete

        :return: the record or records that were deleted
        """
        try:
            return await rust_delete_future(self._connection, name)
        except Exception as e:
            raise SurrealDbError(e)
