"""This file defines the interface between python and the Rust SurrealDB library for creating a document."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Union

from surrealdb.errors import SurrealDbError
from surrealdb.rust_surrealdb import (
    rust_create_future,
    rust_delete_future,
)

if TYPE_CHECKING:
    from surrealdb.connection_interface import SurrealDB


class AsyncCreateMixin:
    """This class is responsible for the interface between python and the Rust SurrealDB library for creating a document."""

    async def create(self: SurrealDB, name: str, data: dict) -> None:
        """
        Creates a new document in the database.

        :param name: the name of the document to create
        :param data: the data to store in the document

        :return: None
        """
        try:
            return json.loads(
                await rust_create_future(self._connection, name, json.dumps(data))
            )
        except Exception as e:
            raise SurrealDbError(e) from None

    async def delete(self: SurrealDB, name: str) -> Union[List[dict], dict]:
        """
        Deletes a document in the database.

        :param name: the name of the document to delete

        :return: the record or records that were deleted
        """
        try:
            return await rust_delete_future(self._connection, name)
        except Exception as e:
            raise SurrealDbError(e) from None
