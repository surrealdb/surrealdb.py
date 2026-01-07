"""
Blocking embedded SurrealDB connection using the Rust extension with CBOR messaging.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from surrealdb._surrealdb_ext import SyncEmbeddedDB
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.url import Url
from surrealdb.data.cbor import decode
from surrealdb.request_message.message import RequestMessage


class BlockingEmbeddedSurrealConnection(BlockingWsSurrealConnection):
    """
    A blocking embedded SurrealDB connection using the Rust extension.

    This class inherits all methods from BlockingWsSurrealConnection and only
    overrides the connection management and message sending to use the embedded
    database instead of WebSocket.

    Attributes:
        url: The URL of the embedded database (mem:// or file://).
        id: The ID of the connection.
    """

    def __init__(self, url: str) -> None:
        """
        Constructor for the BlockingEmbeddedSurrealConnection class.

        :param url: (str) The URL of the embedded database (mem:// or file://).
        """
        # Initialize without calling super().__init__() to avoid WebSocket setup
        self.url: Url = Url(url)
        self.raw_url: str = url
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.id: str = str(uuid.uuid4())
        self.token: str | None = None

        # Embedded database handle
        self._db: SyncEmbeddedDB = SyncEmbeddedDB(url)

        # Not used for embedded, but needed for compatibility
        self.socket = None
        self._lock: threading.Lock = threading.Lock()

    def __enter__(self) -> BlockingEmbeddedSurrealConnection:
        """Context manager entry - connect to the embedded database."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Context manager exit - close the connection."""
        self.close()

    def connect(self, url: str | None = None) -> None:
        """Connects to the embedded database endpoint.

        Args:
            url: Optional new URL to connect to.

        Example:
            db.connect()
        """
        if url is not None:
            self.url = Url(url)
            self.raw_url = url
            self._db = SyncEmbeddedDB(url)

        self._db.connect()

    def close(self) -> None:
        """Closes the connection to the database.

        Example:
            db.close()
        """
        self._db.close()
        self.socket = None

    def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        """
        Send a message to the embedded database using CBOR encoding.

        This method overrides the WebSocket _send to use the Rust extension
        instead of a network connection, while maintaining the same CBOR
        message format for perfect compatibility.

        Args:
            message: The request message to send.
            process: Description of the operation being performed.
            bypass: Whether to bypass error checking.

        Returns:
            The decoded response dictionary.
        """
        # Encode message to CBOR (reuses existing WebSocket CBOR encoding)
        cbor_request = message.WS_CBOR_DESCRIPTOR

        # Execute via Rust extension
        cbor_response_bytes = self._db.execute(cbor_request)

        # Decode CBOR response (reuses existing CBOR decoding)
        response = decode(cbor_response_bytes)

        # Check for errors (inherited method from UtilsMixin)
        if not bypass:
            self.check_response_for_error(response, process)

        # Ensure response is a dict
        if not isinstance(response, dict):
            return {}

        return response

    # All other methods (query, select, create, update, delete, merge, patch, etc.)
    # are inherited from BlockingWsSurrealConnection and work automatically via _send()!
