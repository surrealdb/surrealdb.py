"""
A basic blocking connection to a SurrealDB instance.
"""

import inspect
import logging
import queue
import threading
import time
import uuid
import weakref
from collections.abc import Generator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from types import TracebackType
from typing import Any, cast, overload
from uuid import UUID

import websockets
import websockets.sync.client as ws_sync
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.protocol import State
from websockets.sync.client import ClientConnection

from surrealdb.connections.api import (
    ApiResponse,
    build_api_query,
    graphql_params,
    statement_results,
)
from surrealdb.connections.auth_provider import (
    SENT_WITHOUT_RENEWAL,
    AuthCredentials,
    AuthProvider,
    check_auth_provider,
    check_credentials,
    renewal_due,
)
from surrealdb.connections.batch import Batch
from surrealdb.connections.builders import (
    _UNSET,
    M,
    RelateEdge,
    RelateEnd,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
    _Executor,
    relate_builder,
)
from surrealdb.connections.files import BlockingFiles
from surrealdb.connections.health import check_health
from surrealdb.connections.import_export import (
    ExportOptions,
    ExportTarget,
    ImportData,
    export_sql,
    export_sql_to,
    import_sql,
)
from surrealdb.connections.live import LiveSubscription, SubscriptionTracker
from surrealdb.connections.reconnect import (
    LiveQuery,
    ReconnectOptions,
    SessionRegistry,
    SessionState,
    SessionTrackingMixin,
)
from surrealdb.connections.server_version import ServerVersionMixin, asks_for_refresh
from surrealdb.connections.sync_template import SyncTemplate
from surrealdb.connections.timeouts import (
    DEFAULT_TIMEOUT,
    check_timeout,
    describe,
    effective_timeout,
    scoped_timeout,
)
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import (
    AUTH_FALLBACK_QUERY,
    CBOR,
    CBOR2,
    UtilsMixin,
    check_keepalive,
)
from surrealdb.data.types.null import NullType
from surrealdb.data.types.record_id import RecordID, RecordIdType, StringRecordId
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
    NotAllowedError,
    ServerError,
    TransportTimeoutError,
    UnexpectedResponseError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.features import Features
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.streaming import (
    UNSUPPORTED_BY_SERVER,
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

# Pushed to a subscription whose live query could not be restarted after a
# reconnect: it ends with ConnectionUnavailableError rather than quietly.
_LIVE_BROKEN_SENTINEL: dict[str, Any] = {"action": "BROKEN", "id": None}


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


def _scope(session_id: UUID | None) -> dict[str, Any]:
    return {} if session_id is None else {"session": session_id}


class BlockingWsSurrealConnection(
    SyncTemplate, UtilsMixin, ServerVersionMixin, SessionTrackingMixin
):
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

    def __init__(
        self,
        url: str,
        *,
        streaming: bool = True,
        ping_interval: float | None = 30.0,
        ping_timeout: float | None = 10.0,
        timeout: float | None = DEFAULT_TIMEOUT,
        version_check: bool = True,
        reconnect: bool | ReconnectOptions = True,
        auth: AuthProvider | None = None,
        renew_access: bool = True,
    ) -> None:
        """
        The constructor for the BlockingWsSurrealConnection class.

        :param url: (str) the URL of the database to process queries for.
        :param streaming: Whether queries may be answered as a stream of frames
            rather than one response. On by default and invisible: the answer is
            the same either way, so this only decides how it arrives. Pass
            ``False`` to put every query back on the buffered path.
        :param ping_interval: Seconds between keepalive pings sent on an idle
            socket, or ``None`` to send none. Defaults to 30.
        :param ping_timeout: Seconds to wait for the matching pong before the
            connection is considered dead and closed, or ``None`` to wait
            indefinitely. Defaults to 10, so a gone peer is noticed within
            roughly ``ping_interval + ping_timeout``.
        :param timeout: Seconds to wait for each reply, or ``None`` to wait
            indefinitely. Defaults to 30. Override it for a block of requests
            with :meth:`timeout`.
        :param version_check: Refuse to talk to a server outside the versions
            this SDK supports - see :mod:`surrealdb.features`. On by default.
        :param reconnect: Reconnect when the socket has dropped, replaying the
            session state and live queries - see
            :mod:`surrealdb.connections.reconnect`. This transport has no
            background reader, so a dropped socket is noticed, and replaced,
            by the next request or live subscription that uses it.
        :param auth: How the connection signs itself in when the socket opens
            and after every reconnect: signin credentials, an access token,
            :class:`Tokens`, or a function returning one of those - see
            :mod:`surrealdb.connections.auth_provider`.
        :param renew_access: Renew the connection's access token shortly
            before it expires, with its refresh token or else with *auth*.
            Checked before each request, as this transport has no background
            work. On by default.
        """
        self.url: Url = Url(url)
        self._version_check = version_check
        check_auth_provider(auth)
        self._reconnect: ReconnectOptions = ReconnectOptions.coerce(reconnect)
        self._auth_provider: AuthProvider | None = auth
        self._renew_access = renew_access
        self._renewing = False
        self._registry = SessionRegistry()
        self._init_events()
        self._reconnecting = False
        self.raw_url: str = f"{self.url.raw_url}/rpc"
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self._timeout: float | None = check_timeout("timeout", timeout)
        self.id: str = str(uuid.uuid4())
        self.socket: ClientConnection | None = None
        self._ping_interval: float | None = check_keepalive(
            "ping_interval", ping_interval
        )
        self._ping_timeout: float | None = check_keepalive("ping_timeout", ping_timeout)
        self._lock: threading.Lock = threading.Lock()
        # The thread holding `_lock`, and the events raised while it did: they
        # are published once it is released, since a listener that makes a
        # request on this connection would otherwise wait on the lock forever.
        self._lock_owner: int | None = None
        self._pending_events: list[tuple[str, tuple[Any, ...]]] = []
        # Held across a state-changing request and the registry update that
        # records it, so concurrent threads record them in the order the
        # server applied them. Reentrant, so a listener can make one too.
        self._session_lock: threading.RLock = threading.RLock()
        # Live-query notification queues keyed by live-query UUID string. A
        # ``subscribe_live`` consumer registers its own queue here so that
        # notifications ``_send`` reads while correlating an RPC reply are
        # handed off instead of being lost.
        self.live_queues: dict[str, list[queue.Queue[dict[str, Any]]]] = {}
        self._live_tracker = SubscriptionTracker()
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

    def timeout(self, seconds: float | None) -> AbstractContextManager[None]:
        """Wait *seconds* for each reply to a request made inside the block.

        Overrides the connection's ``timeout`` for the code inside the ``with``
        block only, on the thread that runs it, so a slow import or a long
        report can wait longer without changing the default for everything
        else on the connection. ``None`` waits indefinitely::

            with db.timeout(300):
                db.query("SELECT * FROM big_table")
        """
        return scoped_timeout(self, seconds)

    def _request_timeout(self) -> float | None:
        """The reply deadline for a request made from the current context."""
        return effective_timeout(self, self._timeout)

    def _connect_socket(self) -> ClientConnection:
        """Open the websocket, mapping transport failures to SDK errors."""
        try:
            socket = ws_sync.connect(
                self.raw_url,
                max_size=None,
                subprotocols=[
                    websockets.Subprotocol(CBOR2),
                    websockets.Subprotocol(CBOR),
                ],
                ping_interval=self._ping_interval,
                ping_timeout=self._ping_timeout,
            )
        except TimeoutError as exc:
            raise TransportTimeoutError(
                f"timed out connecting to {self.raw_url}: {exc}"
            ) from exc
        except (WebSocketException, OSError) as exc:
            raise ConnectionUnavailableError(
                f"could not connect to {self.raw_url}: {exc}"
            ) from exc
        self._v2 = socket.subprotocol == CBOR2
        return socket

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
        with self._locked():
            self._connect_locked(url)

    def _connect_locked(self, url: str | None = None) -> None:
        """The body of :meth:`connect`, called with ``self._lock`` held."""
        if url is not None:
            target = Url(url)
            target_raw = f"{target.raw_url}/rpc"
            if self.socket is not None and target_raw != self.raw_url:
                self._shut()
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
            if self._reconnect.enabled:
                self._reconnect_locked()
                return
            self._shut()

        self._open_locked()

    @contextmanager
    def _locked(self) -> Generator[None, None, None]:
        """Hold ``self._lock``, publishing the events raised meanwhile after."""
        pending: list[tuple[str, tuple[Any, ...]]] = []
        try:
            with self._lock:
                self._lock_owner = threading.get_ident()
                try:
                    yield
                finally:
                    self._lock_owner = None
                    pending, self._pending_events = self._pending_events, []
        finally:
            for event, payload in pending:
                super()._emit(event, *payload)

    def _emit(self, event: str, *payload: Any) -> None:
        if self._lock_owner == threading.get_ident():
            self._pending_events.append((event, payload))
            return
        super()._emit(event, *payload)

    def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        # Use a lock to ensure thread-safe send/recv operations
        # This prevents race conditions when multiple threads share the same connection
        with self._locked():
            return self._send_locked(message, process, bypass)

    def _ready_locked(self, renew: bool = True) -> None:
        """Make sure there is an open socket to send on, with the lock held.

        A socket the peer dropped is replaced: by reconnecting, which replays
        the session, or - with reconnecting off - by a fresh one, since the
        server forgot the session along with the old socket.
        """
        if self.socket is None:
            self._open_locked()
        elif self.socket.state is not State.OPEN and not self._reconnecting:
            if self._reconnect.enabled:
                self._reconnect_locked()
            else:
                self._shut()
                self._open_locked()
        if renew and not self._reconnecting:
            self._renew_locked()

    def _send_frame_locked(self, message: RequestMessage) -> None:
        """Send *message*, reconnecting first if the socket turns out closed.

        The socket can close between the check in :meth:`_ready_locked` and
        the send. A send that raises ``ConnectionClosed`` wrote nothing, so the
        request cannot have run, and sending it again on the new socket is
        safe.
        """
        assert self.socket is not None
        try:
            self.socket.send(message.encoded(v2=self._v2))
        except ConnectionClosed:
            if not self._reconnect.enabled or self._reconnecting:
                raise
            # A stream registered for this very request has not started yet,
            # so it is spared when the reconnect breaks the open ones.
            unsent = self._streams.pop(message.id, None)
            try:
                self._reconnect_locked()
            finally:
                if unsent is not None:
                    self._streams[message.id] = unsent
            assert self.socket is not None
            self.socket.send(message.encoded(v2=self._v2))

    def _ensure_open(self) -> None:
        """Open the socket if there is none, as the next request would."""
        with self._locked():
            if self.socket is None:
                self._open_locked()

    def _open_locked(self) -> None:
        """Open the socket and check the server version, with the lock held."""
        self._set_status("connecting")
        try:
            self.socket = self._connect_socket()
        except BaseException:
            self._set_status("disconnected")
            raise
        try:
            self._handshake_locked()
            if self._auth_provider is not None:
                self._apply_auth_provider_locked()
        except BaseException:
            self._shut()
            raise
        self._set_status("connected", self._server_version)

    def _provided_credentials(self) -> AuthCredentials:
        provider = self._auth_provider
        if callable(provider):
            provided = provider()
            if inspect.iscoroutine(provided):
                provided.close()
                raise TypeError(
                    "auth is a coroutine function, which only an async "
                    "connection can call; pass a plain function here"
                )
            return check_credentials(provided)
        assert provider is not None
        return provider

    def _apply_auth_provider_locked(self) -> None:
        """Sign the connection's own session in with ``auth=``."""
        provided = self._provided_credentials()
        if isinstance(provided, dict):
            response = self._send_locked(
                RequestMessage(RequestMethod.SIGN_IN, params=provided), "signing in"
            )
            self.check_response_for_result(response, "signing in")
            self._note_tokens(None, parse_auth_result(response["result"]))
            return
        token = provided if isinstance(provided, str) else provided.access
        if token is None:
            raise ValueError("auth gave Tokens with no access token to sign in with")
        self._send_locked(
            RequestMessage(RequestMethod.AUTHENTICATE, token=token), "authenticating"
        )
        if isinstance(provided, Tokens):
            self._note_tokens(None, provided)
        else:
            self._note_authenticated(None, token)

    def _renew_locked(self) -> None:
        """Replace the access token before it expires, if it is about to."""
        root = self._registry.root
        if not self._renew_access or self._renewing or not renewal_due(root.access):
            return
        self._renewing = True
        try:
            if root.refresh is not None and self.is_feature_supported(
                Features.REFRESH_TOKENS
            ):
                pair = self._token_pair(None, None, "refresh()")
                response = self._send_locked(
                    RequestMessage(RequestMethod.REFRESH, params=[pair]),
                    "refreshing the tokens",
                )
                self.check_response_for_result(response, "refreshing the tokens")
                self._note_tokens(None, parse_auth_result(response["result"]))
            elif self._auth_provider is not None:
                self._apply_auth_provider_locked()
        except Exception as exc:
            logger.debug("renewing the access token failed: %s", exc)
            self._emit("error", exc)
        finally:
            self._renewing = False

    def _reconnect_locked(self) -> None:
        """Replace a dropped socket and replay what the server forgot.

        Runs on the thread that noticed, holding the lock - so other threads
        wait for the replay rather than racing it. The first attempt is
        immediate, since the drop is only noticed when the socket is next
        needed; later ones back off.

        :raises ConnectionUnavailableError: once every attempt has failed. The
            session state is forgotten then, so the request after that starts
            on a fresh, unauthenticated session.
        """
        self._set_status("reconnecting")
        self._break_streams(
            ConnectionUnavailableError(
                "the connection dropped while a streaming query was open."
            )
        )
        self._reconnecting = True
        attempt = 0
        try:
            while True:
                attempt += 1
                if not self._reconnect.allows(attempt):
                    break
                time.sleep(self._reconnect.delay(attempt))
                self._drop_socket()
                try:
                    self.socket = self._connect_socket()
                    self._handshake_locked()
                    self._restore_locked()
                except Exception as exc:
                    logger.debug("reconnect attempt %d failed: %s", attempt, exc)
                    self._emit("error", exc)
                    continue
                self._set_status("connected", self._server_version)
                self._end_unmanaged_live()
                return
        finally:
            self._reconnecting = False
        self._drop_socket()
        self._registry.clear()
        self._live_tracker.ended()
        error = ConnectionUnavailableError(
            f"the connection to {self.raw_url} dropped and could not be "
            f"re-established after {attempt - 1} attempt(s)"
        )
        self._set_status("disconnected")
        self._emit("error", error)
        raise error

    def _end_unmanaged_live(self) -> None:
        """Break the subscriptions a reconnect did not restart.

        A query attached with ``live_of()`` belongs to whoever started it, so
        it is not replayed; its subscribers would otherwise wait on a socket
        that will never carry it.
        """
        managed = self._registry.live.keys()
        for logical, queues in self.live_queues.items():
            if logical not in managed:
                for notifications in queues:
                    notifications.put(_LIVE_BROKEN_SENTINEL)
        self._live_tracker.ended(keep=managed)

    def _drop_socket(self) -> None:
        """Close and forget the socket, if any, keeping the session state."""
        if self.socket is not None:
            try:
                self.socket.close()
            except Exception:
                pass
            finally:
                self.socket = None

    def _restore_locked(self) -> None:
        """Replay every session, then every live query, on the new socket."""
        registry = self._registry
        if self._auth_provider is None:
            self._restore_session_locked(None, registry.root)
        else:
            self._restore_session_locked(None, registry.root, authenticate=False)
            self._apply_auth_provider_locked()
        for session_id, state in list(registry.sessions.items()):
            self._send_locked(
                RequestMessage(RequestMethod.ATTACH, session=session_id),
                "re-attaching a session",
            )
            self._restore_session_locked(session_id, state)
        for live in list(registry.live.values()):
            self._restore_live_locked(live)

    def _restore_session_locked(
        self, session_id: UUID | None, state: SessionState, authenticate: bool = True
    ) -> bool:
        scope: dict[str, Any] = {} if session_id is None else {"session": session_id}
        if state.namespace is not None or state.database is not None:
            self._send_locked(
                RequestMessage(
                    RequestMethod.USE,
                    namespace=state.namespace,
                    database=state.database,
                    **scope,
                ),
                "re-selecting the namespace and database",
            )
        for key, value in list(state.variables.items()):
            self._send_locked(
                RequestMessage(RequestMethod.LET, key=key, value=value, **scope),
                "re-setting a variable",
            )
        if authenticate and state.access is not None:
            try:
                self._send_locked(
                    RequestMessage(
                        RequestMethod.AUTHENTICATE, token=state.access, **scope
                    ),
                    "re-authenticating",
                )
            except ServerError as exc:
                self._emit("error", exc)
                self._note_signed_out(session_id)
                return False
        return True

    def _restore_live_locked(self, live: LiveQuery) -> None:
        kwargs: dict[str, Any] = {"table": live.table, "diff": live.diff}
        if live.session_id is not None:
            kwargs["session"] = live.session_id
        try:
            response = self._send_locked(
                RequestMessage(RequestMethod.LIVE, **kwargs), "restarting a live query"
            )
            self.check_response_for_result(response, "restarting a live query")
        except ServerError as exc:
            self._emit("error", exc)
            logical = str(live.logical)
            self._registry.drop_live(logical)
            self._live_tracker.ended(logical)
            for notifications in self.live_queues.get(logical, []):
                notifications.put(_LIVE_BROKEN_SENTINEL)
            return
        self._registry.move_live(live, UUID(str(response["result"])))

    def _handshake_locked(self) -> None:
        """Ask a freshly opened socket's server for its version."""
        self._forget_server_version()
        self._streaming_supported = None
        self._streaming_refusal = None
        try:
            response = self._send_locked(
                RequestMessage(RequestMethod.VERSION), "checking the server version"
            )
        except ServerError:
            # A server whose capabilities deny `version` still serves
            # everything else; nothing can be gated, but nothing is refused.
            self._adopt_server_version(None)
            return
        self._adopt_server_version(response.get("result"))
        if not self._version_allows_streaming():
            self._streaming_supported = False
            self._streaming_refusal = UNSUPPORTED_BY_SERVER

    def _send_locked(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        """The body of :meth:`_send`, called with ``self._lock`` held."""
        self._ready_locked(renew=message.method not in SENT_WITHOUT_RENEWAL)
        assert self.socket is not None

        # Correlate the reply to this request. Live-query notifications
        # carry no top-level "id" and may be delivered between our send and
        # our reply; route those to their live queue (if a subscriber is
        # registered, else drop) and keep reading, so a notification is
        # never returned as an RPC result.
        budget = self._request_timeout()
        try:
            self._send_frame_locked(message)
            deadline = None if budget is None else time.monotonic() + budget
            while True:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    # The request was sent, so a reply is still coming.
                    # Remember it, or the next call reads this reply,
                    # mismatches the id and fails - and so does every call
                    # after it, permanently out of step by one.
                    self._abandoned.add(message.id)
                    raise TransportTimeoutError(
                        f"timed out while {process} on {self.raw_url}: no "
                        f"reply {describe(budget)}"
                    )
                data = self.socket.recv(timeout=remaining)
                response = self.decode_response(
                    data if isinstance(data, bytes) else data.encode(),
                    process,
                    v2=self._v2,
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
                f"timed out while {process} on {self.raw_url}: no reply "
                f"{describe(budget)}"
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
        logical = self._logical_live(result)
        for notifications in self.live_queues.get(logical, []):
            notifications.put(result)

    def _logical_live(self, result: dict[str, Any]) -> str:
        """The id the caller holds for a notification's live query.

        Rewrites the notification to carry it, so a subscriber sees the id it
        was given even after a reconnect started the query under a new one. A
        ``KILLED`` notification also stops the query being replayed.
        """
        current = str(result["id"])
        logical = self._registry.logical_of(current)
        if logical != current:
            result["id"] = UUID(logical)
        if result.get("action") == _LIVE_KILLED:
            self._registry.drop_live(logical)
            self._live_tracker.ended(logical)
        return logical

    def authenticate(self, token: str, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"token": token}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.AUTHENTICATE, **kwargs)
        self.id = message.id
        with self._session_lock:
            self._send(message, "authenticating")
            # Record the token as the session's identity so a reconnect - and,
            # for the connection's own, new_session() - can replay it.
            self._note_authenticated(session_id, token)

    def invalidate(self, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INVALIDATE, **kwargs)
        self.id = message.id
        with self._session_lock:
            self._send(message, "invalidating")
            self._note_signed_out(session_id)

    def refresh(
        self, tokens: Tokens | None = None, session_id: UUID | None = None
    ) -> Tokens:
        """Exchange a refresh token for a new access and refresh token.

        Uses the session's own tokens unless *tokens* is given, authenticates
        the session with the new access token and returns the new pair. The
        old refresh token is spent. Needs SurrealDB 3.0 or later and an access
        method defined ``WITH REFRESH``.
        """
        self._ensure_open()
        self._require(Features.REFRESH_TOKENS)
        pair = self._token_pair(tokens, session_id, "refresh()")
        message = RequestMessage(
            RequestMethod.REFRESH, params=[pair], **_scope(session_id)
        )
        with self._session_lock:
            response = self._send(message, "refreshing the tokens")
            self.check_response_for_result(response, "refreshing the tokens")
            renewed = parse_auth_result(response["result"])
            self._note_tokens(session_id, renewed)
        return renewed

    def revoke(
        self, tokens: Tokens | None = None, session_id: UUID | None = None
    ) -> None:
        """Revoke a refresh token, so it can never be exchanged again.

        Uses the session's own tokens unless *tokens* is given. The session
        stays signed in with its access token until that expires or
        :meth:`invalidate` is called. Needs SurrealDB 3.0 or later.
        """
        self._ensure_open()
        self._require(Features.REFRESH_TOKENS)
        pair = self._token_pair(tokens, session_id, "revoke()")
        message = RequestMessage(
            RequestMethod.REVOKE, params=[pair], **_scope(session_id)
        )
        with self._session_lock:
            self._send(message, "revoking a refresh token")
            self._note_revoked(session_id, pair["refresh"])

    def reset(self, session_id: UUID | None = None) -> None:
        """Return the session to how it started: no namespace, database,
        variables or authentication. Needs SurrealDB 3.0 or later."""
        self._ensure_open()
        self._require(Features.SESSIONS)
        message = RequestMessage(RequestMethod.RESET, **_scope(session_id))
        with self._session_lock:
            self._send(message, "resetting the session")
            self._note_reset(session_id)
            self._end_session_live(session_id)

    def sessions(self) -> list[UUID]:
        """The ids of the sessions attached to this connection on the server,
        not counting its own. Needs SurrealDB 3.0 or later."""
        self._ensure_open()
        self._require(Features.SESSIONS)
        response = self._send(
            RequestMessage(RequestMethod.SESSIONS), "listing the sessions"
        )
        self.check_response_for_result(response, "listing the sessions")
        return [UUID(str(session)) for session in response["result"] or []]

    def export(self, options: ExportOptions | None = None) -> str:
        """Export the selected database as SurrealQL.

        Args:
            options: What to include; the server's default without it.
                SurrealDB 2.0 takes no options.

        Example:
            sql = db.export(ExportOptions(tables=["person"], records=False))
        """
        options = options or ExportOptions()
        with self._locked():
            self._ready_locked()
        options.check(self._server_version)
        return export_sql(
            self.url,
            options,
            self._request_timeout(),
            self.token,
            self.namespace,
            self.database,
        )

    def export_to(
        self, target: ExportTarget, options: ExportOptions | None = None
    ) -> None:
        """Export the selected database as SurrealQL into *target*.

        Writes the export as it arrives, so one too large to hold in memory
        can still be saved.

        Args:
            target: The path of a file to write, or a binary file object.
            options: What to include, as for :meth:`export`.

        Example:
            db.export_to("backup.surql")
        """
        options = options or ExportOptions()
        with self._locked():
            self._ready_locked()
        options.check(self._server_version)
        export_sql_to(
            self.url,
            options,
            target,
            self._request_timeout(),
            self.token,
            self.namespace,
            self.database,
        )

    def import_(self, data: ImportData) -> None:
        """Import SurrealQL into the selected database.

        Args:
            data: The SurrealQL, as ``str`` or ``bytes``, or the path of a
                file holding it - such as one ``export()`` wrote. SurrealDB 3
                requires it to start with ``OPTION IMPORT;``, as exports do.

        Raises:
            ImportFailedError: if any statement failed, with each failure in
                ``failures``. The other statements were still applied.
        """
        with self._locked():
            self._ready_locked()
        import_sql(
            self.url,
            data,
            self._request_timeout(),
            self.token,
            self.namespace,
            self.database,
        )

    def health(self) -> None:
        """Ask the server's ``/health`` endpoint whether it is healthy.

        :raises ConnectionUnavailableError: if it is not, or cannot be reached.
        """
        check_health(self.url, self._request_timeout())

    def api(
        self,
        path: str,
        *,
        method: str = "get",
        body: Value = None,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> ApiResponse:
        """Call an endpoint defined with ``DEFINE API``.

        Sent as ``RETURN api::invoke(path, request)``. Needs SurrealDB 3.0 or
        later, started with the ``define_api`` experimental capability.

        Args:
            path: The endpoint's path, starting with ``/``.
            method: The HTTP method to invoke it with.
            body: The request body.
            headers: Request headers.
            query: Query-string parameters.

        Example:
            response = db.api("/greet", method="post", body={"name": "Ada"})
            assert response.ok
        """
        self._ensure_open()
        self._require(Features.API)
        sql, variables = build_api_query(path, method, body, headers, query)
        result = self.query(
            sql, variables, session_id=session_id, txn_id=txn_id
        ).first()
        return ApiResponse.from_result(result)

    def gql(
        self,
        query: str,
        vars: Mapping[str, Value] | None = None,
        *,
        session_id: UUID | None = None,
    ) -> list[Value]:
        """Run an ISO GQL query, such as ``MATCH (p:person) RETURN p.name``.

        Returns each statement's result, and raises the first statement that
        failed. Needs a server with the ``gql`` RPC method.
        """
        self._ensure_open()
        params: list[Value] = [query] if vars is None else [query, dict(vars)]
        message = RequestMessage(RequestMethod.GQL, params=params, **_scope(session_id))
        response = self._send(message, "gql")
        self.check_response_for_result(response, "gql")
        return statement_results(response["result"], "gql")

    def graphql(
        self,
        query: str,
        variables: Mapping[str, Value] | None = None,
        operation_name: str | None = None,
        *,
        session_id: UUID | None = None,
    ) -> dict[str, Value]:
        """Run a GraphQL query and return the server's ``{data, errors}``.

        Needs a server with the ``graphql`` RPC method and GraphQL enabled for
        the database, for example with ``DEFINE CONFIG GRAPHQL AUTO``.
        """
        self._ensure_open()
        message = RequestMessage(
            RequestMethod.GRAPHQL,
            params=graphql_params(query, variables, operation_name),
            **_scope(session_id),
        )
        response = self._send(message, "graphql")
        self.check_response_for_result(response, "graphql")
        result = response["result"]
        return dict(result) if isinstance(result, dict) else {"data": result}

    def signup(self, vars: dict[str, Value], session_id: UUID | None = None) -> Tokens:
        kwargs: dict[str, Any] = {"data": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_UP, **kwargs)
        self.id = message.id
        with self._session_lock:
            response = self._send(message, "signup")
            self.check_response_for_result(response, "signup")
            tokens = parse_auth_result(response["result"])
            self._note_tokens(session_id, tokens)
        return tokens

    def signin(self, vars: dict[str, Value], session_id: UUID | None = None) -> Tokens:
        if not self._version_learned and asks_for_refresh(vars):
            self._ensure_open()
        self._require_signin(vars)
        kwargs: dict[str, Any] = {"params": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_IN, **kwargs)
        self.id = message.id
        with self._session_lock:
            response = self._send(message, "signing in")
            self.check_response_for_result(response, "signing in")
            tokens = parse_auth_result(response["result"])
            self._note_tokens(session_id, tokens)
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
        namespace: str | NullType | None = None,
        database: str | NullType | None = None,
        session_id: UUID | None = None,
    ) -> None:
        """Select a namespace and database.

        Either may be left out, or ``None``, to keep the current one, or
        ``Null`` to clear it - ``use(database="other")`` changes only the
        database, and ``use(Null, Null)`` selects neither.
        """
        kwargs: dict[str, Any] = {
            "namespace": namespace,
            "database": database,
        }
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.USE, **kwargs)
        self.id = message.id
        with self._session_lock:
            self._send(message, "use")
            self._note_use(session_id, namespace, database)

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

    def batch(self) -> Batch:
        """Statements to send together as one transaction, in one request.

        Add them with ``.query(sql, vars)`` and run them with ``.execute()``.
        They all apply or none do. Works on every transport and version.
        """
        return Batch(self)

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
            )._collect()  # pyright: ignore[reportPrivateUsage]
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

    def _stream_ops(self) -> SyncStreamOps:
        """Bind the operations a streaming query drives.

        Bound methods rather than the connection itself, so a stream reaches
        only what it needs and cannot connect, close, or correlate an RPC.
        """
        return SyncStreamOps(
            registry=self._streams,
            request_timeout=self._request_timeout,
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
        with self._locked():
            # Exactly as `_send` does, so a query on a dropped connection is
            # handled the same whichever path it takes.
            self._ready_locked()
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
        with self._locked():
            self._ready_locked()
            try:
                self._send_frame_locked(message)
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
        with self._locked():
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
                        v2=self._v2,
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
        with self._session_lock:
            self._send(message, "letting")
            if txn_id is None:
                self._note_let(session_id, key, value)

    def set(
        self,
        key: str,
        value: Value,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> None:
        """Set a variable for the session; ``let`` by its JS name."""
        self.let(key, value, session_id=session_id, txn_id=txn_id)

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
        with self._session_lock:
            self._send(message, "unsetting")
            if txn_id is None:
                self._note_unset(session_id, key)

    @overload
    def select(
        self,
        record: RecordID | StringRecordId,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(
        self,
        record: RecordID | StringRecordId,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[Value]: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Select records, returning a builder.

        A ``RecordID`` (or ``StringRecordId``) returns the record dict, or ``None``
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
        return SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="SELECT",
            record=record,
            op_name="select",
            into=into,
            fields=fields,
        )

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
            statements: bool = False,
            frames: bool = False,
        ) -> QueryStream:
            return QueryStream(
                self._stream_ops(),
                query,
                params or None,
                session_id=session_id,
                txn_id=txn_id,
                require_streaming=require_streaming,
                statements=statements,
                frames=frames,
            )

        return _Executor(_executor, _stream)

    # CRUD -------------------------------------------------------------------
    #
    # Sync CRUD with ``data`` runs immediately and returns the result; the
    # no-data form returns a ``SyncCrudBuilder`` so the caller can pick a
    # clause. ``select`` and ``delete`` always return a builder.

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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
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
        record: RecordID | StringRecordId,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def delete(
        self,
        record: Table,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self,
        record: str,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(
        self,
        record: RecordID | StringRecordId,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(
        self,
        record: Table,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(
        self,
        record: str,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[Value]: ...
    def delete(
        self,
        record: RecordIdType,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> SyncCrudBuilder[Any]:
        """Delete records, returning a builder.

        ``.execute()`` gives the deleted record(s) - a ``RecordID`` (or
        ``StringRecordId``) the deleted record, or ``None`` when none was deleted,
        matching select; a ``Table`` (or bare name) the list. ``.rows()`` reads
        them as the server produces them, since ``DELETE ... RETURN BEFORE``
        does return rows. Pass ``into=Model`` to map them onto ``Model``.
        """
        return SyncCrudBuilder(
            executor=self._make_executor(session_id, txn_id),
            operation="DELETE",
            record=record,
            op_name="delete",
            into=into,
        )

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
    ) -> LiveSubscription:
        """Start a live query on *table* and return its subscription.

        The subscription is also the query's UUID. Iterate it for
        notifications, and ``kill()`` it, or use it with ``with``, to stop the
        query.

        Pass ``diff=True`` for JSON-Patch notifications. Consume notifications
        with :meth:`subscribe_live` and stop the query with :meth:`kill`.
        """
        kwargs: dict[str, Any] = {"table": table, "diff": diff}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.LIVE, **kwargs)
        self.id = message.id
        with self._session_lock:
            response = self._send(message, "live")
            self.check_response_for_result(response, "live")
            live_id = UUID(str(response["result"]))
            self._registry.add_live(
                LiveQuery(live_id, live_id, table, diff, session_id)
            )
        subscription = LiveSubscription(live_id, self, session_id, managed=True)
        self._live_tracker.add(subscription)
        # Listening from now, so nothing that changes before the caller starts
        # iterating is lost.
        subscription._hold(self.subscribe_live(subscription))  # pyright: ignore[reportPrivateUsage]
        return subscription

    def live_of(
        self, live_id: str | UUID, session_id: UUID | None = None
    ) -> LiveSubscription:
        """Attach to a live query started some other way, by its id.

        For example one started with ``LIVE SELECT`` through :meth:`query`.
        Its notifications are delivered from now on; the query is not
        restarted after a reconnect, since the connection does not know it.
        """
        subscription = LiveSubscription(live_id, self, session_id, managed=False)
        self._live_tracker.add(subscription)
        subscription._hold(self.subscribe_live(subscription))  # pyright: ignore[reportPrivateUsage]
        return subscription

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
        suid = str(query_uuid)
        with self._session_lock:
            # The caller holds the id the query was started under; after a
            # reconnect the server knows it by another.
            current = self._registry.resolve(suid)
            kwargs: dict[str, Any] = {
                "uuid": query_uuid if current == suid else UUID(current)
            }
            if session_id is not None:
                kwargs["session"] = session_id
            message = RequestMessage(RequestMethod.KILL, **kwargs)
            self.id = message.id
            self._send(message, "kill")
            self._registry.drop_live(suid)

        self._live_tracker.ended(suid)
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

        A subscription from :meth:`live` already holds a registered generator,
        which is handed over rather than registering a second one.

        :raises ConnectionUnavailableError: if the socket is not established or
            is closed while the subscription is active.
        """
        if isinstance(query_uuid, LiveSubscription):
            held = query_uuid._take()  # pyright: ignore[reportPrivateUsage]
            if held is not None:
                return cast(Generator[dict[str, Value], None, None], held)
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
                    if routed is _LIVE_BROKEN_SENTINEL:
                        raise ConnectionUnavailableError(
                            "WebSocket connection closed while subscribed to "
                            f"live query {suid}, and it could not be restarted."
                        )
                    if routed.get("action") == _LIVE_KILLED:
                        return
                    yield routed
                    continue

                # Otherwise read from the socket ourselves, under the lock so
                # we never race ``_send``. The short timeout releases the lock
                # between reads to keep concurrent RPCs responsive.
                response: dict[str, Any] | None = None
                with self._locked():
                    if self.socket is None:
                        raise ConnectionUnavailableError(
                            "WebSocket connection is not established."
                        )
                    try:
                        data = self.socket.recv(timeout=_LIVE_RECV_TIMEOUT)
                    except TimeoutError:
                        data = None
                    except (ConnectionClosed, WebSocketException, OSError) as exc:
                        if not notifications.empty():
                            # close() left the end-of-subscription marker.
                            continue
                        if self._reconnect.enabled and suid in self._registry.live:
                            # Replays this query under a new server-side id
                            # that still routes to `suid`; carry on reading.
                            self._reconnect_locked()
                            continue
                        logger.warning("Live subscription socket closed: %s", exc)
                        raise ConnectionUnavailableError(
                            "WebSocket connection closed while subscribed to a "
                            "live query."
                        ) from exc
                    if data is not None:
                        response = self.decode_response(
                            data if isinstance(data, bytes) else data.encode(),
                            "reading a live notification",
                            v2=self._v2,
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
                rid = self._logical_live(result)
                if rid == suid:
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
        self._ensure_open()
        self._require(Features.SESSIONS)
        session_id = UUID(str(uuid.uuid4()))
        message = RequestMessage(RequestMethod.ATTACH, session=session_id)
        self.id = message.id
        with self._session_lock:
            self._send(message, "attach")
            self._registry.state(session_id)
        return session_id

    def detach(self, session_id: UUID) -> None:
        message = RequestMessage(RequestMethod.DETACH, session=session_id)
        self.id = message.id
        with self._session_lock:
            self._send(message, "detach")
            self._end_session_live(session_id)
            self._registry.forget_session(session_id)

    def _end_session_live(self, session_id: UUID | None) -> None:
        """End the live queries the server dropped with *session_id*'s state."""
        for logical, live in list(self._registry.live.items()):
            if live.session_id == session_id:
                self._registry.drop_live(logical)
                self._live_tracker.ended(logical)
                for notifications in self.live_queues.get(logical, []):
                    notifications.put(_LIVE_KILLED_SENTINEL)

    def begin(self, session_id: UUID | None = None) -> UUID:
        self._ensure_open()
        self._require(Features.TRANSACTIONS)
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

    def fork_session(self, session_id: UUID | None = None) -> "BlockingSurrealSession":
        """A new session that starts as a copy of another.

        Copies the namespace and database, the variables and the
        authentication of *session_id* - the connection's own session by
        default - into a newly attached session. The two are independent from
        then on. Needs SurrealDB 3.0 or later.
        """
        with self._session_lock:
            if session_id is not None and session_id not in self._registry.sessions:
                raise ValueError(
                    f"session {session_id} is not attached to this connection, "
                    "so there is nothing to fork; fork a session that is still "
                    "open"
                )
            source = self._registry.state(session_id).fork()
            forked = self.attach()
            try:
                with self._locked():
                    authenticated = self._restore_session_locked(forked, source)
            except BaseException:
                self.detach(forked)
                raise
            state = self._registry.state(forked)
            state.namespace, state.database = source.namespace, source.database
            state.variables = source.variables
            if authenticated and source.access is not None:
                state.access, state.refresh = source.access, source.refresh
        return BlockingSurrealSession(self, forked)

    def begin_transaction(
        self, session_id: UUID | None = None
    ) -> "BlockingSurrealTransaction":
        """Begin a transaction on a session - the connection's own by default.

        Commit or cancel it, or use it as a context manager, which commits
        when the block finishes and cancels if it raises. Needs SurrealDB 3.0
        or later; :meth:`batch` works on every version.
        """
        txn_id = self.begin(session_id=session_id)
        return BlockingSurrealTransaction(self, session_id, txn_id)

    def new_session(self) -> "BlockingSurrealSession":
        session_id = self.attach()
        # A freshly attached session starts unauthenticated on the server -
        # it does not inherit the socket's auth automatically. Replay the
        # connection's current token so the new session shares the same
        # identity, matching the documented usage where you sign in once on
        # the connection and then open sessions from it. Callers can still
        # sign in / invalidate on the session to change its identity.
        if self.token is not None:
            try:
                self.authenticate(self.token, session_id=session_id)
            except NotAllowedError as e:
                if not e.is_token_expired:
                    self.detach(session_id)
                    raise
                self._note_signed_out(None)
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
        self._shut(_LIVE_KILLED_SENTINEL)

    def _shut(self, live_end: dict[str, Any] = _LIVE_BROKEN_SENTINEL) -> None:
        """Drop the socket and the session state behind it.

        Live subscribers are sent *live_end*: :meth:`close` ends them cleanly,
        as on the async transport, while a dead socket found elsewhere breaks
        them, so a subscriber hears of the failure.
        """
        for queues in self.live_queues.values():
            for notifications in queues:
                notifications.put(live_end)
        # Streams get an error rather than a clean end: a caller iterating rows
        # asked for all of them, and a socket taken away mid-stream means it
        # will not get them. `_connect_locked` shuts a dead socket itself, so
        # this is reachable without the caller closing anything.
        self._break_streams(
            ConnectionUnavailableError(
                "the connection was closed while a streaming query was open."
            )
        )
        self._live_tracker.ended()
        if self.socket is not None:
            try:
                self.socket.close()
            finally:
                self.socket = None
        self._registry.clear()
        self._set_status("disconnected")

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

    def relate(
        self,
        from_: RelateEnd,
        edge: RelateEdge,
        to: RelateEnd,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> Any:
        """Relate *from_* to *to* through *edge*: ``RELATE from->edge->to``.

        *edge* is the edge table (a name or ``Table``), or a ``RecordID`` for
        an edge with a chosen id. *from_* and *to* are records, or lists of
        records to relate every pair. Pass *data* to set the edge's content.
        With *data* the edge is created at once and returned; without it, a
        builder is returned, taking ``.output()`` and ``.timeout()``, to
        finish with ``.execute()`` or ``.content(data)``.
        """
        builder: SyncCrudBuilder[Any] = relate_builder(
            SyncCrudBuilder, self._make_executor(session_id, txn_id), from_, edge, to
        )
        if data is _UNSET:
            return builder
        return builder.content(data)


class BlockingSurrealSession:
    def __init__(
        self,
        connection: BlockingWsSurrealConnection,
        session_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id

    def timeout(self, seconds: float | None) -> AbstractContextManager[None]:
        """Wait *seconds* for each reply inside the block - see the connection's."""
        return self._connection.timeout(seconds)

    @property
    def id(self) -> UUID:
        """The session's id on the server."""
        return self._session_id

    @property
    def server_version(self) -> str | None:
        """The version the connected server reported."""
        return self._connection.server_version

    def use(
        self,
        namespace: str | NullType | None = None,
        database: str | NullType | None = None,
    ) -> None:
        self._connection.use(namespace, database, session_id=self._session_id)

    def refresh(self, tokens: Tokens | None = None) -> Tokens:
        return self._connection.refresh(tokens, session_id=self._session_id)

    def revoke(self, tokens: Tokens | None = None) -> None:
        self._connection.revoke(tokens, session_id=self._session_id)

    def reset(self) -> None:
        self._connection.reset(session_id=self._session_id)

    def fork(self) -> "BlockingSurrealSession":
        """A new session that starts as a copy of this one."""
        return self._connection.fork_session(self._session_id)

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> SyncQueryBuilder:
        return self._connection.query(query, vars, session_id=self._session_id)

    def batch(self) -> Batch:
        """Statements to send together as one transaction, in one request.

        Add them with ``.query(sql, vars)`` and run them with ``.execute()``.
        They all apply or none do. Works on every transport and version.
        """
        return Batch(self)

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

    def set(self, key: str, value: Value) -> None:
        """Set a session variable; ``let`` by its JS name."""
        self.let(key, value)

    def unset(self, key: str) -> None:
        self._connection.unset(key, session_id=self._session_id)

    @overload
    def select(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self, record: str, *, into: type[M]
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def select(self, record: str) -> SyncCrudBuilder[Value]: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
    ) -> SyncCrudBuilder[Any]:
        # Branched because the overloads take `into: type[M]` or nothing, not
        # `type[M] | None` - the same reason the old delegation branched.
        if into is None:
            return self._connection.select(
                record, fields=fields, session_id=self._session_id
            )
        return self._connection.select(
            record, fields=fields, into=into, session_id=self._session_id
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
            return self._connection.create(record, data, session_id=self._session_id)
        return self._connection.create(
            record, data, into=into, session_id=self._session_id
        )

    @overload
    def update(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def update(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def update(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId, data: Value, *, into: type[M]
    ) -> M: ...
    @overload
    def update(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def update(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId, data: Value
    ) -> dict[str, Value]: ...
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
    def upsert(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def upsert(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId, data: Value, *, into: type[M]
    ) -> M: ...
    @overload
    def upsert(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def upsert(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId, data: Value
    ) -> dict[str, Value]: ...
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
    def delete(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self, record: str, *, into: type[M]
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> SyncCrudBuilder[Value]: ...
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

    def api(
        self,
        path: str,
        *,
        method: str = "get",
        body: Value = None,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> ApiResponse:
        return self._connection.api(
            path,
            method=method,
            body=body,
            headers=headers,
            query=query,
            session_id=self._session_id,
        )

    def gql(self, query: str, vars: Mapping[str, Value] | None = None) -> list[Value]:
        return self._connection.gql(query, vars, session_id=self._session_id)

    def graphql(
        self,
        query: str,
        variables: Mapping[str, Value] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Value]:
        return self._connection.graphql(
            query, variables, operation_name, session_id=self._session_id
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
    ) -> LiveSubscription:
        return self._connection.live(table, diff, session_id=self._session_id)

    def live_of(self, live_id: str | UUID) -> LiveSubscription:
        return self._connection.live_of(live_id, session_id=self._session_id)

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

    def relate(
        self,
        from_: RelateEnd,
        edge: RelateEdge,
        to: RelateEnd,
        data: Value = _UNSET,
    ) -> Any:
        return self._connection.relate(
            from_, edge, to, data, session_id=self._session_id
        )


class BlockingSurrealTransaction:
    def __init__(
        self,
        connection: BlockingWsSurrealConnection,
        session_id: UUID | None,
        txn_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id
        self._txn_id = txn_id
        # Set once commit() or cancel() succeeds: the transaction is gone, so
        # leaving a `with` block must not try to finish it again.
        self._finished = False

    def timeout(self, seconds: float | None) -> AbstractContextManager[None]:
        """Wait *seconds* for each reply inside the block - see the connection's."""
        return self._connection.timeout(seconds)

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
    def select(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self, record: str, *, into: type[M]
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def select(self, record: str) -> SyncCrudBuilder[Value]: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
    ) -> SyncCrudBuilder[Any]:
        if into is None:
            return self._connection.select(
                record,
                fields=fields,
                session_id=self._session_id,
                txn_id=self._txn_id,
            )
        return self._connection.select(
            record,
            fields=fields,
            into=into,
            session_id=self._session_id,
            txn_id=self._txn_id,
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
    def update(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def update(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def update(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId, data: Value, *, into: type[M]
    ) -> M: ...
    @overload
    def update(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def update(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId, data: Value
    ) -> dict[str, Value]: ...
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
    def upsert(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M]: ...
    @overload
    def upsert(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId, data: Value, *, into: type[M]
    ) -> M: ...
    @overload
    def upsert(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def upsert(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId, data: Value
    ) -> dict[str, Value]: ...
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
    def delete(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> SyncCrudBuilder[M | None]: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self, record: str, *, into: type[M]
    ) -> SyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(
        self, record: RecordID | StringRecordId
    ) -> SyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> SyncCrudBuilder[Value]: ...
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

    def api(
        self,
        path: str,
        *,
        method: str = "get",
        body: Value = None,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> ApiResponse:
        return self._connection.api(
            path,
            method=method,
            body=body,
            headers=headers,
            query=query,
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
        self._finished = True

    def cancel(self) -> None:
        self._connection.cancel(self._txn_id, session_id=self._session_id)
        self._finished = True

    def set(self, key: str, value: Value) -> None:
        """Set a variable for the rest of the transaction; ``let`` by its JS name."""
        self.let(key, value)

    def __enter__(self) -> "BlockingSurrealTransaction":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._finished:
            return
        if exc_type is None:
            self.commit()
        else:
            self.cancel()

    @property
    def files(self) -> BlockingFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return BlockingFiles(self)

    def relate(
        self,
        from_: RelateEnd,
        edge: RelateEdge,
        to: RelateEnd,
        data: Value = _UNSET,
    ) -> Any:
        return self._connection.relate(
            from_, edge, to, data, session_id=self._session_id, txn_id=self._txn_id
        )
