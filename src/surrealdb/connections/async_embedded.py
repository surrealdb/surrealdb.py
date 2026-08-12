"""
Async embedded SurrealDB connection using the Rust extension with CBOR messaging.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any
from uuid import UUID

from surrealdb_embedded import AsyncEmbeddedDB

from surrealdb.connections.async_ws import AsyncSurrealSession, AsyncWsSurrealConnection
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


class AsyncEmbeddedSurrealConnection(AsyncWsSurrealConnection):
    """
    An async embedded SurrealDB connection using the Rust extension.

    This class inherits all methods from AsyncWsSurrealConnection and only
    overrides the connection management and message sending to use the embedded
    database instead of WebSocket.

    Attributes:
        url: The URL of the embedded database (mem:// or file://).
        id: The ID of the connection.
    """

    def __init__(self, url: str) -> None:
        """
        Constructor for the AsyncEmbeddedSurrealConnection class.

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
        self.id: str = str(uuid.uuid4())
        self.namespace: str | None = None
        self.database: str | None = None
        self.vars: dict[str, Any] = dict()

        # Embedded database handle
        with mapped_engine_errors("opening the database"):
            self._db: AsyncEmbeddedDB = AsyncEmbeddedDB(url)
        # Whether `close()` has shut the engine down - see `connect`.
        self._closed: bool = False

    async def __aenter__(self) -> AsyncEmbeddedSurrealConnection:
        """Context manager entry - connect to the embedded database."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - close the connection."""
        await self.close()

    async def connect(self, url: str | None = None) -> None:
        """Connect to the embedded database endpoint.

        Idempotent while the engine is open, and it reopens one that
        :meth:`close` shut down. ``close()`` shuts the datastore down for good -
        the handle it leaves behind answers every request with "Database
        connection is closed" - while ``connect()`` on the native side is a
        no-op that reports success, so reconnecting *said* it had worked and
        then failed on the next query. The websocket transports have always
        reopened here; this makes the embedded engine agree.

        A reopened ``memory://`` database starts empty, because the one that
        was closed is gone. That mirrors a reconnected websocket getting a new,
        unauthenticated server-side session: closing a connection ends what was
        behind it. A file-backed engine (``file://``, ``surrealkv://``) reopens
        its store and keeps its data.

        Args:
            url: Optional new URL to connect to.

        Example:
            await db.connect()
        """
        if url is not None:
            self.url = Url(url)
            self.raw_url = url
            with mapped_engine_errors("opening the database"):
                self._db = AsyncEmbeddedDB(url)
            self._closed = False
        elif self._closed:
            with mapped_engine_errors("opening the database"):
                self._db = AsyncEmbeddedDB(self.raw_url)
            self._closed = False

        with mapped_engine_errors("connecting"):
            await self._db.connect()

    async def close(self) -> None:
        """Closes the connection to the database.

        Idempotent, and leaves the connection reusable: :meth:`connect` opens a
        fresh engine afterwards.

        Example:
            await db.close()
        """
        with mapped_engine_errors("closing"):
            await self._db.close()
        self._closed = True

    async def _send(
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
            cbor_response_bytes = await self._db.execute(cbor_request)

        # Decode CBOR response (reuses existing CBOR decoding)
        response = decode(cbor_response_bytes)

        # Check for errors (inherited method from UtilsMixin)
        if not bypass:
            self.check_response_for_error(response, process)

        # Ensure response is a dict
        if not isinstance(response, dict):
            return {}

        return response

    async def attach(self) -> UUID:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def detach(self, session_id: Any) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def begin(self, session_id: Any = None) -> UUID:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def commit(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def cancel(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def new_session(self) -> AsyncSurrealSession:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    # Live queries -----------------------------------------------------------
    #
    # Refused up front rather than inherited. ``live`` and ``kill`` reached the
    # engine and came back as "Unable to perform the realtime query", which
    # says nothing about why; ``subscribe_live`` would have waited on a queue
    # the background reader this connection does not run would have filled.

    async def live(
        self,
        table: str | Table,
        diff: bool = False,
        session_id: UUID | None = None,
    ) -> UUID:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    async def kill(
        self,
        query_uuid: str | UUID,
        session_id: UUID | None = None,
    ) -> None:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    async def subscribe_live(
        self,
        query_uuid: str | UUID,
    ) -> AsyncGenerator[dict[str, Value], None]:
        raise UnsupportedFeatureError(_NO_LIVE_QUERIES)

    # All other methods (query, select, create, update, delete, merge, patch, etc.)
    # are inherited from AsyncWsSurrealConnection and work automatically via _send()!
