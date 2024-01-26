"""
This file defines the interface between python and the Rust SurrealDB library for querying the database.
queries can be found in the link below:
https://github.com/surrealdb/surrealdb/blob/main/lib/tests/fetch.rs
"""
import json
from typing import List, Union

from surrealdb.rust_surrealdb import rust_query_future
from surrealdb.rust_surrealdb import rust_select_future

from surrealdb.errors import SurrealDbError


class AsyncQueryMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """
    async def query(self: "SurrealDB", query: str) -> List[dict]:
        """
        queries the database.

        :param query: the query to run on the database

        :return: None
        """
        try:
            return json.loads(await rust_query_future(self._connection, query))[0]
        except Exception as e:
            raise SurrealDbError(e)

    async def select(self: "SurrealDB", resource: str) -> Union[List[dict], dict]:
        """
        Performs a select query on the database for a particular resource.

        :param resource: the resource to select from

        :return: the result of the select
        """
        return await rust_select_future(self._connection, resource)
