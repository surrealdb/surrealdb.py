"""
This file defines the interface for the AsyncSurrealDB.

# Usage
The database can be used by the following code:
```python
from surrealdb.async_surrealdb import AsyncSurrealDB

db = SurrealDB(url="ws://localhost:8080")
await db.connect()
await db.use("ns", "db_name")
```
It can also be used as a context manager:
```python
from surrealdb.async_surrealdb import AsyncSurrealDB

async with SurrealDB("ws://localhost:8080") as db:
    await db.use("ns", "db_name")
```
"""

import uuid
from typing import Optional, TypeVar

from surrealdb.connection.constants import DEFAULT_CONNECTION_URL
from surrealdb.connection.factory import create_connection_factory


_Self = TypeVar('_Self', bound='SurrealDB')


class SurrealDB:
    """This class is responsible for managing the connection to SurrealDB and managing operations on the connection."""

    def __init__(self, url: Optional[str] = None) -> None:
        """
        The constructor for the SurrealDB class.

        :param url: the url to connect to SurrealDB with
        """
        if url is None:
            url = DEFAULT_CONNECTION_URL

        self.__connection = create_connection_factory(url)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def connect(self) -> _Self:
        """Connect to SurrealDB."""
        await self.__connection.connect()
        return self

    async def close(self):
        """Close connection to SurrealDB."""
        await self.__connection.close()

    async def use(self, namespace: str, database: str) -> None:
        """
        Uses the given namespace and database in the connection.

        :param namespace: the namespace to use
        :param database: the database to use
        :return: None
        """

        await self.__connection.use(namespace=namespace, database=database)

    async def sign_in(self, username: str, password: str) -> str:
        """
        Signs in to the database.

        :param password: the password to sign in with
        :param username: the username to sign in with

        :return: str
        """

        token = await self.__connection.send('signin', {'user': username, 'pass': password})
        self.__connection.set_token(token)

        return token

    async def sign_up(self, username: str, password: str) -> str:
        """
        Sign up a user to the database.

        :param password: the password to sign up with
        :param username: the username to sign up with

        :return: str
        """

        token = await self.__connection.send('signup', {'user': username, 'pass': password})
        self.__connection.set_token(token)

        return token

    async def authenticate(self, jwt: str) -> None:
        """
        Authenticates a JWT.

        :param jwt: the JWT to authenticate
        :return: None
        """

        await self.__connection.send('authenticate', jwt)
        self.__connection.set_token(jwt)

    async def invalidate(self, jwt: str) -> None:
        """
        Invalidates a valid JWT.

        :param jwt: the JWT to invalidate
        :return: None
        """

        await self.__connection.send('invalidate', jwt)
        self.__connection.set_token()

    async def info(self) -> dict:
        """
        This returns the record of an authenticated record user.

        :return: dict
        """

        return await self.__connection.send('info')

    async def version(self) -> str:
        """
        This returns the version of the Server backend.

        :return: str
        """

        return await self.__connection.send('version')

    async def set(self, name: str, value) -> _Self:
        await self.__connection.send('let', name, value)
        return self

    async def unset(self, name: str) -> _Self:
        await self.__connection.send('unset', name)
        return self

    async def query(self):
        """
        queries the database.

        :param query: the query to run on the database

        :return: None
        """
        pass

    async def create(self):
        """
        Creates a new document in the database.

        :param name: the name of the document to create
        :param data: the data to store in the document

        :return: None
        """
        pass

    async def select(self):
        """
        Performs a select query on the database for a particular resource.

        :param resource: the resource to select from

        :return: the result of the select
        """
        pass

    async def insert(self):
        pass

    async def patch(self):
        """
        Patches the given resource with the given data.

        :param resource: the resource to update
        :param data: the data to patch the resource with
        :return: the updated resource such as an individual row or a list of rows
        """
        pass

    async def update(self):
        """
        Updates the given resource with the given data.

        :param resource: the resource to update
        :param data: the data to update the resource with
        :return: the updated resource such as an individual row or a list of rows
        """
        pass

    async def upsert(self):
        pass

    async def delete(self):
        """
        Deletes a document in the database.

        :param name: the name of the document to delete

        :return: the record or records that were deleted
        """
        pass

    async def merge(self):
        """
        Merges the given resource with the given data.

        :param resource: the resource to update
        :param data: the data to merge the resource with
        :return: the updated resource such as an individual row or a list of rows
        """
        pass

    async def relate(self):
        pass

    async def insert_relation(self):
        pass

