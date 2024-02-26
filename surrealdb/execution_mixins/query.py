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
from surrealdb.asyncio_runtime import AsyncioRuntime 


class QueryMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """

    @staticmethod
    def convert_nested_json_strings(data):
        """
        For some reason, if there is a dict in the query result, the value is a string. This does not happen with the
        raw async method but the implementation is the same. For now this method will be used to convert the string
        values to JSON in the query result to valid JSON but we should look into why this is happening.

        :param data: The query result data to be checked
        :return: The processed query data
        """
        for item in data:
            for key, value in item.items():
                if isinstance(value, str):  # Check if the value is a string
                    try:
                        # Attempt to load the string as JSON
                        item[key] = json.loads(value)
                    except json.JSONDecodeError:
                        # If it's not a valid JSON string, do nothing
                        pass
        return data

    def query(self: "SurrealDB", query: str) -> List[dict]:
        """
        queries the database.

        :param query: the query to run on the database

        :return: None
        """
        async def _query(connection, query):
            return await rust_query_future(connection, query)

        try:
            loop_manager = AsyncioRuntime()
            return self.convert_nested_json_strings(
                json.loads(loop_manager.loop.run_until_complete(_query(self._connection, query)))[0]
            )
        except Exception as e:
            raise SurrealDbError(e)

    def select(self: "SurrealDB", resource: str) -> Union[List[dict], dict]:
        """
        Performs a select query on the database for a particular resource.

        :param resource: the resource to select from

        :return: the result of the select
        """
        async def _select(connection, resource):
            return await rust_select_future(connection, resource)

        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(_select(self._connection, resource))
