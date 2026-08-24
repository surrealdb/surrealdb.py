"""
A basic blocking connection to a SurrealDB instance.
"""

import logging
import queue
import threading
import time
import uuid
import weakref
from collections.abc import Generator, Sequence
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
    _Executor,
    _map_result,
)
from surrealdb.connections.files import BlockingFiles
from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import (
    AUTH_FALLBACK_QUERY,
    UtilsMixin,
    render_projection,
)
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
    TransportTimeoutError,
    UnexpectedResponseError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.streaming import (
    QueryStream,
    SyncStreamOps,
    buffered_statements,
    stream_broken,
)
from surrealdb.types import Tokens, Value, parse_auth_result

logger = logging.getLogger(__name__)

# How long ``subscribe_live`` blocks on a single socket read before releasing
# the connection lock so concurrent RPCs on the same socket can proceed.
_LIVE_RECV_TIMEOUT = 0.1

# How long `_stream_pump` holds the connection lock looking for a frame. Short
# because the lock is unavailable for exactly this long each time: the waiting
# happens outside it, so this is the fairness bound for every other caller on
# the connection, not a polling interval.
_STREAM_POLL_TIMEOUT = 0.005

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

    def __init__(self, url: str, *, streaming: bool = True) -> None:
        """
        The constructor for the BlockingWsSurrealConnection class.

        :param url: (str) the URL of the database to process queries for.
        :param streaming: Whether queries may be answered as a stream of frames
            rather than one response. On by default and invisible: the answer is
            the same either way, so this only decides how it arrives. Pass
            ``False`` to put every query back on the buffered path.
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
        # Streaming queries, keyed by the request id whose frames they carry.
        # A ``query_stream`` request is answered by a sequence of responses all
        # sharing one id, which the single-reply correlation in ``_send`` cannot
        # represent: it stops at the first match and treats anything else as a
        # protocol desync. Queues hold decoded frames plus a ``_ChannelBroken``
        # sentinel, so the value type is ``Any``.
        self._streams: dict[str, queue.Queue[Any]] = {}
        # Whether this server knows ``query_stream``: ``None`` until one
        # request settles it. Cached per connection because the answer is a
        # property of the server build.
        self._streaming_supported: bool | None = None
        # Why it refused, when it did - a server older than v3.3.0 and one whose
        # capabilities deny `query_stream` need different advice.
        self._streaming_refusal: str | None = None
        # The driver-level switch, distinct from what the server turned out to
        # support.
        self._streaming_enabled: bool = streaming

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
                    if response_id == message.id:
                        break
                    if response_id is None and response.get("error") is not None:
                        # A frame with no `id` is normally a live-query
                        # notification. A protocol-level error - a request the
                        # server could not parse or correlate - also arrives
                        # without one, and routing that to the notification
                        # path discarded the only reply this call would ever
                        # get, leaving the loop blocked on recv() forever.
                        self.check_response_for_error(response, process)
                    # Anything else belongs to a live subscription, to a
                    # streaming query, or to a request that timed out and was
                    # abandoned. Hand it over and keep reading for our own.
                    self._route_foreign(response)
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

    def _route_foreign(self, response: dict[str, Any]) -> None:
        """Hand a response this reader was not waiting for to whoever wants it.

        Every socket read on this transport happens inside one of three loops -
        an RPC correlating its reply, a live subscription, or a streaming query
        - and each of them sees traffic belonging to the other two. Routing in
        one place is what stops one loop from discarding another's frames:
        before this existed, ``_send`` raised on any unrecognised id and
        ``_iter_live`` dropped every response that had one, so a stream sharing
        a connection with either lost frames outright.

        An id that matches nothing is dropped rather than raised on. It used to
        be a protocol desync worth failing over, but a stream that has been
        released - a cancel whose drain gave up, say - leaves frames in flight
        that belong to nobody, and failing an unrelated caller for them would
        turn a tidy-up into an error.
        """
        response_id = response.get("id")
        if response_id is None:
            if response.get("error") is not None and len(self._streams) == 1:
                # A request the server could not parse far enough to correlate
                # is answered with no id at all, and with `query()` streaming
                # that request is usually a stream. Routed to notifications it
                # was dropped, and the stream then waited out its deadline for
                # a frame that was never coming - on `select()` of a malformed
                # record id, an outright hang before the deadline existed.
                #
                # Only when it can be attributed: this transport serialises its
                # traffic, so a single open stream is the only thing that could
                # have sent the rejected frame. With two, nothing on the wire
                # says which.
                rejection = parse_rpc_error(response["error"])
                for stream in list(self._streams.values()):
                    stream.put(stream_broken(rejection))
                return
            self._route_live_notification(response)
            return
        key = str(response_id)
        frames = self._streams.get(key)
        if frames is not None:
            frames.put(response)
            return
        if key in self._abandoned:
            self._abandoned.discard(key)
            return
        logger.debug("dropping a response for unknown request id %s", key)

    def _break_streams(self, error: BaseException) -> None:
        """Tell every open stream that no more frames are coming.

        Streams wait on a queue rather than being handed an exception, so
        nothing else on the teardown paths reaches them. Snapshotted because a
        stream may be registered by another thread while this runs.
        """
        for frames in list(self._streams.values()):
            frames.put(stream_broken(error))

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
                    self._buffered_first(AUTH_FALLBACK_QUERY, session_id)
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
        if self._may_stream(txn_id):
            # Streamed, and the answer rebuilt in the shape a buffered query
            # returns - so `query()`, `select()`, `create()` and every builder
            # above this get their rows as the server produces them without
            # knowing anything about frames. `None` means the query was not run:
            # the server declined to stream it, so ask the buffered way.
            streamed = QueryStream(
                self._stream_ops(), query, vars, session_id=session_id
            ).collect()
            if streamed is not None:
                return streamed
        kwargs: dict[str, Any] = {"query": query, "params": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        if txn_id is not None:
            kwargs["txn"] = txn_id
        message = RequestMessage(RequestMethod.QUERY, **kwargs)
        self.id = message.id
        response = self._send(message, "query", bypass=True)
        return response

    def _buffered_first(self, query: str, session_id: UUID | None) -> Value | None:
        """Run *query* buffered and return its first statement's result.

        See :meth:`AsyncWsSurrealConnection._buffered_first`: the queries the
        SDK issues for itself stay off the frame path.
        """
        kwargs: dict[str, Any] = {"query": query, "params": {}}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.QUERY, **kwargs)
        response = self._send(message, "getting auth information", bypass=True)
        statements = buffered_statements(response)
        if not statements:
            return None
        first = statements[0]
        if first.get("status") == "ERR":
            raise parse_query_error(first)
        result: Value = first.get("result")
        return result

    def _may_stream(self, txn_id: UUID | None) -> bool:
        """Whether this query may be asked for as a stream.

        A query on a client transaction never is: it would run on the
        transaction `begin` handed out, and a `commit` arriving mid-stream would
        commit a prefix of the query rather than the whole of it. Excluding them
        removes the hazard instead of documenting it.
        """
        if not self._streaming_enabled or txn_id is not None:
            return False
        return self._streaming_supported is not False

    def query_stream(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
        *,
        require_streaming: bool = False,
    ) -> QueryStream:
        """Run SurrealQL and read the answer as it is produced.

        Needs SurrealDB v3.3.0 or later. Against an older server this falls
        back to a buffered :meth:`query` and replays it, so the call works
        everywhere - pass ``require_streaming=True`` to be told rather than
        served the fallback, which is what you want if the reason for
        streaming is to avoid holding a large result in memory.

        Iterate for rows, or use ``.statements()`` for one completed result per
        statement - see :class:`surrealdb.QueryStream`, which also covers
        stopping early and the sense in which a row is provisional::

            for person in db.query_stream("SELECT * FROM person"):
                ...

        Nothing is sent until iteration starts.
        """
        return QueryStream(
            self._stream_ops(),
            query,
            vars,
            session_id=session_id,
            txn_id=txn_id,
            require_streaming=require_streaming,
        )

    def _stream_ops(self) -> SyncStreamOps:
        """Bind the operations a streaming query drives.

        Bound methods rather than the connection itself, so a stream reaches
        only what it needs and cannot connect, close, or correlate an RPC.
        """
        return SyncStreamOps(
            registry=self._streams,
            open_timeout=_RPC_RECV_TIMEOUT,
            open=self._stream_open,
            release=self._stream_release,
            send=self._stream_send,
            pump=self._stream_pump,
            cancel=self._stream_cancel,
            buffered=self._stream_buffered,
            supported=self._stream_supported,
            set_supported=self._stream_set_supported,
            refusal=self._stream_refusal,
        )

    def _stream_open(self, request_id: str) -> "queue.Queue[Any]":
        """Register *request_id* and return the queue its frames arrive on.

        Registered before the request is sent, so a frame - or the immediate
        rejection of an unknown method - cannot arrive before there is
        anywhere to put it. Unbounded: nothing reads this socket except the
        loops that route into these queues, so a bounded queue could only be
        made to wait by stopping the reads that drain it.
        """
        with self._lock:
            if self.socket is None:
                # Lazily, exactly as `_send` connects. Going through
                # `connect()` instead pulled in `_connect_locked`, which closes
                # and reopens a socket whose state is not OPEN - a new
                # server-side session, unauthenticated - so a query on a stale
                # connection would have failed differently than it used to for
                # no reason the caller asked for.
                self.socket = self._connect_socket()
        frames: queue.Queue[Any] = queue.Queue()
        self._streams[request_id] = frames
        return frames

    def _stream_release(self, request_id: str) -> None:
        """Deregister a stream. Safe to call twice."""
        self._streams.pop(request_id, None)

    def _stream_send(self, message: RequestMessage) -> None:
        """Send *message* without correlating a reply.

        Not :meth:`_send`: that reads until it sees one response for this id
        and would consume the stream's first frame as the whole answer.
        """
        with self._lock:
            if self.socket is None:
                self.socket = self._connect_socket()
            assert self.socket is not None
            try:
                self.socket.send(message.WS_CBOR_DESCRIPTOR)
            except (WebSocketException, OSError) as exc:
                raise ConnectionUnavailableError(
                    f"the connection to {self.raw_url} failed while starting a "
                    f"streaming query: {exc}"
                ) from exc

    def _stream_pump(self, timeout: float) -> None:
        """Poll the socket for at most *timeout* seconds and route what arrives.

        Called by the thread iterating a stream, because nothing else on this
        transport reads the socket.

        The lock is held for the *poll*, never for the wait. Holding it for the
        whole slice - which is what "read with this timeout under the lock" did -
        left it free for microseconds out of every hundred milliseconds, so a
        thread merely wanting to run a query could be starved for as long as the
        stream stayed quiet. That is exactly what a stream does while a slow
        statement runs, and CI measured an ordinary query waiting 2.4s behind a
        stream idling through a `SLEEP`. Now the wait happens with the lock
        released, so it is available for most of every slice.
        """
        poll = min(_STREAM_POLL_TIMEOUT, timeout)
        with self._lock:
            if self.socket is None:
                raise ConnectionUnavailableError(
                    "WebSocket connection is not established."
                )
            try:
                data = self.socket.recv(timeout=poll)
            except TimeoutError:
                data = None
            except (ConnectionClosed, WebSocketException, OSError) as exc:
                error = ConnectionUnavailableError(
                    "WebSocket connection closed while a streaming query was "
                    f"open: {exc}"
                )
                self._break_streams(error)
                raise error from exc
            if data is not None:
                # Decoded and routed while still holding the lock, which the
                # read order depends on. Two threads pumping - one per stream,
                # or a stream beside a live subscription - each read one message
                # and then raced to route it, so a stream could be handed frame
                # two before frame one: rows out of order, or a terminal frame
                # ahead of the rows it terminates. Routing only puts to an
                # unbounded queue, so nothing here can block under the lock.
                self._route_foreign(
                    self.decode_response(
                        data if isinstance(data, bytes) else data.encode(),
                        "reading a streaming query frame",
                    )
                )
                return
        # Nothing was waiting. Sleep out the rest of the caller's slice with the
        # lock released, so anyone else on this connection can take it.
        time.sleep(max(0.0, timeout - poll))

    def _stream_cancel(self, request_id: str) -> None:
        """Ask the server to stop the stream *request_id* opened.

        A no-op once the socket has gone: there is nothing left to tell, and
        :meth:`_send` would reconnect the connection a caller had just closed,
        onto a new session where the stream does not exist.
        """
        if self.socket is None:
            return
        message = RequestMessage(RequestMethod.QUERY_CANCEL, stream=request_id)
        self._send(message, "cancelling a streaming query")

    def _stream_buffered(
        self,
        query: str,
        variables: dict[str, Value],
        session_id: UUID | None,
        txn_id: UUID | None,
    ) -> list[dict[str, Any]]:
        """Run *query* the buffered way, for a server without streaming."""
        response = self.query_raw(query, variables, session_id, txn_id)
        return buffered_statements(response)

    def _stream_supported(self) -> bool | None:
        return self._streaming_supported

    def _stream_refusal(self) -> str | None:
        return self._streaming_refusal

    def _stream_set_supported(self, supported: bool, reason: str | None) -> None:
        self._streaming_supported = supported
        self._streaming_refusal = reason

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
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | None: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[M]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> M | list[M] | None: ...
    @overload
    def select(
        self,
        record: RecordID,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> dict[str, Value] | None: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> list[Value]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Value: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Select records eagerly.

        A ``RecordID`` (or ``"table:id"``) returns the record dict, or ``None``
        when it is absent. A ``Table`` (or bare table-name string) returns the
        list of records. Pass ``into=Model`` to map each record onto ``Model``.

        ``fields`` narrows the projection, so the server sends only what is
        asked for rather than the whole record::

            db.select(RecordID("person", "tobie"), fields=["name", "email"])
            db.select(Table("person"), fields=["address.city"])

        A dot walks into a nested object; each segment is escaped separately, so
        a name with a space or unicode in it is quoted correctly. A field whose
        name genuinely contains a dot cannot be spelled this way - use
        :meth:`query` for that.

        Note that ``id`` is not included unless you ask for it, exactly as in
        SurrealQL. A model passed to ``into=`` that declares an ``id`` field
        therefore needs ``fields=["id", ...]``.
        """
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        projection = render_projection(fields)
        query = f"SELECT {projection} FROM {resource_ref}"

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
        """Build the executor a builder terminates through - see the async twin."""

        def _executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
            return self.query_raw(query, params, session_id=session_id, txn_id=txn_id)

        def _stream(
            query: str,
            params: dict[str, Value] | None,
            *,
            require_streaming: bool = False,
        ) -> QueryStream:
            return QueryStream(
                self._stream_ops(),
                query,
                params or None,
                session_id=session_id,
                txn_id=txn_id,
                require_streaming=require_streaming,
            )

        return _Executor(_executor, _stream)

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
                response: dict[str, Any] | None = None
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
                    if data is not None:
                        response = self.decode_response(
                            data if isinstance(data, bytes) else data.encode(),
                            "reading a live notification",
                        )
                        if response.get("id") is not None:
                            # Not a notification: an RPC reply with no waiter,
                            # or a frame belonging to a streaming query on this
                            # connection. Dropping it here lost the stream's
                            # frames, so hand it on - and do it inside the same
                            # lock hold as the read, because a stream's frames
                            # have to reach it in the order they came off the
                            # socket. Decoding and routing after releasing let
                            # two readers deliver out of order.
                            self._route_foreign(response)
                            response = None

                if response is None:
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
        # Streams get an error rather than a clean end: a caller iterating rows
        # asked for all of them, and a socket taken away mid-stream means it
        # will not get them. `_connect_locked` calls `close()` itself when it
        # finds a dead socket, so this is reachable without the caller closing
        # anything.
        self._break_streams(
            ConnectionUnavailableError(
                "the connection was closed while a streaming query was open."
            )
        )
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

    @property
    def files(self) -> BlockingFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return BlockingFiles(self)


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

    def query_stream(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        *,
        require_streaming: bool = False,
    ) -> QueryStream:
        return self._connection.query_stream(
            query,
            vars,
            session_id=self._session_id,
            require_streaming=require_streaming,
        )

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

    @property
    def files(self) -> BlockingFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return BlockingFiles(self)


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

    def query_stream(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        *,
        require_streaming: bool = False,
    ) -> QueryStream:
        """Stream a query on this transaction.

        Finish the stream before committing: the stream runs on the transaction
        this object holds, requests on one connection are served concurrently,
        and a ``commit`` that lands mid-stream commits a prefix of the query
        rather than the whole of it - the stream's next operation then fails
        with the transaction already finished.
        """
        return self._connection.query_stream(
            query,
            vars,
            session_id=self._session_id,
            txn_id=self._txn_id,
            require_streaming=require_streaming,
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

    @property
    def files(self) -> BlockingFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return BlockingFiles(self)
