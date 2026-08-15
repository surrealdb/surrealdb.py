"""
A basic blocking connection to a SurrealDB instance.
"""

import logging
import queue
import threading
import time
import uuid
import weakref
from collections.abc import Generator
from types import TracebackType
from typing import Any, overload
from uuid import UUID

import websockets
import websockets.sync.client as ws_sync
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.protocol import State
from websockets.sync.client import ClientConnection

from surrealdb.connections.builders import (
    _UNSET,
    M,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
    _map_result,
)
from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import AUTH_FALLBACK_QUERY, UtilsMixin
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
    TransportTimeoutError,
    UnexpectedResponseError,
    parse_rpc_error,
)
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Tokens, Value, parse_auth_result

logger = logging.getLogger(__name__)

# How long ``subscribe_live`` blocks on a single socket read before releasing
# the connection lock so concurrent RPCs on the same socket can proceed.
_LIVE_RECV_TIMEOUT = 0.1

# The `action` SurrealDB puts on the notification it sends when a live query
# ends. It reports the end of the subscription rather than a change to the
# table - it carries no record and its `result` is None - so it terminates the
# generator instead of being handed to the consumer.
_LIVE_KILLED = "KILLED"

# Pushed into a subscriber's queue by `kill()` on this connection, so the
# generator ends without waiting for a server notification. 2.x never sends one.
_LIVE_KILLED_SENTINEL: dict[str, Any] = {"action": _LIVE_KILLED, "id": None}

# Upper bound on how long a single RPC waits for its reply. Without it the
# receive loop below blocks forever if the reply never arrives - which it does
# not when the server answers with a protocol-level error, since those carry no
# `id` to correlate. Matches the 30s total the HTTP transports give aiohttp and
# requests.
_RPC_RECV_TIMEOUT = 30.0


def _release_live_queue(
    live_queues: dict[str, list["queue.Queue[dict[str, Any]]"]],
    suid: str,
    notifications: "queue.Queue[dict[str, Any]]",
) -> None:
    """Deregister one subscriber's queue. Safe to call twice."""
    queues = live_queues.get(suid)
    if queues is None:
        return
    if notifications in queues:
        queues.remove(notifications)
    if not queues:
        live_queues.pop(suid, None)


class BlockingWsSurrealConnection(SyncTemplate, UtilsMixin):
    """
    A single blocking connection to a SurrealDB instance. To be used once and discarded.

    Attributes:
        url: The URL of the database to process queries for.
        user: The username to login on.
        password: The password to login on.
        namespace: The namespace that the connection will stick to.
        database: The database that the connection will stick to.
        id: The ID of the connection.
    """

    def __init__(self, url: str) -> None:
        """
        The constructor for the BlockingWsSurrealConnection class.

        :param url: (str) the URL of the database to process queries for.
        """
        self.url: Url = Url(url)
        self.raw_url: str = f"{self.url.raw_url}/rpc"
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.id: str = str(uuid.uuid4())
        self.token: str | None = None
        self.socket: ClientConnection | None = None
        self._lock: threading.Lock = threading.Lock()
        # Live-query notification queues keyed by live-query UUID string. A
        # ``subscribe_live`` consumer registers its own queue here so that
        # notifications ``_send`` reads while correlating an RPC reply are
        # handed off instead of being lost.
        self.live_queues: dict[str, list[queue.Queue[dict[str, Any]]]] = {}
        # Ids of requests abandoned by a timeout. The server still answers
        # them, and that reply arrives while some later request is waiting, so
        # it has to be recognised and dropped rather than mistaken for the
        # later request's reply.
        self._abandoned: set[str] = set()

    def _connect_socket(self) -> ClientConnection:
        """Open the websocket, mapping transport failures to SDK errors."""
        try:
            return ws_sync.connect(
                self.raw_url,
                max_size=None,
                subprotocols=[websockets.Subprotocol("cbor")],
            )
        except TimeoutError as exc:
            raise TransportTimeoutError(
                f"timed out connecting to {self.raw_url}: {exc}"
            ) from exc
        except (WebSocketException, OSError) as exc:
            raise ConnectionUnavailableError(
                f"could not connect to {self.raw_url}: {exc}"
            ) from exc

    def connect(self, url: str | None = None) -> None:
        """Open the websocket.

        ``_send`` connects lazily on first use, so this is not required - but
        it was the only connection class without it, which meant code written
        against the connection API raised ``AttributeError`` here while every
        other transport connected. Calling it eagerly also surfaces an
        unreachable endpoint at ``connect()`` rather than at the first query.

        Idempotent: a no-op when the socket is already open and *url* names
        the endpoint it is already connected to. Passing a *different* url
        re-points the connection, matching the other transports, and replaces
        an open socket - keeping it would leave the connection talking to the
        previous endpoint while reporting the new URL. Re-pointing costs the
        server-side session, so the same-url case is left alone: a defensive
        ``connect(url)`` must not quietly discard a completed ``signin()``.

        Serialised on the same lock ``_send`` uses, so two threads opening a
        connection at once produce one socket rather than one each. Unguarded,
        both saw ``socket is None``, both connected, and the loser's socket -
        with its ``recv_events`` and ``keepalive`` threads - was overwritten
        and leaked with no reference left to close it.
        """
        with self._lock:
            self._connect_locked(url)

    def _connect_locked(self, url: str | None = None) -> None:
        """The body of :meth:`connect`, called with ``self._lock`` held."""
        if url is not None:
            target = Url(url)
            target_raw = f"{target.raw_url}/rpc"
            if self.socket is not None and target_raw != self.raw_url:
                self.close()
            # Applied whether or not the socket had to go: skipping this when
            # the endpoint compares equal means any part of the URL the
            # comparison does not look at gets silently dropped.
            self.url = target
            self.raw_url = target_raw
            self.host = target.hostname
            self.port = target.port

        if self.socket is not None:
            if self.socket.state is State.OPEN:
                return
            # The socket object is still here but the connection behind it is
            # gone - the peer dropped it, or the server restarted. Returning
            # early left the connection permanently wedged: every later request
            # failed on the dead socket, and `connect()` - the documented way
            # to reopen one - silently refused to, so there was no way back
            # short of building a new connection. The async transport already
            # noticed this through its reader task; the blocking one has no
            # reader, so the socket's own state is what says so.
            self.close()

        self.socket = self._connect_socket()

    def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        # Use a lock to ensure thread-safe send/recv operations
        # This prevents race conditions when multiple threads share the same connection
        with self._lock:
            if self.socket is None:
                self.socket = self._connect_socket()

            # Correlate the reply to this request. Live-query notifications
            # carry no top-level "id" and may be delivered between our send and
            # our reply; route those to their live queue (if a subscriber is
            # registered, else drop) and keep reading, so a notification is
            # never returned as an RPC result.
            try:
                self.socket.send(message.WS_CBOR_DESCRIPTOR)
                deadline = time.monotonic() + _RPC_RECV_TIMEOUT
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        # The request was sent, so a reply is still coming.
                        # Remember it, or the next call reads this reply,
                        # mismatches the id and fails - and so does every call
                        # after it, permanently out of step by one.
                        self._abandoned.add(message.id)
                        raise TransportTimeoutError(
                            f"timed out while {process} on {self.raw_url}: no "
                            f"reply within {_RPC_RECV_TIMEOUT}s"
                        )
                    data = self.socket.recv(timeout=remaining)
                    response = self.decode_response(
                        data if isinstance(data, bytes) else data.encode(), process
                    )
                    response_id = response.get("id")
                    if response_id is None:
                        # A frame with no `id` is normally a live-query
                        # notification. A protocol-level error - a request the
                        # server could not parse or correlate - also arrives
                        # without one, and routing that to the notification
                        # path discarded the only reply this call would ever
                        # get, leaving the loop blocked on recv() forever.
                        if response.get("error") is not None:
                            self.check_response_for_error(response, process)
                        self._route_live_notification(response)
                        continue
                    if response_id in self._abandoned:
                        # The late reply to a timed-out request. Drop it and
                        # keep reading for this request's own reply.
                        self._abandoned.discard(response_id)
                        continue
                    if response_id != message.id:
                        raise UnexpectedResponseError(
                            f"Response ID mismatch: expected {message.id}, got "
                            f"{response_id}. This should not happen with proper "
                            "locking."
                        )
                    break
            except TimeoutError as exc:
                # `recv(timeout=...)` expiring is the path that actually fires;
                # the deadline check above only catches the next iteration.
                # Both have to record the id, or the abandoned reply is still
                # waiting in the socket for the next caller to trip over.
                self._abandoned.add(message.id)
                raise TransportTimeoutError(
                    f"timed out while {process} on {self.raw_url}: {exc}"
                ) from exc
            except (WebSocketException, OSError) as exc:
                raise ConnectionUnavailableError(
                    f"the connection to {self.raw_url} failed while {process}: {exc}"
                ) from exc

            if bypass is False:
                self.check_response_for_error(response, process)
            return response

    def _route_live_notification(self, response: dict[str, Any]) -> None:
        """Hand a live-query notification off to its subscriber queue.

        Notifications for a live query with no registered ``subscribe_live``
        queue are dropped. Called while holding ``self._lock``.
        """
        result = response.get("result")
        if not isinstance(result, dict):
            return
        live_id = result.get("id")
        if live_id is None:
            return
        for notifications in self.live_queues.get(str(live_id), []):
            notifications.put(result)

    def authenticate(self, token: str, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"token": token}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.AUTHENTICATE, **kwargs)
        self.id = message.id
        self._send(message, "authenticating")
        # Record the token as the connection identity so new_session() can
        # replay it — only when authenticating the connection, not a sub-session.
        if session_id is None:
            self.token = token

    def invalidate(self, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INVALIDATE, **kwargs)
        self.id = message.id
        self._send(message, "invalidating")
        self.token = None

    def signup(self, vars: dict[str, Value], session_id: UUID | None = None) -> Tokens:
        kwargs: dict[str, Any] = {"data": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_UP, **kwargs)
        self.id = message.id
        response = self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    def signin(self, vars: dict[str, Value], session_id: UUID | None = None) -> Tokens:
        kwargs: dict[str, Any] = {"params": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_IN, **kwargs)
        self.id = message.id
        response = self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    def info(self, session_id: UUID | None = None) -> Value:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INFO, **kwargs)
        self.id = message.id
        response = self._send(message, "getting database information", bypass=True)

        if response.get("error") is not None:
            # Record-auth sessions have no ROOT/NS/DB info; re-resolve the
            # authenticated record via `$auth`.
            if self._info_needs_auth_fallback(response):
                record = self._extract_auth_record(
                    self.query(AUTH_FALLBACK_QUERY, session_id=session_id).first()
                )
                if record is not None:
                    return record
            raise parse_rpc_error(response["error"])

        self.check_response_for_result(response, "getting database information")
        return response["result"]

    def use(
        self,
        namespace: str,
        database: str,
        session_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "namespace": namespace,
            "database": database,
        }
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.USE, **kwargs)
        self.id = message.id
        self._send(message, "use")

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncQueryBuilder:
        """Run SurrealQL and return a builder; trigger it explicitly.

        ``.execute()`` returns ``list[Value]`` (one entry per statement, always
        a list - the v3 fix for issue #232), ``.first()`` returns the first
        statement's result (or ``None``), and ``.into(cls)`` maps the statement
        results onto a dataclass / class.
        """
        return SyncQueryBuilder(
            executor=self._make_executor(session_id, txn_id),
            query=query,
            variables=vars,
        )

    def query_raw(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Any]:
        if vars is None:
            vars = {}
        kwargs: dict[str, Any] = {"query": query, "params": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.QUERY, **kwargs)
        self.id = message.id
        response = self._send(message, "query", bypass=True)
        return response

    def version(self, session_id: UUID | None = None) -> str:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.VERSION, **kwargs)
        self.id = message.id
        response = self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    def let(
        self,
        key: str,
        value: Value,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"key": key, "value": value}
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.LET, **kwargs)
        self.id = message.id
        self._send(message, "letting")

    def unset(
        self,
        key: str,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"params": [key]}
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.UNSET, **kwargs)
        self.id = message.id
        self._send(message, "unsetting")

    @overload
    def select(
        self,
        record: RecordID,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | None: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[M]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | list[M] | None: ...
    @overload
    def select(
        self,
        record: RecordID,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Value] | None: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[Value]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value: ...
    def select(
        self,
        record: RecordIdType,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Select records eagerly.

        A ``RecordID`` (or ``"table:id"``) returns the record dict, or ``None``
        when it is absent. A ``Table`` (or bare table-name string) returns the
        list of records. Pass ``into=Model`` to map each record onto ``Model``.
        """
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = self.query_raw(
            query, variables, session_id=session_id, txn_id=txn_id
        )
        self.check_response_for_error(response, "select")
        self._check_query_result(response["result"][0])
        result = response["result"][0]["result"]
        # Single-record targets (RecordID / "table:id") unwrap the one-element
        # result list to the record dict, or None when the record is absent.
        if self._is_single_record_operation(record):
            if isinstance(result, list):
                value: Any = result[0] if result else None
            else:
                value = result
        else:
            value = result
        if into is not None:
            return _map_result(into, value)
        return value

    def _make_executor(
        self,
        session_id: UUID | None,
        txn_id: UUID | None,
    ) -> Any:
        """Build an executor closure that calls query_raw with the right context."""

        def _executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
            return self.query_raw(query, params, session_id=session_id, txn_id=txn_id)

        return _executor

    # CRUD (eager) ----------------------------------------------------------
    #
    # Sync CRUD runs single-shot operations immediately: passing ``data``
    # executes and returns the result, while the no-data form returns a
    # ``SyncCrudBuilder`` so the caller can pick a clause. ``select`` and
    # ``delete`` always run eagerly.

    @overload
    def create(
        self,
        record: RecordIdType,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def create(
        self,
        record: RecordIdType,
        data: Value,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M: ...
    @overload
    def create(
        self,
        record: RecordIdType,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self,
        record: RecordIdType,
        data: Value,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Value]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Create a record (eager).

        ``db.create(record, data)`` runs ``CREATE ... CONTENT $data``
        immediately and returns the created record (``data=None`` runs
        ``CONTENT NULL``). ``db.create(record)`` (no data) returns a
        :class:`SyncCrudBuilder` so the caller can pick a terminal clause
        (``.content`` / ``.replace`` / ``.merge`` / ``.patch`` / ``.execute``).
        Pass ``into=Model`` to map the created record onto ``Model``.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="CREATE",
            record=record,
            op_name="create",
            always_unwrap=True,
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def update(
        self,
        record: RecordID,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def update(
        self,
        record: Table,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def update(
        self,
        record: str,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self,
        record: RecordID,
        data: Value,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M: ...
    @overload
    def update(
        self,
        record: Table,
        data: Value,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[M]: ...
    @overload
    def update(
        self,
        record: str,
        data: Value,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | list[M]: ...
    @overload
    def update(
        self,
        record: RecordID,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self,
        record: Table,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(
        self,
        record: str,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(
        self,
        record: RecordID,
        data: Value,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Value]: ...
    @overload
    def update(
        self,
        record: Table,
        data: Value,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[Value]: ...
    @overload
    def update(
        self,
        record: str,
        data: Value,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value: ...
    def update(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Update records, replacing existing content by default (eager).

        ``db.update(record, data)`` runs ``UPDATE ... CONTENT $data``
        immediately and returns the result (``data=None`` runs ``CONTENT
        NULL``). ``db.update(record)`` (no data) returns a
        :class:`SyncCrudBuilder` with terminal clause methods. Pass
        ``into=Model`` to map the returned record(s) onto ``Model`` /
        ``list[Model]``.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="UPDATE",
            record=record,
            op_name="update",
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def upsert(
        self,
        record: RecordID,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def upsert(
        self,
        record: Table,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(
        self,
        record: str,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self,
        record: RecordID,
        data: Value,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M: ...
    @overload
    def upsert(
        self,
        record: Table,
        data: Value,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[M]: ...
    @overload
    def upsert(
        self,
        record: str,
        data: Value,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | list[M]: ...
    @overload
    def upsert(
        self,
        record: RecordID,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self,
        record: Table,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(
        self,
        record: str,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(
        self,
        record: RecordID,
        data: Value,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Value]: ...
    @overload
    def upsert(
        self,
        record: Table,
        data: Value,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[Value]: ...
    @overload
    def upsert(
        self,
        record: str,
        data: Value,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Insert or update records (eager).

        ``db.upsert(record, data)`` runs ``UPSERT ... CONTENT $data``
        immediately and returns the result (``data=None`` runs ``CONTENT
        NULL``). ``db.upsert(record)`` (no data) returns a
        :class:`SyncCrudBuilder` with terminal clause methods. Pass
        ``into=Model`` to map the returned record(s) onto ``Model`` /
        ``list[Model]``.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="UPSERT",
            record=record,
            op_name="upsert",
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    @overload
    def delete(
        self,
        record: RecordID,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | None: ...
    @overload
    def delete(
        self,
        record: Table,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[M]: ...
    @overload
    def delete(
        self,
        record: str,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | list[M] | None: ...
    @overload
    def delete(
        self,
        record: RecordID,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Value] | None: ...
    @overload
    def delete(
        self,
        record: Table,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[Value]: ...
    @overload
    def delete(
        self,
        record: str,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value: ...
    def delete(
        self,
        record: RecordIdType,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Delete records eagerly and return the deleted record(s).

        A ``RecordID`` (or ``"table:id"``) returns the deleted record, or
        ``None`` when no record was deleted (matching select); a ``Table`` (or
        bare name) returns the list of deleted records. Pass ``into=Model`` to
        map the deleted record(s) onto ``Model``.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="DELETE",
            record=record,
            op_name="delete",
            into=into,
        )
        return builder.execute()

    @overload
    def insert(
        self,
        table: str | Table,
        *,
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        *,
        into: type[M],
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncInsertBuilder[M]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        data: Value,
        *,
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[Value]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        data: Value,
        *,
        into: type[M],
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Insert record(s) or relation(s) into a table (eager).

        ``db.insert(table, data)`` runs immediately and returns the inserted
        records. ``db.insert(table)`` (no data) returns a
        :class:`SyncInsertBuilder`; pass ``relation=True`` (or chain
        ``.relation()``) for ``INSERT RELATION INTO`` and run it with
        ``.content(data)`` / ``.execute()``. Pass ``into=Model`` to map the
        inserted records onto ``list[Model]``.
        """
        builder: SyncInsertBuilder[Any] = SyncInsertBuilder(
            executor=self._make_executor(session_id, txn_id),
            table=table,
            relation=relation,
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        kwargs: dict[str, Any] = {"name": name}
        if version is not None:
            kwargs["version"] = version
        if args is not None:
            kwargs["args"] = args
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.RUN, **kwargs)
        self.id = message.id
        response = self._send(message, "run")
        self.check_response_for_result(response, "run")
        return response["result"]

    def live(
        self,
        table: str | Table,
        diff: bool = False,
        session_id: UUID | None = None,
    ) -> UUID:
        """Start a live query on *table* and return its UUID.

        Pass ``diff=True`` for JSON-Patch notifications. Consume notifications
        with :meth:`subscribe_live` and stop the query with :meth:`kill`.
        """
        kwargs: dict[str, Any] = {"table": table, "diff": diff}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.LIVE, **kwargs)
        self.id = message.id
        response = self._send(message, "live")
        self.check_response_for_result(response, "live")
        return response["result"]

    def kill(
        self,
        query_uuid: str | UUID,
        session_id: UUID | None = None,
    ) -> None:
        """Kill a running live query by its UUID.

        Any ``subscribe_live`` generator on this connection for that query ends
        as a result, on every server version. 3.x announces the kill with a
        ``KILLED`` notification and the generator stops on that, but 2.x sends
        nothing at all - so waiting for the server left the caller's own
        subscription blocked forever on a query it had just killed itself. The
        sentinel below is pushed locally, which is what the async transport has
        always done.
        """
        kwargs: dict[str, Any] = {"uuid": query_uuid}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.KILL, **kwargs)
        self.id = message.id
        self._send(message, "kill")

        suid = str(query_uuid)
        for notifications in self.live_queues.get(suid, []):
            notifications.put(_LIVE_KILLED_SENTINEL)

    def subscribe_live(
        self,
        query_uuid: str | UUID,
    ) -> Generator[dict[str, Value], None, None]:
        """Yield notifications for a live query over this WebSocket.

        The blocking client has no background reader, so a single socket is
        shared between RPC calls and live subscriptions. Notifications are read
        under the connection lock with a short timeout, so concurrent RPCs from
        other threads stay responsive. Any notification that :meth:`_send`
        reads while correlating an RPC reply is routed here instead of lost.

        .. note::
            Only a single ``subscribe_live`` generator should be driven per
            connection at a time; running several concurrently on one socket is
            not supported (use separate connections instead).

        The subscription is registered before this returns, not on the first
        ``next()``. As a plain generator function the body - registration
        included - did not run until the consumer first iterated, and any
        notification ``_send`` read in that window found no queue to route to
        and was dropped with no error and no log. One RPC between ``live()``
        and the first ``next()`` was enough to lose a change permanently.

        Ends when the live query is killed, by :meth:`kill` here or by anyone
        else. The server marks that with a ``KILLED`` notification, which is
        not a change to the table - it carries no record - so it stops the
        iteration instead of being yielded. Yielding it handed consumers a
        notification whose ``result`` was ``None``, and the generator then ran
        on forever waiting for a query that no longer existed.

        :raises ConnectionUnavailableError: if the socket is not established or
            is closed while the subscription is active.
        """
        suid = str(query_uuid)
        notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self.live_queues.setdefault(suid, []).append(notifications)
        subscription = self._iter_live(suid, notifications)
        # Registration is eager, so release has to be reachable without ever
        # iterating. A generator that is never started does not run its
        # `finally` on close or GC, so a subscription that was set up and then
        # abandoned - on an early error, a conditional consumer, a retry loop -
        # stayed registered for the life of the connection while notifications
        # kept being routed into a queue nobody would ever drain.
        #
        # The finalizer deliberately closes over `live_queues` rather than
        # `self`: a bound method here would keep the whole connection alive for
        # as long as the generator, trading one leak for another.
        weakref.finalize(
            subscription, _release_live_queue, self.live_queues, suid, notifications
        )
        return subscription

    def _iter_live(
        self,
        suid: str,
        notifications: "queue.Queue[dict[str, Any]]",
    ) -> Generator[dict[str, Value], None, None]:
        """The body of :meth:`subscribe_live`, split out so registration is eager."""
        try:
            while True:
                # Hand back anything ``_send`` routed to us while correlating.
                try:
                    routed = notifications.get_nowait()
                except queue.Empty:
                    pass
                else:
                    if routed.get("action") == _LIVE_KILLED:
                        return
                    yield routed
                    continue

                # Otherwise read from the socket ourselves, under the lock so
                # we never race ``_send``. The short timeout releases the lock
                # between reads to keep concurrent RPCs responsive.
                with self._lock:
                    if self.socket is None:
                        raise ConnectionUnavailableError(
                            "WebSocket connection is not established."
                        )
                    try:
                        data = self.socket.recv(timeout=_LIVE_RECV_TIMEOUT)
                    except TimeoutError:
                        data = None
                    except (ConnectionClosed, WebSocketException, OSError) as exc:
                        logger.warning("Live subscription socket closed: %s", exc)
                        raise ConnectionUnavailableError(
                            "WebSocket connection closed while subscribed to a "
                            "live query."
                        ) from exc

                if data is None:
                    continue

                response = self.decode_response(
                    data if isinstance(data, bytes) else data.encode(),
                    "reading a live notification",
                )
                if response.get("id") is not None:
                    # Stray RPC reply with no waiter (should not happen while
                    # the lock serialises RPCs); ignore rather than yield it.
                    continue
                result = response.get("result")
                if not isinstance(result, dict):
                    continue
                rid = result.get("id")
                if rid is None:
                    continue
                if str(rid) == suid:
                    if result.get("action") == _LIVE_KILLED:
                        return
                    yield result
                else:
                    # Notification for a different live query; route it onward.
                    for other in self.live_queues.get(str(rid), []):
                        other.put(result)
        finally:
            # Deregister this consumer's queue on exit (consumer break, GC,
            # error, or connection close).
            queues = self.live_queues.get(suid)
            if queues is not None and notifications in queues:
                queues.remove(notifications)
            if queues is not None and not queues:
                self.live_queues.pop(suid, None)

    def attach(self) -> UUID:
        session_id = UUID(str(uuid.uuid4()))
        message = RequestMessage(RequestMethod.ATTACH, session=session_id)
        self.id = message.id
        self._send(message, "attach")
        return session_id

    def detach(self, session_id: UUID) -> None:
        message = RequestMessage(RequestMethod.DETACH, session=session_id)
        self.id = message.id
        self._send(message, "detach")

    def begin(self, session_id: UUID | None = None) -> UUID:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.BEGIN, **kwargs)
        self.id = message.id
        response = self._send(message, "begin")
        self.check_response_for_result(response, "begin")
        result = response["result"]
        if isinstance(result, UUID):
            return result
        if isinstance(result, str):
            return UUID(result)
        if isinstance(result, list) and len(result) == 1:
            return UUID(str(result[0]))
        if isinstance(result, dict):
            txn_val = result.get("id") or result.get("txn")
            if txn_val is not None:
                return UUID(str(txn_val))
        raise UnexpectedResponseError(
            f"begin() expected transaction UUID from server, got: {type(result).__name__}"
        )

    def commit(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"txn": txn_id}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.COMMIT, **kwargs)
        self.id = message.id
        self._send(message, "commit")

    def cancel(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        if session_id is not None:
            message = RequestMessage(
                RequestMethod.CANCEL, txn=txn_id, session=session_id
            )
        else:
            message = RequestMessage(RequestMethod.CANCEL, txn=txn_id)
        self.id = message.id
        self._send(message, "cancel")

    def new_session(self) -> "BlockingSurrealSession":
        session_id = self.attach()
        # A freshly attached session starts unauthenticated on the server -
        # it does not inherit the socket's auth automatically. Replay the
        # connection's current token so the new session shares the same
        # identity, matching the documented usage where you sign in once on
        # the connection and then open sessions from it. Callers can still
        # sign in / invalidate on the session to change its identity.
        if self.token is not None:
            self.authenticate(self.token, session_id=session_id)
        return BlockingSurrealSession(self, session_id)

    def close(self) -> None:
        """Close the websocket, if one is open.

        Idempotent, and leaves the connection reusable: ``connect()`` opens a
        fresh socket afterwards. Dropping the reference is what makes that
        work - while the attribute still held the closed socket, ``connect()``
        saw a connection and returned without doing anything, and every later
        call failed against the dead one. Matches ``AsyncWsSurrealConnection``,
        which has always cleared it here.

        The replacement socket is a new server-side session, so it starts
        unauthenticated and with no namespace or database selected; sign in and
        ``use()`` again after reconnecting.
        """
        if self.socket is not None:
            try:
                self.socket.close()
            finally:
                self.socket = None

    def __del__(self) -> None:
        """Close the socket if the connection is dropped without ``close()``.

        Every open websocket holds a TCP socket and two ``websockets`` worker
        threads (``recv_events`` and ``keepalive``). Nothing else releases
        them, so a program that built connections in a loop and let them go out
        of scope accumulated all three per connection until the process
        exited - ten live threads after five discarded connections.

        Deliberately *not* the graceful :meth:`close`. That performs a closing
        handshake and then joins the reader thread, which is wrong in a
        destructor twice over: at interpreter shutdown the reader has already
        been stopped without releasing its lock, so the join never returns and
        the process hangs instead of exiting; and whenever the peer has gone
        quiet it stalls whoever dropped the last reference for the full close
        timeout, at an arbitrary point in unrelated code. Shutting the socket
        down without waiting for anyone releases everything this needs to -
        ``websockets`` guarantees the reader terminates once it is closed, and
        both worker threads are daemons, so neither can hold the process open.
        """
        connection = getattr(self, "socket", None)
        if connection is None:
            return
        # `try`/`except`, not `contextlib.suppress`: a module-global lookup in a
        # destructor can fail at interpreter shutdown, which is the very case
        # this is defending against.
        try:  # noqa: SIM105
            connection.close_socket()
        except Exception:
            # Interpreter shutdown can pull what this needs out from under us,
            # and an exception raised here is unraisable anyway.
            pass

    def __enter__(self) -> "BlockingWsSurrealConnection":
        """Open the websocket if it is not already open, and return ``self``.

        Goes through :meth:`connect`, which is idempotent and holds the lock,
        rather than assigning a fresh socket unconditionally. Assigning
        replaced a socket that was already open and signed in: the server-side
        session went with it, the old socket leaked with its two worker
        threads, and the first statement inside the block failed with
        ``NotAllowedError: Anonymous access not allowed``. Signing in and
        *then* using the connection as a context manager - the obvious reading
        of "``with`` manages the connection I already have" - was exactly the
        shape that broke.
        """
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Synchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        self.close()


class BlockingSurrealSession:
    def __init__(
        self,
        connection: BlockingWsSurrealConnection,
        session_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id

    def use(self, namespace: str, database: str) -> None:
        self._connection.use(namespace, database, session_id=self._session_id)

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> SyncQueryBuilder:
        return self._connection.query(query, vars, session_id=self._session_id)

    def query_raw(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> dict[str, Any]:
        return self._connection.query_raw(query, vars, session_id=self._session_id)

    def signin(self, vars: dict[str, Value]) -> Tokens:
        return self._connection.signin(vars, session_id=self._session_id)

    def signup(self, vars: dict[str, Value]) -> Tokens:
        return self._connection.signup(vars, session_id=self._session_id)

    def authenticate(self, token: str) -> None:
        self._connection.authenticate(token, session_id=self._session_id)

    def invalidate(self) -> None:
        self._connection.invalidate(session_id=self._session_id)

    def info(self) -> Value:
        return self._connection.info(session_id=self._session_id)

    def version(self) -> str:
        return self._connection.version(session_id=self._session_id)

    def let(self, key: str, value: Value) -> None:
        self._connection.let(key, value, session_id=self._session_id)

    def unset(self, key: str) -> None:
        self._connection.unset(key, session_id=self._session_id)

    @overload
    def select(self, record: RecordID, *, into: type[M]) -> M | None: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> list[M]: ...
    @overload
    def select(self, record: str, *, into: type[M]) -> M | list[M] | None: ...
    @overload
    def select(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def select(self, record: Table) -> list[Value]: ...
    @overload
    def select(self, record: str) -> Value: ...
    def select(self, record: RecordIdType, *, into: type[M] | None = None) -> Any:
        if into is None:
            return self._connection.select(record, session_id=self._session_id)
        return self._connection.select(record, into=into, session_id=self._session_id)

    @overload
    def create(self, record: RecordIdType, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def create(self, record: RecordIdType, data: Value, *, into: type[M]) -> M: ...
    @overload
    def create(self, record: RecordIdType) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(self, record: RecordIdType, data: Value) -> dict[str, Value]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> Any:
        if into is None:
            return self._connection.create(record, data, session_id=self._session_id)
        return self._connection.create(
            record, data, into=into, session_id=self._session_id
        )

    @overload
    def update(self, record: RecordID, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def update(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def update(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(self, record: RecordID, data: Value, *, into: type[M]) -> M: ...
    @overload
    def update(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def update(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def update(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def update(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def update(self, record: str, data: Value) -> Value: ...
    def update(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> Any:
        if into is None:
            return self._connection.update(record, data, session_id=self._session_id)
        return self._connection.update(
            record, data, into=into, session_id=self._session_id
        )

    @overload
    def upsert(self, record: RecordID, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def upsert(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(self, record: RecordID, data: Value, *, into: type[M]) -> M: ...
    @overload
    def upsert(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def upsert(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def upsert(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def upsert(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def upsert(self, record: str, data: Value) -> Value: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> Any:
        if into is None:
            return self._connection.upsert(record, data, session_id=self._session_id)
        return self._connection.upsert(
            record, data, into=into, session_id=self._session_id
        )

    @overload
    def delete(self, record: RecordID, *, into: type[M]) -> M | None: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> list[M]: ...
    @overload
    def delete(self, record: str, *, into: type[M]) -> M | list[M] | None: ...
    @overload
    def delete(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def delete(self, record: Table) -> list[Value]: ...
    @overload
    def delete(self, record: str) -> Value: ...
    def delete(self, record: RecordIdType, *, into: type[M] | None = None) -> Any:
        if into is None:
            return self._connection.delete(record, session_id=self._session_id)
        return self._connection.delete(record, into=into, session_id=self._session_id)

    @overload
    def insert(
        self, table: str | Table, *, relation: bool = False
    ) -> SyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self, table: str | Table, *, into: type[M], relation: bool = False
    ) -> SyncInsertBuilder[M]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, relation: bool = False
    ) -> list[Value]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, into: type[M], relation: bool = False
    ) -> list[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> Any:
        if into is None:
            return self._connection.insert(
                table, data, relation=relation, session_id=self._session_id
            )
        return self._connection.insert(
            table, data, into=into, relation=relation, session_id=self._session_id
        )

    def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        return self._connection.run(name, args, version, session_id=self._session_id)

    def live(
        self,
        table: str | Table,
        diff: bool = False,
    ) -> UUID:
        return self._connection.live(table, diff, session_id=self._session_id)

    def kill(self, query_uuid: str | UUID) -> None:
        self._connection.kill(query_uuid, session_id=self._session_id)

    def subscribe_live(
        self, query_uuid: str | UUID
    ) -> Generator[dict[str, Value], None, None]:
        """Yield notifications for a live query started on this session.

        The session exposed :meth:`live` and :meth:`kill` but not this, so a
        session could start a live query it had no way to consume - callers had
        to reach past the wrapper to the underlying connection. Subscriptions
        are keyed by the live-query id rather than the session, so this
        forwards unchanged.
        """
        return self._connection.subscribe_live(query_uuid)

    def begin_transaction(self) -> "BlockingSurrealTransaction":
        txn_id = self._connection.begin(session_id=self._session_id)
        return BlockingSurrealTransaction(self._connection, self._session_id, txn_id)

    def close_session(self) -> None:
        self._connection.detach(self._session_id)


class BlockingSurrealTransaction:
    def __init__(
        self,
        connection: BlockingWsSurrealConnection,
        session_id: UUID,
        txn_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id
        self._txn_id = txn_id

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> SyncQueryBuilder:
        return self._connection.query(
            query,
            vars,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def query_raw(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> dict[str, Any]:
        return self._connection.query_raw(
            query,
            vars,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def info(self) -> Value:
        return self._connection.info(session_id=self._session_id)

    def version(self) -> str:
        return self._connection.version(session_id=self._session_id)

    @overload
    def select(self, record: RecordID, *, into: type[M]) -> M | None: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> list[M]: ...
    @overload
    def select(self, record: str, *, into: type[M]) -> M | list[M] | None: ...
    @overload
    def select(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def select(self, record: Table) -> list[Value]: ...
    @overload
    def select(self, record: str) -> Value: ...
    def select(self, record: RecordIdType, *, into: type[M] | None = None) -> Any:
        if into is None:
            return self._connection.select(
                record, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.select(
            record, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def create(self, record: RecordIdType, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def create(self, record: RecordIdType, data: Value, *, into: type[M]) -> M: ...
    @overload
    def create(self, record: RecordIdType) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(self, record: RecordIdType, data: Value) -> dict[str, Value]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> Any:
        if into is None:
            return self._connection.create(
                record, data, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.create(
            record, data, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def update(self, record: RecordID, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def update(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def update(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(self, record: RecordID, data: Value, *, into: type[M]) -> M: ...
    @overload
    def update(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def update(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def update(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def update(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def update(self, record: str, data: Value) -> Value: ...
    def update(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> Any:
        if into is None:
            return self._connection.update(
                record, data, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.update(
            record, data, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def upsert(self, record: RecordID, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def upsert(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(self, record: RecordID, data: Value, *, into: type[M]) -> M: ...
    @overload
    def upsert(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def upsert(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def upsert(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def upsert(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def upsert(self, record: str, data: Value) -> Value: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> Any:
        if into is None:
            return self._connection.upsert(
                record, data, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.upsert(
            record, data, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def delete(self, record: RecordID, *, into: type[M]) -> M | None: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> list[M]: ...
    @overload
    def delete(self, record: str, *, into: type[M]) -> M | list[M] | None: ...
    @overload
    def delete(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def delete(self, record: Table) -> list[Value]: ...
    @overload
    def delete(self, record: str) -> Value: ...
    def delete(self, record: RecordIdType, *, into: type[M] | None = None) -> Any:
        if into is None:
            return self._connection.delete(
                record, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.delete(
            record, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def insert(
        self, table: str | Table, *, relation: bool = False
    ) -> SyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self, table: str | Table, *, into: type[M], relation: bool = False
    ) -> SyncInsertBuilder[M]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, relation: bool = False
    ) -> list[Value]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, into: type[M], relation: bool = False
    ) -> list[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> Any:
        if into is None:
            return self._connection.insert(
                table,
                data,
                relation=relation,
                session_id=self._session_id,
                txn_id=self._txn_id,
            )
        return self._connection.insert(
            table,
            data,
            into=into,
            relation=relation,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        return self._connection.run(
            name,
            args,
            version,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    def let(self, key: str, value: Value) -> None:
        self._connection.let(
            key, value, session_id=self._session_id, txn_id=self._txn_id
        )

    def unset(self, key: str) -> None:
        self._connection.unset(key, session_id=self._session_id, txn_id=self._txn_id)

    def commit(self) -> None:
        self._connection.commit(self._txn_id, session_id=self._session_id)

    def cancel(self) -> None:
        self._connection.cancel(self._txn_id, session_id=self._session_id)
