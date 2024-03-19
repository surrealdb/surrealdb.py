"""This file defines the interface between python and the Rust SurrealDB library for setting a key value."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from surrealdb.asyncio_runtime import AsyncioRuntime
from surrealdb.errors import SurrealDbError
from surrealdb.rust_surrealdb import (
    rust_set_future,
)

if TYPE_CHECKING:
    from surrealdb.connection_interface import SurrealDB


class SetMixin:
    """This class is responsible for the interface between python and the Rust SurrealDB library for creating a document."""

    def set(self: SurrealDB, key: str, value: dict) -> None:
        """
        Creates a new document in the database.

        :param name: the name of the document to create
        :param data: the data to store in the document

        :return: None
        """

        async def _set(connection, key, value):
            return await rust_set_future(connection, key, json.dumps(value))

        json_str = None
        try:
            json_str = json.dumps(value)
        except json.JSONEncodeError as e:
            print(f"cannot serialize value {type(value)} to json")
            raise SurrealDbError(e) from None

        if json_str is not None:
            try:
                loop_manager = AsyncioRuntime()
                loop_manager.loop.run_until_complete(
                    _set(self._connection, key, json_str)
                )
            except Exception as e:
                raise SurrealDbError(e) from None
