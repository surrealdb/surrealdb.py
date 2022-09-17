from .clients.asynchronous import AsyncSurrealDBClient
from .clients.sync import SurrealDBClient

__version__ = "0.0.1"
__author__ = "tsunyoku"
__all__ = ["SurrealDBClient", "AsyncSurrealDBClient"]
