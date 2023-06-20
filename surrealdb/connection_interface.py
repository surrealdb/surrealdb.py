"""
This file defines the interface for the SurrealDB connection.
"""
from surrealdb.rust_surrealdb import blocking_make_connection
from surrealdb.rust_surrealdb import blocking_close_connection


class SurrealDB:

    def __init__(self, url: str, keep_connection: bool = False) -> None:
        self._connection: str = blocking_make_connection(url)
        self._keep_connection: bool = keep_connection

    def __del__(self):
        if self._keep_connection is False:
            self.close()

    def __atexit__(self):
        if self._keep_connection is False:
            self.close()
    
    def close(self) -> None:
        blocking_close_connection(self._connection)