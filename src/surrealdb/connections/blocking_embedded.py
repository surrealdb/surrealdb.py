"""
Blocking embedded SurrealDB connection using the Rust extension with CBOR messaging.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from uuid import UUID

from surrealdb_embedded import SyncEmbeddedDB

from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingWsSurrealConnection,
)
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import mapped_engine_errors
from surrealdb.data.cbor import decode
from surrealdb.data.types.table import Table
from surrealdb.errors import UnsupportedFeatureError
from surrealdb.request_message.message import RequestMessage
from surrealdb.types import Value

# The embedded engine builds no live-query notification channel (the Rust
# extension reports ``LQ_SUPPORT = false``), so there is nowhere for
# notifications to arrive.
_NO_LIVE_QUERIES = (
    "Live queries are only supported for WebSocket connections; the embedded "
    "engine has no notification channel to deliver them over"
)


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
        # The parent constructor opens nothing - it only sets attributes - and
        # running it is what guarantees every inherited method finds the state
        # it expects. Hand-copying a subset of it is how ``subscribe_live``
        # came to fail with a bare ``AttributeError`` on ``live_queues``.
        super().__init__(url)
        # Embedded URLs address a local engine, not an HTTP endpoint, so they
        # keep their original form instead of the parent's ``/rpc`` suffix.
        self.raw_url = url

        # Embedded database handle
        with mapped_engine_errors("opening the database"):
            self._db: SyncEmbeddedDB = SyncEmbeddedDB(url)

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
            with mapped_engine_errors("opening the database"):
                self._db = SyncEmbeddedDB(url)

        with mapped_engine_errors("connecting"):
            self._db.connect()

    def close(self) -> None:
        """Closes the connection to the database.

        Example:
            db.close()
        """
        with mapped_engine_errors("closing"):
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
        with mapped_engine_errors(process):
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

    def attach(self) -> UUID:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def detach(self, session_id: Any) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def begin(self, session_id: Any = None) -> UUID:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def commit(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def cancel(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    def new_session(self) -> BlockingSurrealSession:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    # Live queries -----------------------------------------------------------
    #
    # Refused up front rather than inherited. ``live`` and ``kill`` reached the
    # engine and came back as "Unable to perform the realtime query", which
    # says nothing about why; ``subscribe_live`` would have read notifications
    # off a websocket this connection does not have.

    def live(
        self,
        table: str | Table,
        diff: bool = False,
        session_id: UUID | None = None,
    ) -> UUID:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    def kill(
        self,
        query_uuid: str | UUID,
        session_id: UUID | None = None,
    ) -> None:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    def subscribe_live(
        self,
        query_uuid: str | UUID,
    ) -> Generator[dict[str, Value], None, None]:
        # Deliberately not a generator function: raising on the call itself
        # reports the problem where it is made, rather than on the first
        # ``next()`` somewhere further away.
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    # All other methods (query, select, create, update, delete, merge, patch, etc.)
    # are inherited from BlockingWsSurrealConnection and work automatically via _send()!
