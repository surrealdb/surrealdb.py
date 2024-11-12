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

from typing import Optional, TypeVar, Union, List

from surrealdb.constants import DEFAULT_CONNECTION_URL
from surrealdb.connection_factory import create_connection_factory
from surrealdb.data import RecordID, Table, Patch

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
    
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        # self.close()
        pass

    def connect(self) -> _Self:
        """Connect to SurrealDB."""
        # self.__connection.connect()

        return self

    def close(self):
        """Close connection to SurrealDB."""
        # self.__connection.close()
        pass

    def use(self, namespace: str, database: str) -> None:
        """
        Uses the given namespace and database in the connection.

        :param namespace: the namespace to use
        :param database: the database to use
        :return: None
        """

        # self.__connection.use(namespace=namespace, database=database)
        pass

    def sign_in(self, username: str, password: str) -> str:
        """
        Signs in to the database.

        :param password: the password to sign in with
        :param username: the username to sign in with

        :return: str
        """

        # token = self.__connection.send('signin', {'user': username, 'pass': password})
        # self.__connection.set_token(token)
        #
        # return token
        pass

    def sign_up(self, username: str, password: str) -> str:
        """
        Sign up a user to the database.

        :param password: the password to sign up with
        :param username: the username to sign up with

        :return: str
        """
        #
        # token = self.__connection.send('signup', {'user': username, 'pass': password})
        # self.__connection.set_token(token)
        #
        # return token
        pass

    def authenticate(self, jwt: str) -> None:
        """
        Authenticates a JWT.

        :param jwt: the JWT to authenticate
        :return: None
        """

        # self.__connection.send('authenticate', jwt)
        # self.__connection.set_token(jwt)
        pass

    def invalidate(self, jwt: str) -> None:
        """
        Invalidates a valid JWT.

        :param jwt: the JWT to invalidate
        :return: None
        """

        # self.__connection.send('invalidate', jwt)
        # self.__connection.set_token()
        pass

    def info(self) -> dict:
        """
        This returns the record of an authenticated record user.

        :return: dict
        """

        # return self.__connection.send('info')
        pass

    def version(self) -> str:
        """
        This returns the version of the Server backend.

        :return: str
        """

        # return self.__connection.send('version')
        pass

    def set(self, name: str, value) -> None:
        # self.__connection.send('let', name, value)
        pass

    def unset(self, name: str) -> None:
        # self.__connection.send('unset', name)
        pass

    def select(self, what: Union[str, Table, RecordID]) -> Union[List[dict], dict]:
        """
        Performs a select query on the database for a particular resource.

        :param what: the resource to select from.

        :return: the result of the select
        """
        # return self.__connection.send('select', what)
        pass

    def query(self, query: str, variables: dict = {}) -> List[dict]:
        """
        Queries sends a custom SurrealQL query.

        :param query: The query to execute against SurrealDB. Queries are seperated by semicolons.
        :param variables: A set of variables used by the query

        :return: An array of query results
        """
        # return self.__connection.send('query', query, variables)
        pass

    def create(self, thing: Union[str, RecordID, Table], data: Union[List[dict], dict]):
        """
        Creates a record either with a random or specified ID

        :param thing: The Table or Record ID to create. Passing just a table will result in a randomly generated ID
        :param data: The data to store in the document

        :return: None
        """
        # return self.__connection.send('create', thing, data)
        pass

    def insert(self, thing: Union[str, Table], data: Union[List[dict], dict]):
        """
        Inserts a record either with a random or specified ID.

        :param thing: The table to insert in to
        :param data: One or multiple record(s)
        :return:
        """
        # return self.__connection.send('insert', thing, data)
        pass

    def patch(self, thing: Union[str, RecordID, Table], patches: List[Patch], diff: Optional[bool] = False):
        """
        Patches the given resource with the given data.

        :param thing: The Table or Record ID to patch.
        :param patches: An array of patches following the JSON Patch specification
        :param diff: A boolean representing if just a diff should be returned.
        :return: the patched resource such as a record/records or patches
        """
        if diff is None:
            diff = False
        # return self.__connection.send('insert', thing, patches, diff)
        pass

    def update(self, thing: Union[str, RecordID, Table], data: dict):
        """
        Updates replaces either all records in a table or a single record with specified data

        :param thing: The Table or Record ID to update.
        :param data: The content for the record
        :return: the updated resource such as an individual row or a list of rows
        """
        # return self.__connection.send('update', thing, data)
        pass

    def upsert(self, thing: Union[str, RecordID, Table], data: dict):
        """
        Upsert replaces either all records in a table or a single record with specified data

        :param thing: The Table or Record ID to upsert.
        :param data: The content for the record
        :return: the upsert-ed records such as an individual row or a list of rows
        """
        # return self.__connection.send('upsert', thing, data)
        pass

    def delete(self, thing: Union[str, RecordID, Table]) -> Union[List[dict], dict]:
        """
        Deletes either all records in a table or a single record.

        :param thing: The Table or Record ID to update.

        :return: the record or records that were deleted
        """
        # return self.__connection.send('delete', thing)
        pass

    def merge(self, thing: Union[str, RecordID, Table], data: dict) -> Union[List[dict], dict]:
        """
        Merge specified data into either all records in a table or a single record

        :param thing: The Table or Record ID to merge into.
        :param data: The content for the record.
        :return: the updated resource such as an individual row or a list of rows
        """
        # return  self.__connection.send('update', thing, data)
        pass

