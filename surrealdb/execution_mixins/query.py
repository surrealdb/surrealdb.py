"""
This file defines the interface between python and the Rust SurrealDB library for querying the database.
queries can be found in the link below:
https://github.com/surrealdb/surrealdb/blob/main/lib/tests/fetch.rs
"""
import json
from typing import List

from surrealdb.rust_surrealdb import blocking_query
from surrealdb.errors import SurrealDbError


class QueryMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for creating a document.
    """
    def query(self: "SurrealDB", query: str) -> List[dict]:
        """
        queries the database.

        :param query: the query to run on the database

        :return: None
        """
        try:
            return json.loads(blocking_query(self._connection, query))[0]
        except Exception as e:
            SurrealDbError(e)
