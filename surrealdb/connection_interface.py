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
from surrealdb.rust_surrealdb import blocking_close_connection
from surrealdb.rust_surrealdb import blocking_check_connection

# import the mixins for operations for the connection
from surrealdb.execution_mixins.create import CreateMixin


class SurrealDB(
    CreateMixin
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
        self._connection: str = self._make_connection(url=url, existing_connection_id=existing_connection_id)
        self._keep_connection: bool = keep_connection

    def __del__(self):
        """
        The destructor for the SurrealDB class (fires when the object is destroyed).

        :return: None
        """
        if self._keep_connection is False:
            self.close()

    def __atexit__(self):
        """
        The atexit function for the SurrealDB class (fires if the system crashes).

        :return: None
        """
        if self._keep_connection is False:
            self.close()

    def _make_connection(self, url: str, existing_connection_id: Optional[str]) -> str:
        """
        Makes a connection to SurrealDB or establishes an existing connection.

        :param url: the url to connect to SurrealDB with
        :param existing_connection_id: the existing connection id to use instead of making a new connection
        :return: the connection id of the connection
        """
        if existing_connection_id is None:
            return blocking_make_connection(url)
        if blocking_check_connection(existing_connection_id) is False:
            raise ValueError("Connection ID is invalid")
        else:
            return existing_connection_id
    
    def close(self) -> None:
        """
        Closes the connection to SurrealDB.

        :return: None
        """
        blocking_close_connection(self._connection)

    def check_connection(self) -> bool:
        """
        Checks if the connection to SurrealDB is still open.

        :return: True if the connection is open, False otherwise
        """
        return blocking_check_connection(self._connection)
