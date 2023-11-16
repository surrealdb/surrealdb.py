"""
This file defines the interface for the SurrealDB connection and operations on that connection.

# Usage
The connection can be used by the following code:
```python
from surrealdb.connection_interface import SurrealDB

connection = SurrealDB(url="ws://localhost:8080")
```
Existing connections can be used by the following code:
```python
from surrealdb.connection_interface import SurrealDB

connection = SurrealDB(url="ws://localhost:8080", existing_connection_id="some_connection_id")
```
"""
import uuid
from typing import Optional

from surrealdb.rust_surrealdb import rust_make_connection_future
from surrealdb.rust_surrealdb import rust_use_namespace_future
from surrealdb.rust_surrealdb import rust_use_database_future
from surrealdb.asyncio_runtime import AsyncioRuntime

from surrealdb.execution_mixins.auth import SignInMixin

# import the mixins for operations for the connection
from surrealdb.execution_mixins.create import CreateMixin
from surrealdb.execution_mixins.query import QueryMixin
from surrealdb.execution_mixins.set import SetMixin
from surrealdb.execution_mixins.update import UpdateMixin


class ConnectionController(type):

    instances = {}
    main_connection = None

    def remove_connection(cls, connection_id: str) -> None:
        """
        Closes the connection with the given connection id.

        :param connection_id: the id of the connection to close

        :return: None
        """
        del cls.instances[connection_id]

    def __call__(cls, *args, **kwargs):

        # establish the main connection
        if kwargs.get("main_connection", False) is True:
            if cls.main_connection is None:
                instance = super(ConnectionController, cls).__call__(*args, **kwargs)
                cls.main_connection = instance
            return cls.main_connection
        if len(args) > 4 and args[3] is True:
            if cls.main_connection is None:
                instance = super(ConnectionController, cls).__call__(*args, **kwargs)
                cls.main_connection = instance
            return cls.main_connection

        # get the existing connection
        if kwargs.get("existing_connection_id", None) is not None:
            return cls.instances[kwargs["existing_connection_id"]]
        if len(args) > 2 and args[2] is not None and args[2] in cls.instances:
            return cls.instances[args[2]]

        # store the connection
        if kwargs.get("keep_connection", False) is True:
            instance = super(ConnectionController, cls).__call__(*args, **kwargs)
            cls.instances[instance.id] = instance
            return instance
        if len(args) > 1 and args[1] is True:
            instance = super(ConnectionController, cls).__call__(*args, **kwargs)
            cls.instances[instance.id] = instance
            return instance

        return super(ConnectionController, cls).__call__(*args, **kwargs)


class SurrealDB(
    CreateMixin,
    SignInMixin,
    SetMixin,
    QueryMixin,
    UpdateMixin,
    metaclass=ConnectionController
):
    """
    This class is responsible for managing the connection to SurrealDB and managing operations on the connection.
    """
    def __init__(self,
                 url: Optional[str] = None,
                 keep_connection: Optional[bool] = False,
                 existing_connection_id: Optional[str] = None,
                 main_connection: Optional[bool] = False
                 ) -> None:
        """
        The constructor for the SurrealDB class.

        :param url: the url to connect to SurrealDB with
        :param keep_connection: wether or not to keep the connection open after this object is destroyed
        :param existing_connection_id: the existing connection id to use instead of making a new connection
        """
        self._connection: Optional[str] = self._make_connection(url=url)
        self.id: str = str(uuid.uuid4()) if existing_connection_id is None else existing_connection_id
        self.keep_connection: bool = keep_connection
        self.main_connection: bool = main_connection

    def _make_connection(self, url: str) -> str:
        """
        Makes a connection to SurrealDB or establishes an existing connection.

        :param url: the url to connect to SurrealDB with
        :param existing_connection_id: the existing connection id to use instead of making a new connection
        :return: the connection id of the connection
        """
        async def async_make_connection(url: str):
            return await rust_make_connection_future(url)

        loop_manager = AsyncioRuntime()
        connection_id = loop_manager.loop.run_until_complete(async_make_connection(url))
        return connection_id

    def use_namespace(self, namespace: str) -> None:
        """
        Uses the given namespace in the connection.

        :param namespace: the namespace to use
        :return: None
        """
        async def async_use_namespace(namespace: str):
            return await rust_use_namespace_future(self._connection, namespace)

        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(async_use_namespace(namespace))

    def use_database(self, database: str) -> None:
        """
        Uses the given database in the connection.

        :param database: the database to use
        :return: None
        """
        async def async_use_database(database: str):
            return await rust_use_database_future(self._connection, database)

        loop_manager = AsyncioRuntime()
        loop_manager.loop.run_until_complete(async_use_database(database))
