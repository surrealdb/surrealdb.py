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
from typing import Optional

from surrealdb.rust_surrealdb import blocking_make_connection

# import the mixins for operations for the connection
from surrealdb.execution_mixins.create import CreateMixin
from surrealdb.execution_mixins.auth import SignInMixin
# from surrealdb.execution_mixins.set import SetMixin


class SurrealDB(
    CreateMixin,
    SignInMixin,
    # SetMixin,
):
    """
    This class is responsible for managing the connection to SurrealDB and managing operations on the connection.
    """
    def __init__(self, url: str, keep_connection: bool = False, existing_connection_id: Optional[str] = None) -> None:
        """
        The constructor for the SurrealDB class.

        :param url: the url to connect to SurrealDB with
        :param keep_connection: whether or not to keep the connection open after this object is destroyed
        :param existing_connection_id: the existing connection id to use instead of making a new connection
        """
        self._connection: str = self._make_connection(url=url)

    def _make_connection(self, url: str) -> str:
        """
        Makes a connection to SurrealDB or establishes an existing connection.

        :param url: the url to connect to SurrealDB with
        :param existing_connection_id: the existing connection id to use instead of making a new connection
        :return: the connection id of the connection
        """
        return blocking_make_connection(url)
