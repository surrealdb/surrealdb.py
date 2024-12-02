"""
This file defines the interface for the AsyncSurrealDB.

# Usage
The database can be used by the following code:
```python
from surrealdb.async_surrealdb import AsyncSurrealDB

db = SurrealDB(url="ws://localhost:8080")
db.connect()
db.use("ns", "db_name")
```
It can also be used as a context manager:
```python
from surrealdb.surrealdb import SurrealDB

with SurrealDB("ws://localhost:8080") as db:
    db.use("ns", "db_name")
```
"""

import asyncio
import uuid
from typing import Union, List
from typing_extensions import Self

from surrealdb.asyncio_runtime import AsyncioRuntime
from surrealdb.constants import (
    DEFAULT_CONNECTION_URL,
    METHOD_KILL,
    METHOD_LIVE,
    METHOD_MERGE,
    METHOD_DELETE,
    METHOD_UPSERT,
    METHOD_UPDATE,
    METHOD_PATCH,
    METHOD_INSERT,
    METHOD_CREATE,
    METHOD_QUERY,
    METHOD_SELECT,
    METHOD_VERSION,
    METHOD_INFO,
    METHOD_INVALIDATE,
    METHOD_AUTHENTICATE,
    METHOD_SIGN_UP,
    METHOD_SIGN_IN,
)
from surrealdb.connection_factory import create_connection_factory
from surrealdb.data import RecordID, Table, Patch


class SurrealDB:
    """This class is responsible for managing the connection to SurrealDB and managing operations on the connection."""

    def __init__(self, url: str | None = None) -> None:
        """
        The constructor for the SurrealDB class.

        :param url: the url to connect to SurrealDB with
        """
        if url is None:
            url = DEFAULT_CONNECTION_URL

        self.__connection = create_connection_factory(url)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    def connect(self) -> Self:
        """Connect to SurrealDB."""
        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(self.__connection.connect())

        return self

    def close(self):
        """Close connection to SurrealDB."""
        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(self.__connection.close())

    def use(self, namespace: str, database: str) -> None:
        """
        Uses the given namespace and database in the connection.

        :param namespace: the namespace to use
        :param database: the database to use
        :return: None
        """
        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(
            self.__connection.use(namespace=namespace, database=database)
        )

    def sign_in(self, username: str, password: str) -> str:
        """
        Signs in to the database.

        :param password: the password to sign in with
        :param username: the username to sign in with

        :return: str
        """

        async def async_fn(_username: str, _password: str):
            _token = await self.__connection.send(
                METHOD_SIGN_IN, {"user": _username, "pass": _password}
            )
            self.__connection.set_token(_token)
            return _token

        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(async_fn(username, password))

    def sign_up(self, username: str, password: str) -> str:
        """
        Sign up a user to the database.

        :param password: the password to sign up with
        :param username: the username to sign up with

        :return: str
        """

        async def async_fn(_username: str, _password: str):
            _token = await self.__connection.send(
                METHOD_SIGN_UP, {"user": _username, "pass": _password}
            )
            self.__connection.set_token(_token)
            return _token

        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(async_fn(username, password))

    def authenticate(self, token: str) -> None:
        """
        Authenticates a JWT.

        :param token: the JWT to authenticate
        :return: None
        """

        async def async_fn(_jwt: str):
            _token = await self.__connection.send(METHOD_AUTHENTICATE, _jwt)
            self.__connection.set_token(_token)
            return _token

        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(async_fn(token))

    def invalidate(self, token: str) -> None:
        """
        Invalidates a valid JWT.

        :param token: the JWT to invalidate
        :return: None
        """

        async def async_fn(_token: str):
            await self.__connection.send(METHOD_INVALIDATE, _token)
            self.__connection.set_token()
            return _token

        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(async_fn(token))

    def info(self) -> dict:
        """
        This returns the record of an authenticated record user.

        :return: dict
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(self.__connection.send(METHOD_INFO))

    def version(self) -> str:
        """
        This returns the version of the Server backend.

        :return: str
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_VERSION)
        )

    def set(self, name: str, value) -> None:
        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(self.__connection.set(name, value))

    def unset(self, name: str) -> None:
        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(self.__connection.unset(name))

    def select(self, what: Union[str, Table, RecordID]) -> Union[List[dict], dict]:
        """
        Performs a select query on the database for a particular resource.

        :param what: the resource to select from.

        :return: the result of the select
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_SELECT, what)
        )

    def query(self, query: str, variables: dict = {}) -> List[dict]:
        """
        Queries sends a custom SurrealQL query.

        :param query: The query to execute against SurrealDB. Queries are seperated by semicolons.
        :param variables: A set of variables used by the query

        :return: An array of query results
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_QUERY, query, variables)
        )

    def create(self, thing: Union[str, RecordID, Table], data: Union[List[dict], dict]):
        """
        Creates a record either with a random or specified ID

        :param thing: The Table or Record ID to create. Passing just a table will result in a randomly generated ID
        :param data: The data to store in the document

        :return: None
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_CREATE, thing, data)
        )

    def insert(self, thing: Union[str, Table], data: Union[List[dict], dict]):
        """
        Inserts a record either with a random or specified ID.

        :param thing: The table to insert in to
        :param data: One or multiple record(s)
        :return:
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_INSERT, thing, data)
        )

    def patch(
        self,
        thing: Union[str, RecordID, Table],
        patches: List[Patch],
        diff: bool = False,
    ):
        """
        Patches the given resource with the given data.

        :param thing: The Table or Record ID to patch.
        :param patches: An array of patches following the JSON Patch specification
        :param diff: A boolean representing if just a diff should be returned.
        :return: the patched resource such as a record/records or patches
        """
        if diff is None:
            diff = False

        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_PATCH, thing, patches, diff)
        )

    def update(self, thing: Union[str, RecordID, Table], data: dict):
        """
        Updates replaces either all records in a table or a single record with specified data

        :param thing: The Table or Record ID to update.
        :param data: The content for the record
        :return: the updated resource such as an individual row or a list of rows
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_UPDATE, thing, data)
        )

    def upsert(self, thing: Union[str, RecordID, Table], data: dict):
        """
        Upsert replaces either all records in a table or a single record with specified data

        :param thing: The Table or Record ID to upsert.
        :param data: The content for the record
        :return: the upsert-ed records such as an individual row or a list of rows
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_UPSERT, thing, data)
        )

    def delete(self, thing: Union[str, RecordID, Table]) -> Union[List[dict], dict]:
        """
        Deletes either all records in a table or a single record.

        :param thing: The Table or Record ID to update.

        :return: the record or records that were deleted
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_DELETE, thing)
        )

    def merge(
        self, thing: Union[str, RecordID, Table], data: dict
    ) -> Union[List[dict], dict]:
        """
        Merge specified data into either all records in a table or a single record

        :param thing: The Table or Record ID to merge into.
        :param data: The content for the record.
        :return: the updated resource such as an individual row or a list of rows
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_MERGE, thing, data)
        )

    def live(self, thing: Union[str, Table], diff: bool = False) -> uuid.UUID:
        """
        Live initiates a live query for a specified table name.

        :param thing: The Table tquery.
        :param diff: If set to true, live notifications will contain an array of JSON Patches instead of the entire record
        :return: the live query uuid
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_LIVE, thing, diff)
        )

    def live_notifications(self, live_id: uuid.UUID) -> asyncio.Queue:
        """
        Live notification returns a queue that receives notification messages from the back end.

        :param live_id: The live id for the live query
        :return: the notification queue
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.live_notifications(live_id)
        )

    def kill(self, live_query_id: uuid.UUID) -> None:
        """
        This kills an active live query

        :param live_query_id: The UUID of the live query to kill.
        """
        loop_manager = AsyncioRuntime()
        return loop_manager.loop.run_until_complete(
            self.__connection.send(METHOD_KILL, live_query_id)
        )
