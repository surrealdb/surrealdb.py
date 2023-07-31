"""
This file defines the interface between python and the Rust SurrealDB library for updating rows in the database. 
"""
import json
from typing import List, Union

from surrealdb.rust_surrealdb import blocking_merge
from surrealdb.rust_surrealdb import blocking_update
from surrealdb.rust_surrealdb import blocking_patch

from surrealdb.errors import SurrealDbError


class UpdateMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """
    def update(self: "SurrealDB", resource: str, data: dict) -> Union[List[dict], dict]:
        """
        Updates the given resource with the given data.

        :param resource: the resource to update
        :param data: the data to update the resource with
        :return: the updated resource such as an individual row or a list of rows
        """
        try:
            return json.loads(blocking_update(self._connection, resource, data))
        except Exception as e:
            SurrealDbError(e)

    def merge(self: "SurrealDB", resource: str, data: dict) -> Union[List[dict], dict]:
        """
        Merges the given resource with the given data.

        :param resource: the resource to update
        :param data: the data to merge the resource with
        :return: the updated resource such as an individual row or a list of rows
        """
        try:
            return json.loads(blocking_merge(self._connection, resource, data))
        except Exception as e:
            SurrealDbError(e)

    def patch(self: "SurrealDB", resource: str, data: dict) -> Union[List[dict], dict]:
        """
        Patches the given resource with the given data.

        :param resource: the resource to update
        :param data: the data to patch the resource with
        :return: the updated resource such as an individual row or a list of rows
        """
        try:
            return json.loads(blocking_patch(self._connection, resource, data))
        except Exception as e:
            SurrealDbError(e)
