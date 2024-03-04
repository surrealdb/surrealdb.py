"""
This file defines the interface between python and the Rust SurrealDB library for creating a document.
"""
import json
from typing import List, Union

from surrealdb.rust_surrealdb import rust_create_future
from surrealdb.rust_surrealdb import rust_delete_future

from surrealdb.errors import SurrealDbError
from surrealdb.asyncio_runtime import AsyncioRuntime 


class CreateMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """
    def create(self: "SurrealDB", name: str, data: dict) -> dict:
        """
        Creates a new document in the database.

        :param name: the name of the document to create
        :param data: the data to store in the document

        :return: None
        """
        async def _create(connection, name, data):
            return await rust_create_future(connection, name, json.dumps(data))

        try:
            loop_manager = AsyncioRuntime()
            return json.loads(loop_manager.loop.run_until_complete(_create(self._connection, name, data)))
        except Exception as e:
            raise SurrealDbError(e)

    def delete(self: "SurrealDB", name: str) -> Union[List[dict], dict]:
        """
        Deletes a document in the database.

        :param name: the name of the document to delete

        :return: the record or records that were deleted
        """
        async def _delete(connection, name):
            return await rust_delete_future(connection, name)

        try:
            loop_manager = AsyncioRuntime()
            return loop_manager.loop.run_until_complete(_delete(self._connection, name))
        except Exception as e:
            raise SurrealDbError(e)
