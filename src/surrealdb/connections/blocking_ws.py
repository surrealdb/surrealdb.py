"""
A basic blocking connection to a SurrealDB instance.
"""

import logging
import queue
import threading
import uuid
from collections.abc import Generator
from types import TracebackType
from typing import Any, cast, overload
from uuid import UUID

import websockets
import websockets.sync.client as ws_sync
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.sync.client import ClientConnection

from surrealdb.connections.builders import (
    _UNSET,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
)
from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import AUTH_FALLBACK_QUERY, UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
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

    def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        # Use a lock to ensure thread-safe send/recv operations
        # This prevents race conditions when multiple threads share the same connection
        with self._lock:
            if self.socket is None:
                self.socket = ws_sync.connect(
                    self.raw_url,
                    max_size=None,
                    subprotocols=[websockets.Subprotocol("cbor")],
                )
            self.socket.send(message.WS_CBOR_DESCRIPTOR)

            # Correlate the reply to this request. Live-query notifications
            # carry no top-level "id" and may be delivered between our send and
            # our reply; route those to their live queue (if a subscriber is
            # registered, else drop) and keep reading, so a notification is
            # never returned as an RPC result.
            while True:
                data = self.socket.recv()
                response = decode(data if isinstance(data, bytes) else data.encode())
                response_id = response.get("id")
                if response_id is None:
                    self._route_live_notification(response)
                    continue
                if response_id != message.id:
                    raise UnexpectedResponseError(
                        f"Response ID mismatch: expected {message.id}, got "
                        f"{response_id}. This should not happen with proper "
                        "locking."
                    )
                break

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
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        """Select records eagerly.

        A ``RecordID`` (or ``"table:id"``) returns the record dict, or ``None``
        when it is absent. A ``Table`` (or bare table-name string) returns the
        list of records.
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
                return result[0] if result else None
            return result
        return result

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
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[dict[str, Value]] | dict[str, Value]:
        """Create a record (eager).

        ``db.create(record, data)`` runs ``CREATE ... CONTENT $data``
        immediately and returns the created record (``data=None`` runs
        ``CONTENT NULL``). ``db.create(record)`` (no data) returns a
        :class:`SyncCrudBuilder` so the caller can pick a terminal clause
        (``.content`` / ``.replace`` / ``.merge`` / ``.patch`` / ``.execute``).
        """
        builder: SyncCrudBuilder[dict[str, Value]] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="CREATE",
            record=record,
            op_name="create",
            always_unwrap=True,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

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
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[Any] | Value:
        """Update records, replacing existing content by default (eager).

        ``db.update(record, data)`` runs ``UPDATE ... CONTENT $data``
        immediately and returns the result (``data=None`` runs ``CONTENT
        NULL``). ``db.update(record)`` (no data) returns a
        :class:`SyncCrudBuilder` with terminal clause methods.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="UPDATE",
            record=record,
            op_name="update",
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

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
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[Any] | Value:
        """Insert or update records (eager).

        ``db.upsert(record, data)`` runs ``UPSERT ... CONTENT $data``
        immediately and returns the result (``data=None`` runs ``CONTENT
        NULL``). ``db.upsert(record)`` (no data) returns a
        :class:`SyncCrudBuilder` with terminal clause methods.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="UPSERT",
            record=record,
            op_name="upsert",
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

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
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value:
        """Delete records eagerly and return the deleted record(s).

        A ``RecordID`` (or ``"table:id"``) returns the deleted record, or
        ``None`` when no record was deleted (matching select); a ``Table`` (or
        bare name) returns the list of deleted records.
        """
        builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="DELETE",
            record=record,
            op_name="delete",
        )
        return cast(Value, builder.execute())

    @overload
    def insert(
        self,
        table: str | Table,
        *,
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncInsertBuilder: ...
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
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncInsertBuilder | list[Value]:
        """Insert record(s) or relation(s) into a table (eager).

        ``db.insert(table, data)`` runs immediately and returns the inserted
        records. ``db.insert(table)`` (no data) returns a
        :class:`SyncInsertBuilder`; pass ``relation=True`` (or chain
        ``.relation()``) for ``INSERT RELATION INTO`` and run it with
        ``.content(data)`` / ``.execute()``.
        """
        builder = SyncInsertBuilder(
            executor=self._make_executor(session_id, txn_id),
            table=table,
            relation=relation,
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
        kwargs: dict[str, Any] = {"table": table}
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
        """Kill a running live query by its UUID."""
        kwargs: dict[str, Any] = {"uuid": query_uuid}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.KILL, **kwargs)
        self.id = message.id
        self._send(message, "kill")

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

        :raises ConnectionUnavailableError: if the socket is not established or
            is closed while the subscription is active.
        """
        suid = str(query_uuid)
        notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self.live_queues.setdefault(suid, []).append(notifications)
        try:
            while True:
                # Hand back anything ``_send`` routed to us while correlating.
                try:
                    yield notifications.get_nowait()
                    continue
                except queue.Empty:
                    pass

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
                    except (ConnectionClosed, WebSocketException) as exc:
                        logger.warning("Live subscription socket closed: %s", exc)
                        raise ConnectionUnavailableError(
                            "WebSocket connection closed while subscribed to a "
                            "live query."
                        ) from exc

                if data is None:
                    continue

                response = decode(data if isinstance(data, bytes) else data.encode())
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
        if self.socket is not None:
            self.socket.close()

    def __enter__(self) -> "BlockingWsSurrealConnection":
        """
        Synchronous context manager entry.
        Initializes a websocket connection and returns the connection instance.
        """
        self.socket = ws_sync.connect(
            self.raw_url, max_size=None, subprotocols=[websockets.Subprotocol("cbor")]
        )
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
        if self.socket is not None:
            self.socket.close()


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

    def signin(self, vars: dict[str, Value]) -> Tokens:
        return self._connection.signin(vars, session_id=self._session_id)

    def signup(self, vars: dict[str, Value]) -> Tokens:
        return self._connection.signup(vars, session_id=self._session_id)

    def authenticate(self, token: str) -> None:
        self._connection.authenticate(token, session_id=self._session_id)

    def invalidate(self) -> None:
        self._connection.invalidate(session_id=self._session_id)

    def let(self, key: str, value: Value) -> None:
        self._connection.let(key, value, session_id=self._session_id)

    def unset(self, key: str) -> None:
        self._connection.unset(key, session_id=self._session_id)

    @overload
    def select(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def select(self, record: Table) -> list[Value]: ...
    @overload
    def select(self, record: str) -> Value: ...
    def select(self, record: RecordIdType) -> Value:
        return self._connection.select(record, session_id=self._session_id)

    @overload
    def create(self, record: RecordIdType) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(self, record: RecordIdType, data: Value) -> dict[str, Value]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
    ) -> SyncCrudBuilder[dict[str, Value]] | dict[str, Value]:
        return self._connection.create(record, data, session_id=self._session_id)

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
    ) -> SyncCrudBuilder[Any] | Value:
        return self._connection.update(record, data, session_id=self._session_id)

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
    ) -> SyncCrudBuilder[Any] | Value:
        return self._connection.upsert(record, data, session_id=self._session_id)

    @overload
    def delete(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def delete(self, record: Table) -> list[Value]: ...
    @overload
    def delete(self, record: str) -> Value: ...
    def delete(self, record: RecordIdType) -> Value:
        return self._connection.delete(record, session_id=self._session_id)

    @overload
    def insert(
        self, table: str | Table, *, relation: bool = False
    ) -> SyncInsertBuilder: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, relation: bool = False
    ) -> list[Value]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        relation: bool = False,
    ) -> SyncInsertBuilder | list[Value]:
        return self._connection.insert(
            table, data, relation=relation, session_id=self._session_id
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

    @overload
    def select(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def select(self, record: Table) -> list[Value]: ...
    @overload
    def select(self, record: str) -> Value: ...
    def select(self, record: RecordIdType) -> Value:
        return self._connection.select(
            record,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    @overload
    def create(self, record: RecordIdType) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(self, record: RecordIdType, data: Value) -> dict[str, Value]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
    ) -> SyncCrudBuilder[dict[str, Value]] | dict[str, Value]:
        return self._connection.create(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

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
    ) -> SyncCrudBuilder[Any] | Value:
        return self._connection.update(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

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
    ) -> SyncCrudBuilder[Any] | Value:
        return self._connection.upsert(
            record,
            data,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    @overload
    def delete(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def delete(self, record: Table) -> list[Value]: ...
    @overload
    def delete(self, record: str) -> Value: ...
    def delete(self, record: RecordIdType) -> Value:
        return self._connection.delete(
            record,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    @overload
    def insert(
        self, table: str | Table, *, relation: bool = False
    ) -> SyncInsertBuilder: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, relation: bool = False
    ) -> list[Value]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        relation: bool = False,
    ) -> SyncInsertBuilder | list[Value]:
        return self._connection.insert(
            table,
            data,
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
