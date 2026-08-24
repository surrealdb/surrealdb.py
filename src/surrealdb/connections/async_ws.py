"""
A basic async connection to a SurrealDB instance.
"""

import asyncio
import logging
import uuid
import warnings
import weakref
from asyncio import AbstractEventLoop, Future, Queue, Task
from collections.abc import AsyncGenerator, Sequence
from types import TracebackType
from typing import Any, overload
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from surrealdb.connections.async_template import AsyncTemplate
from surrealdb.connections.builders import (
    _UNSET,
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryBuilder,
    M,
    _Executor,
)
from surrealdb.connections.files import AsyncFiles
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import (
    AUTH_FALLBACK_QUERY,
    UtilsMixin,
)
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    ConnectionUnavailableError,
    SurrealError,
    TransportTimeoutError,
    UnexpectedResponseError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.streaming import (
    AsyncQueryStream,
    AsyncStreamOps,
    buffered_statements,
    stream_broken,
)
from surrealdb.types import Tokens, Value, parse_auth_result

logger = logging.getLogger(__name__)

# Sentinel pushed into a live-query queue to tell a ``subscribe_live`` consumer
# to stop iterating. Emitted by ``kill`` (the query was killed) and ``close``
# (the connection is going away) so waiting consumers do not leak.
_LIVE_QUEUE_CLOSED = object()

# Sentinel pushed when the reader stops for any other reason - the peer went
# away, the socket errored, the server restarted. Distinct from
# ``_LIVE_QUEUE_CLOSED`` because it is not a clean end of stream: the consumer
# has to hear that notifications stopped arriving because the connection broke,
# not just that iteration finished. A silent ``return`` here is indistinguishable
# from a ``kill()``, so a consumer would go on believing it had seen every
# change to the table.
_LIVE_QUEUE_BROKEN = object()

# The `action` SurrealDB puts on the notification it sends when a live query
# ends. It reports the end of the subscription rather than a change to the
# table - it carries no record and its `result` is None - so it terminates the
# generator instead of being handed to the consumer.
_LIVE_KILLED = "KILLED"


# Upper bound on how long a single RPC waits for its reply. The blocking
# transport has had one since it was found hanging on a protocol error; without
# the same bound here a caller can wait forever if the reply never arrives.
_RPC_RECV_TIMEOUT = 30.0


def _release_live_queue(
    live_queues: dict[str, list["Queue[Any]"]],
    suid: str,
    result_queue: "Queue[Any]",
) -> None:
    """Deregister one subscriber's queue. Safe to call twice."""
    queues = live_queues.get(suid)
    if queues is None:
        return
    if result_queue in queues:
        queues.remove(result_queue)
    if not queues:
        live_queues.pop(suid, None)


async def _read_frames(
    ref: "weakref.ReferenceType[AsyncWsSurrealConnection]", socket: Any
) -> None:
    """Read frames off *socket* and route them to the connection behind *ref*.

    A module-level function taking a weak reference, rather than a bound method
    on the connection, so that the reader task does not keep the connection
    alive. ``asyncio.create_task(self._recv_task())`` produced exactly that: the
    running loop holds the task, the task holds its coroutine, and the coroutine
    held ``self``. A connection whose last user reference was dropped was
    therefore never collected - so no finaliser ran, and its socket, its file
    descriptor and both worker tasks stayed for the life of the process. Fifty
    connections built in a loop meant fifty live sockets.

    The strong reference is taken per frame and dropped again immediately, so
    between frames - which is where a suspended reader spends essentially all
    of its time - nothing here refers to the connection.
    """
    try:
        async for data in socket:
            connection = ref()
            if connection is None:
                # Nobody is left to route to; stop reading rather than
                # resurrect the connection for the length of a frame.
                return
            try:
                connection._route_frame(data)  # pyright: ignore[reportPrivateUsage]
            finally:
                del connection
    except (ConnectionClosed, WebSocketException, asyncio.CancelledError):
        # Connection was closed or cancelled, this is expected
        pass
    except Exception as e:
        logger.debug(f"Unexpected error in _read_frames: {e}")
    finally:
        connection = ref()
        if connection is not None:
            connection._reader_stopped()  # pyright: ignore[reportPrivateUsage]


def _abandon_connection(
    socket: Any, recv_task: "Task[None] | None", loop: AbstractEventLoop | None
) -> None:
    """Release a websocket nobody closed, without awaiting anything.

    Deliberately not the graceful :meth:`AsyncWsSurrealConnection.close`, for
    the same reason the blocking transport's ``__del__`` is not: a destructor
    cannot await, and the loop that would run the closing handshake is often
    already gone by the time the last reference is dropped (``asyncio.run``
    closes its loop on the way out).

    Two cases, because they need opposite treatment:

    * the loop is still alive - schedule the cancel and the transport abort on
      it, so the socket is torn down by the thread that owns it;
    * the loop is closed - nothing can be scheduled, so close the underlying
      socket object directly. That is what actually releases the file
      descriptor, which is the resource that otherwise accumulates.
    """
    alive = loop if loop is not None and not loop.is_closed() else None

    if recv_task is not None and not recv_task.done():
        try:
            if alive is not None:
                alive.call_soon_threadsafe(recv_task.cancel)
            else:
                recv_task.cancel()
        except RuntimeError:
            pass

    transport = getattr(socket, "transport", None)
    if transport is None:
        return
    if alive is not None:
        try:
            alive.call_soon_threadsafe(transport.abort)
            return
        except RuntimeError:
            pass
    # The real socket, not the ``TransportSocket`` wrapper that
    # `get_extra_info("socket")` returns: closing the wrapper works but is
    # deprecated, and a destructor is the last place that should depend on a
    # deprecated path still being there. Falls back to the wrapper if the
    # private attribute ever goes, since a deprecated close beats a leaked
    # descriptor.
    raw = getattr(transport, "_sock", None)
    if raw is None:
        try:
            raw = transport.get_extra_info("socket")
        except Exception:
            raw = None
    if raw is not None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                raw.close()
        except Exception:
            # Interpreter shutdown can pull what this needs out from under us,
            # and an exception raised here is unraisable anyway.
            pass


class AsyncWsSurrealConnection(AsyncTemplate, UtilsMixin):
    """
    A single async connection to a SurrealDB instance. To be used once and discarded.

    Attributes:
        url: The URL of the database to process queries for.
    """

    def __init__(
        self,
        url: str,
        *,
        streaming: bool = True,
    ) -> None:
        """
        The constructor for the AsyncSurrealConnection class.

        :param url: The URL of the database to process queries for.
        :param streaming: Whether queries may be answered as a stream of frames
            rather than one response. On by default and invisible: the answer is
            the same either way, so this only decides how it arrives. Pass
            ``False`` to put every query back on the buffered path - worth doing
            if a slow consumer of a very large result would rather the server
            waited than the client buffered.
        """
        self.url: Url = Url(url)
        self.raw_url: str = f"{self.url.raw_url}/rpc"
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.token: str | None = None
        self.socket: Any = None  # WebSocket connection
        self.loop: AbstractEventLoop | None = None
        self.qry: dict[str, Future[dict[str, Any]]] = {}
        self.recv_task: Task[None] | None = None
        # Queues hold live-notification dicts plus the ``_LIVE_QUEUE_CLOSED``
        # sentinel, so the value type is ``Any``.
        self.live_queues: dict[str, list[Queue[Any]]] = {}
        # Guards socket creation - see `_connect_guard`. Built on first use
        # rather than here: an `asyncio.Lock` binds to the loop that first
        # awaits it, and these connections are routinely constructed outside
        # the loop that ends up running them.
        self._connect_lock: asyncio.Lock | None = None
        self._connect_lock_loop: AbstractEventLoop | None = None
        # A protocol error the server could not correlate to a request, held
        # until the request it belongs to hits its deadline - see
        # `_deliver_uncorrelated`. `_uncorrelated_for` is the set of request ids
        # that were in flight when it arrived: the rejected frame belongs to one
        # of those and to nothing else.
        self._uncorrelated_error: SurrealError | None = None
        self._uncorrelated_for: set[str] = set()
        # Streaming queries, keyed by the request id whose frames they carry.
        # Separate from ``self.qry`` because a ``query_stream`` request is
        # answered by a *sequence* of responses sharing one id, and a future
        # can only be resolved once: routed through ``self.qry`` the first
        # frame would resolve the call and every frame after it would be
        # dropped. Queues hold decoded frames plus a ``_ChannelBroken``
        # sentinel, so the value type is ``Any``.
        self._streams: dict[str, Queue[Any]] = {}
        # Whether this server knows ``query_stream``: ``None`` until one
        # request settles it. Cached per connection because the answer is a
        # property of the server build, and re-learning it would cost a
        # rejected request on every call.
        self._streaming_supported: bool | None = None
        # Why it refused, when it did - a server older than v3.3.0 and one whose
        # capabilities deny `query_stream` need different advice.
        self._streaming_refusal: str | None = None
        # Whether this connection may stream at all - the driver-level switch,
        # distinct from what the server turned out to support.
        self._streaming_enabled: bool = streaming

    def _connect_guard(self) -> asyncio.Lock:
        """The lock serialising ``connect()``, bound to the running loop.

        Without it, concurrent first requests each saw ``socket is None`` and
        each opened one: N sockets and N reader tasks for one connection, of
        which the object kept only the last. The rest leaked, and every reader
        but one raced to resolve futures on a socket nobody would ever read
        the replies from - so most callers got a spurious
        ``ConnectionUnavailableError`` from a connection that was in fact fine.

        Re-made when the loop changes so a connection reused across
        ``asyncio.run`` calls - each of which builds and discards a loop - does
        not fail on a lock bound to a loop that is gone.
        """
        loop = asyncio.get_running_loop()
        if self._connect_lock is None or self._connect_lock_loop is not loop:
            self._connect_lock = asyncio.Lock()
            self._connect_lock_loop = loop
        return self._connect_lock

    def _fail_pending(self, error: BaseException) -> None:
        """Hand *error* to every caller currently awaiting a reply."""
        for fut in self.qry.values():
            if not fut.done():
                fut.set_exception(error)
        self.qry.clear()
        self._break_streams(error)

    def _break_streams(self, error: BaseException) -> None:
        """Tell every open stream that no more frames are coming.

        Streams wait on a queue rather than on ``self.qry``, so failing the
        pending futures leaves them untouched - the same trap live subscribers
        fell into, where nothing was ever put in the queue again and the
        consumer waited forever with no timeout on the path. A stream's frames
        are unbounded by design once it has opened, which makes this the only
        thing that ends one when the socket goes away.
        """
        for frames in self._streams.values():
            frames.put_nowait(stream_broken(error))

    def _deliver_uncorrelated(self, error: SurrealError) -> None:
        """Deliver an error the server could not tie to any request.

        A protocol-level error arrives with no ``id`` because the server could
        not parse the frame far enough to read one. Exactly *one* request is
        affected - the one whose frame was rejected - and it is the one that
        will never be answered. Every other request in flight is untouched and
        gets its own reply as normal.

        Failing every pending future, which is what this used to do, turned one
        bad request into N failures: three unrelated queries on the same
        connection all came back ``Parse error`` because a fourth, concurrent
        one was malformed. The same three run alone succeeded.

        With a single request in flight there is no ambiguity, so it is failed
        straight away. With several, the error is held instead: the doomed
        request is the one that never gets a reply, so it is the one that hits
        its deadline, and :meth:`_send` reports this error there rather than a
        bare timeout. That costs the doomed caller its timeout - which is
        unavoidable, since nothing on the wire says which one it is - while
        letting the others finish normally.
        """
        pending = [
            (query_id, fut) for query_id, fut in self.qry.items() if not fut.done()
        ]
        # A streaming query in flight is a candidate exactly as a pending call
        # is: it too sent a frame the server may have rejected, and now that
        # `query()` streams, most requests are of that kind. Leaving streams out
        # meant the error was held for `self.qry` ids alone, so a streamed
        # request that was the doomed one waited out its opening deadline and
        # reported a bare timeout instead of the parse error the server sent.
        candidates = {query_id for query_id, _ in pending} | set(self._streams)
        if len(candidates) == 1 and pending:
            query_id, fut = pending[0]
            fut.set_exception(error)
            self.qry.pop(query_id, None)
            return
        # A streaming query in flight is a candidate too, and when it is the
        # only one the error belongs to it. Without this the frame the server
        # rejected went unreported: the error was held for a `self.qry` entry
        # that did not exist, and the stream waited out its opening deadline
        # and blamed a timeout for what was really a parse error. It is handed
        # over as the end-of-frames sentinel, which carries the parsed error
        # itself - re-encoding it as a response would flatten a typed error
        # back into its message.
        if len(candidates) == 1:
            for frames in self._streams.values():
                frames.put_nowait(stream_broken(error))
            return
        self._uncorrelated_error = error
        self._uncorrelated_for = candidates

    def _take_uncorrelated(self, query_id: str) -> SurrealError | None:
        """Consume a held protocol error if it can belong to *query_id*.

        Only a request that was already in flight when the error arrived can be
        the one whose frame the server rejected; anything started afterwards has
        its own reply coming. Handing the error to whichever request happened to
        time out next told a caller its own perfectly valid query had a parse
        error - a request that was not even sent when the failure happened.
        """
        if self._uncorrelated_error is None or query_id not in self._uncorrelated_for:
            return None
        error = self._uncorrelated_error
        self._forget_uncorrelated()
        return error

    def _forget_uncorrelated(self) -> None:
        """Drop a held error once it can no longer belong to anyone."""
        self._uncorrelated_error = None
        self._uncorrelated_for = set()

    def _prune_uncorrelated(self) -> None:
        """Forget a held error whose candidates have all gone away.

        A caller that abandons its request - an application-level timeout, a
        cancelled task - never reaches the deadline that would have collected
        the error, so without this it would sit there waiting to ambush an
        unrelated request much later.
        """
        if self._uncorrelated_error is None:
            return
        self._uncorrelated_for &= self.qry.keys() | self._streams.keys()
        if not self._uncorrelated_for:
            self._forget_uncorrelated()

    def _route_frame(self, data: Any) -> None:
        """Hand one received frame to whoever is waiting for it."""
        # A single frame this loop cannot handle must not end it. When it did,
        # the socket stayed open - so `connect()` saw a live socket and
        # no-opped, and every later request registered a future that nothing
        # would ever resolve. The caller then waited forever, with no timeout
        # anywhere on this path.
        try:
            response = decode(data)
        except Exception as exc:
            self._fail_pending(
                UnexpectedResponseError(f"could not decode a websocket frame: {exc}")
            )
            return

        try:
            if response_id := response.get("id"):
                # Streams first: a streaming query's id stays registered for
                # the whole sequence of frames, while ``self.qry`` holds ids
                # that are answered once.
                if (frames := self._streams.get(response_id)) is not None:
                    frames.put_nowait(response)
                elif (fut := self.qry.get(response_id)) and not fut.done():
                    fut.set_result(response)
            elif response_result := response.get("result"):
                live_id = str(response_result["id"])
                for queue in self.live_queues.get(live_id, []):
                    queue.put_nowait(response_result)
            else:
                # An id-less frame carrying no result is a protocol-level error
                # the server could not correlate to a request, so everyone in
                # flight has to hear it.
                try:
                    self.check_response_for_error(response, "_recv_task")
                except SurrealError as exc:
                    self._deliver_uncorrelated(exc)
        except Exception as exc:
            self._fail_pending(
                UnexpectedResponseError(f"could not route a websocket frame: {exc}")
            )

    def _reader_stopped(self) -> None:
        """Tell everyone still waiting that no more frames are coming."""
        # Fail any pending futures with a typed error so awaiting callers
        # surface ``ConnectionUnavailableError`` instead of a raw
        # ``CancelledError`` when the socket closes mid-request.
        self._fail_pending(
            ConnectionUnavailableError(
                "WebSocket connection closed before a response was received."
            )
        )
        # Live subscribers wait on a queue, not on `self.qry`, so failing the
        # pending futures left them untouched: nothing would ever be put in
        # their queue again and `async for` waited forever, with no timeout on
        # the path. The blocking transport has always raised
        # `ConnectionUnavailableError` here.
        for queues in self.live_queues.values():
            for queue in queues:
                queue.put_nowait(_LIVE_QUEUE_BROKEN)

    async def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict[str, Any]:
        await self.connect()
        assert (
            self.socket is not None and self.loop is not None
        )  # will always not be None as the self.connect ensures there's a connection

        # setup future to wait for response
        fut = self.loop.create_future()
        query_id = message.id
        self.qry[query_id] = fut
        try:
            # correlate message to query, send and forget it
            try:
                await self.socket.send(message.WS_CBOR_DESCRIPTOR)
            except (WebSocketException, OSError) as exc:
                raise ConnectionUnavailableError(
                    f"the connection to {self.raw_url} failed while {process}: {exc}"
                ) from exc
            del message

            # wait for response, bounded so a reply that never arrives cannot
            # block the caller forever
            try:
                response = await asyncio.wait_for(fut, _RPC_RECV_TIMEOUT)
            except asyncio.TimeoutError as exc:
                # The server may have rejected this request's frame outright,
                # in which case it answered with an error carrying no `id` and
                # no reply is ever coming. That error was held rather than
                # failing every other request in flight; this is the request it
                # belongs to, so report it instead of a bare deadline.
                uncorrelated = self._take_uncorrelated(query_id)
                if uncorrelated is not None:
                    raise uncorrelated from exc
                raise TransportTimeoutError(
                    f"timed out while {process} on {self.raw_url}: no reply "
                    f"within {_RPC_RECV_TIMEOUT}s"
                ) from exc
        finally:
            # ``_recv_task`` clears ``self.qry`` when the socket closes, so the
            # key may already be gone; ``pop`` avoids a spurious ``KeyError``.
            self.qry.pop(query_id, None)
            self._prune_uncorrelated()

        if bypass is False:
            self.check_response_for_error(response, process)

        # Response comes from Future[dict[str, Any]] defined in self.qry
        # The decode() function returns Any, but we know it's always a dict in this context
        if not isinstance(response, dict):
            # This should never happen in practice, but handle defensively
            return {}
        # Return type is dict[str, Any] - contents are dynamic database responses
        # Cannot be more specific without runtime schema validation
        return response

    def _check_event_loop(self) -> None:
        """Refuse to use a socket that belongs to a different event loop.

        Every awaiting caller's future is created on ``self.loop``, and the
        reader that resolves them runs there too. Used from a second loop, the
        first ``await`` failed deep inside asyncio with
        ``ValueError: The future belongs to a different loop than the one
        specified as the loop argument`` - a message with nothing in it about
        connections, event loops the *caller* controls, or what to do next.
        The connection was then wedged: the request stayed in ``self.qry``, and
        every later call failed the same way.

        Two loops in one program is not exotic - ``asyncio.run`` builds and
        destroys one per call, so reusing a connection across two of them is
        enough. Reconnecting silently instead would trade this for a worse
        failure: a new socket is a new server-side session, so the next
        statement would come back ``NotAllowedError`` from a connection the
        caller had already signed in.
        """
        if self.socket is None or self.loop is None:
            return
        running = asyncio.get_running_loop()
        if running is self.loop:
            return
        state = "closed" if self.loop.is_closed() else "still running"
        raise ConnectionUnavailableError(
            f"this connection to {self.raw_url} belongs to a different event "
            f"loop (which is {state}), so it cannot be used from this one. A "
            "connection is bound to the loop it was opened on - build a new "
            "one for this loop, or keep all of its work on a single loop "
            "(one asyncio.run call, not several)."
        )

    async def connect(self, url: str | None = None) -> None:
        # Serialised: `_send` calls this on every request, so the first few
        # requests of a gathered batch all arrive here at once.
        self._check_event_loop()
        async with self._connect_guard():
            await self._connect_locked(url)

    async def _connect_locked(self, url: str | None = None) -> None:
        if (
            url is not None
            and self.socket is not None
            and f"{Url(url).raw_url}/rpc" != self.raw_url
        ):
            # Re-pointing an open connection has to replace the socket, or it
            # keeps talking to the previous endpoint while reporting the new
            # URL - the early return below would otherwise swallow *url*. Only
            # for a *different* endpoint: re-pointing costs the server-side
            # session, so a defensive `connect(url)` naming the endpoint
            # already in use must not quietly discard a completed `signin()`.
            await self.close()

        if self.socket is not None:
            if self.recv_task is None or not self.recv_task.done():
                return
            # The reader ran and stopped while the socket stayed open, so this
            # used to be a silent no-op that left the connection permanently
            # unusable - every later request waited on a future nothing would
            # resolve. Tear it down and reconnect. Deliberately narrow: a
            # socket with no reader at all is left alone, since that is not the
            # state this guards against.
            await self.close()

        # overwrite params if passed in
        if url is not None:
            self.url = Url(url)
            self.raw_url = f"{self.url.raw_url}/rpc"
            self.host = self.url.hostname
            self.port = self.url.port

        try:
            self.socket = await websockets.connect(
                self.raw_url,
                max_size=None,
                subprotocols=[websockets.Subprotocol("cbor")],
            )
        except asyncio.TimeoutError as exc:
            raise TransportTimeoutError(
                f"timed out connecting to {self.raw_url}: {exc}"
            ) from exc
        except (WebSocketException, OSError) as exc:
            raise ConnectionUnavailableError(
                f"could not connect to {self.raw_url}: {exc}"
            ) from exc
        self.loop = asyncio.get_running_loop()
        self.recv_task = asyncio.create_task(
            _read_frames(weakref.ref(self), self.socket)
        )

    async def authenticate(self, token: str, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"token": token}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.AUTHENTICATE, **kwargs)
        await self._send(message, "authenticating")
        # Record the token as the connection identity so new_session() can
        # replay it — only when authenticating the connection, not a sub-session.
        if session_id is None:
            self.token = token

    async def invalidate(self, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INVALIDATE, **kwargs)
        await self._send(message, "invalidating")
        self.token = None

    async def signup(
        self, vars: dict[str, Value], session_id: UUID | None = None
    ) -> Tokens:
        kwargs: dict[str, Any] = {"data": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_UP, **kwargs)
        response = await self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def signin(
        self, vars: dict[str, Value], session_id: UUID | None = None
    ) -> Tokens:
        kwargs: dict[str, Any] = {"params": vars}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.SIGN_IN, **kwargs)
        response = await self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def info(self, session_id: UUID | None = None) -> Value:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.INFO, **kwargs)
        response = await self._send(
            message, "getting database information", bypass=True
        )

        if response.get("error") is not None:
            # Record-auth sessions have no ROOT/NS/DB info; re-resolve the
            # authenticated record via `$auth`.
            if self._info_needs_auth_fallback(response):
                record = self._extract_auth_record(
                    await self._buffered_first(AUTH_FALLBACK_QUERY, session_id)
                )
                if record is not None:
                    return record
            raise parse_rpc_error(response["error"])

        self.check_response_for_result(response, "getting auth information")
        return response["result"]

    async def use(
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
        await self._send(message, "use")

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncQueryBuilder:
        """Run SurrealQL and return an awaitable builder.

        Awaiting it (or ``.execute()``) returns ``list[Value]`` - one entry per
        statement, always a list (the v3 fix for issue #232). Use ``.first()``
        for the first statement's result, or ``.into(cls)`` to map the results
        onto a dataclass / class.
        """
        return AsyncQueryBuilder(
            executor=self._make_executor(session_id, txn_id),
            query=query,
            variables=vars,
        )

    async def query_raw(
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
            streamed = await AsyncQueryStream(
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
        response = await self._send(message, "query", bypass=True)
        return response

    async def _buffered_first(
        self, query: str, session_id: UUID | None
    ) -> Value | None:
        """Run *query* buffered and return its first statement's result.

        For the queries the SDK issues on its own behalf. Streaming exists to
        get a caller's data moving sooner; a one-row internal lookup gains
        nothing from frames, and putting `query_stream` on the wire for
        something nobody asked for makes the SDK's own traffic harder to reason
        about - and harder to assert on, which is how this was noticed.
        """
        kwargs: dict[str, Any] = {"query": query, "params": {}}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.QUERY, **kwargs)
        response = await self._send(message, "getting auth information", bypass=True)
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

        A query on a client transaction never is. It would run on the
        transaction `begin` handed out, and requests on one connection are
        served concurrently, so a `commit` arriving mid-stream would commit a
        prefix of the query rather than the whole of it. Excluding them removes
        the hazard instead of documenting it.
        """
        if not self._streaming_enabled or txn_id is not None:
            return False
        return self._streaming_supported is not False

    def _stream_ops(self) -> AsyncStreamOps:
        """Bind the operations a streaming query drives.

        Bound methods rather than the connection itself, so a stream reaches
        only what it needs: it cannot connect or close, and it can only ask the
        pending-request machinery whether a held protocol error is its own.
        """
        return AsyncStreamOps(
            registry=self._streams,
            open_timeout=_RPC_RECV_TIMEOUT,
            open=self._stream_open,
            release=self._stream_release,
            send=self._stream_send,
            cancel=self._stream_cancel,
            buffered=self._stream_buffered,
            supported=self._stream_supported,
            set_supported=self._stream_set_supported,
            refusal=self._stream_refusal,
            take_uncorrelated=self._take_uncorrelated,
        )

    async def _stream_open(self, request_id: str) -> Queue[Any]:
        """Register *request_id* and return the queue its frames arrive on.

        Registered before the request is sent, so the reader cannot deliver a
        frame - or the immediate rejection of an unknown method - before there
        is anywhere to put it.

        The queue is unbounded, and deliberately so. A bounded one would have
        to stall the shared reader task when it filled, which deadlocks the
        common pattern of running another query for each row: the reader would
        be waiting for the consumer, and the consumer waiting for a reply the
        stalled reader is holding. The protocol offers no per-stream flow
        control, so a consumer slower than the server buffers rows in memory
        until it catches up; ``.statements()``, or stopping the stream early,
        are the ways out.
        """
        await self.connect()
        frames: Queue[Any] = Queue()
        self._streams[request_id] = frames
        return frames

    def _stream_release(self, request_id: str) -> None:
        """Deregister a stream. Safe to call twice."""
        self._streams.pop(request_id, None)
        # A held protocol error may have been waiting for this stream to collect
        # it; with the stream gone it cannot belong to it, and keeping it would
        # let it ambush an unrelated request much later.
        self._prune_uncorrelated()

    async def _stream_send(self, message: RequestMessage) -> None:
        """Send *message* without registering a reply future.

        Not :meth:`_send`: that awaits exactly one response and pops the id
        when it arrives, which would resolve the call on the first frame and
        then route every frame after it nowhere.
        """
        await self.connect()
        assert self.socket is not None
        try:
            await self.socket.send(message.WS_CBOR_DESCRIPTOR)
        except (WebSocketException, OSError) as exc:
            raise ConnectionUnavailableError(
                f"the connection to {self.raw_url} failed while starting a "
                f"streaming query: {exc}"
            ) from exc

    async def _stream_cancel(self, request_id: str) -> None:
        """Ask the server to stop the stream *request_id* opened.

        A no-op once the socket has gone: there is nothing left to tell, and
        going through :meth:`_send` would call ``connect()`` and reopen the
        connection a caller had just closed - on a new session, where the
        stream does not exist.
        """
        if self.socket is None:
            return
        message = RequestMessage(RequestMethod.QUERY_CANCEL, stream=request_id)
        await self._send(message, "cancelling a streaming query")

    async def _stream_buffered(
        self,
        query: str,
        variables: dict[str, Value],
        session_id: UUID | None,
        txn_id: UUID | None,
    ) -> list[dict[str, Any]]:
        """Run *query* the buffered way, for a server without streaming."""
        response = await self.query_raw(query, variables, session_id, txn_id)
        return buffered_statements(response)

    def _stream_supported(self) -> bool | None:
        return self._streaming_supported

    def _stream_refusal(self) -> str | None:
        return self._streaming_refusal

    def _stream_set_supported(self, supported: bool, reason: str | None) -> None:
        self._streaming_supported = supported
        self._streaming_refusal = reason

    async def version(self, session_id: UUID | None = None) -> str:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.VERSION, **kwargs)
        response = await self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    async def let(
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
        await self._send(message, "letting")

    async def unset(
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
        await self._send(message, "unsetting")

    @overload
    def select(
        self,
        record: RecordID,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        fields: Sequence[str] | None = None,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(
        self,
        record: RecordID,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(
        self,
        record: Table,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def select(
        self,
        record: str,
        *,
        fields: Sequence[str] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Value]: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Select records.

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
        return AsyncCrudBuilder(
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
        """Build the executor a builder terminates through.

        Callable for the buffered answer, ``.stream()`` for the rows as they
        arrive. Both carry this builder's session and transaction, so a
        streamed `select()` runs in the same place its awaited form would.
        """

        async def _executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
            return await self.query_raw(
                query, params, session_id=session_id, txn_id=txn_id
            )

        def _stream(
            query: str,
            params: dict[str, Value] | None,
            *,
            require_streaming: bool = False,
        ) -> AsyncQueryStream:
            return AsyncQueryStream(
                self._stream_ops(),
                query,
                params or None,
                session_id=session_id,
                txn_id=txn_id,
                require_streaming=require_streaming,
            )

        return _Executor(_executor, _stream)

    # CRUD overloads --------------------------------------------------------

    @overload
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def create(
        self,
        record: RecordID,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self,
        record: Table,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self,
        record: str,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Create a record; returns an awaitable builder.

        ``await db.create(record, data)`` is sugar for
        ``await db.create(record).content(data)``. Clause methods
        (``.content`` / ``.replace`` / ``.merge`` / ``.patch``) return the
        builder so it stays awaitable. Pass ``into=Model`` to map the created
        record onto ``Model``.
        """
        builder: AsyncCrudBuilder[Any] = AsyncCrudBuilder(
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
        data: Value = _UNSET,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def update(
        self,
        record: Table,
        data: Value = _UNSET,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def update(
        self,
        record: str,
        data: Value = _UNSET,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self,
        record: RecordID,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self,
        record: Table,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def update(
        self,
        record: str,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Value]: ...
    def update(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Update records; returns an awaitable builder.

        Optional clause methods ``.content`` / ``.replace`` / ``.merge`` /
        ``.patch`` return the builder so it stays awaitable. Pass ``into=Model``
        to map the returned record(s) onto ``Model`` / ``list[Model]``.
        """
        builder: AsyncCrudBuilder[Any] = AsyncCrudBuilder(
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
        data: Value = _UNSET,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def upsert(
        self,
        record: Table,
        data: Value = _UNSET,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(
        self,
        record: str,
        data: Value = _UNSET,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self,
        record: RecordID,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self,
        record: Table,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(
        self,
        record: str,
        data: Value = _UNSET,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Value]: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Insert or update records; returns an awaitable builder.

        Optional clause methods ``.content`` / ``.replace`` / ``.merge`` /
        ``.patch`` return the builder so it stays awaitable. Pass ``into=Model``
        to map the returned record(s) onto ``Model`` / ``list[Model]``.
        """
        builder: AsyncCrudBuilder[Any] = AsyncCrudBuilder(
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
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def delete(
        self,
        record: Table,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self,
        record: str,
        *,
        into: type[M],
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(
        self,
        record: RecordID,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(
        self,
        record: Table,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(
        self,
        record: str,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Value]: ...
    def delete(
        self,
        record: RecordIdType,
        *,
        into: type[M] | None = None,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Delete records; returns an awaitable builder.

        A ``RecordID`` (or ``"table:id"``) resolves to the deleted record, or
        ``None`` when no record was deleted (matching select); a ``Table`` (or
        bare name) to the list of deleted records. ``DELETE`` has no clause
        methods. Pass ``into=Model`` to map the deleted record(s) onto ``Model``.
        """
        return AsyncCrudBuilder(
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
        data: Value = _UNSET,
        *,
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M],
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncInsertBuilder[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
    ) -> AsyncInsertBuilder[Any]:
        """Insert record(s) or relation(s); returns an awaitable builder.

        Pass ``relation=True`` (or chain ``.relation()``) for ``INSERT
        RELATION INTO``. Awaiting the builder (or ``.execute()``) runs it. Pass
        ``into=Model`` to map the inserted records onto ``list[Model]``.
        """
        builder: AsyncInsertBuilder[Any] = AsyncInsertBuilder(
            executor=self._make_executor(session_id, txn_id),
            table=table,
            relation=relation,
            into=into,
        )
        if data is _UNSET:
            return builder
        return builder.content(data)

    async def run(
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
        response = await self._send(message, "run")
        self.check_response_for_result(response, "run")
        return response["result"]

    async def live(
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
        response = await self._send(message, "live")
        self.check_response_for_result(response, "live")
        uuid = response["result"]
        assert uuid not in self.live_queues
        self.live_queues[str(uuid)] = []
        return uuid

    async def subscribe_live(
        self, query_uuid: str | UUID
    ) -> AsyncGenerator[dict[str, Value], None]:
        """Return an async generator yielding notifications for a live query.

        Multiple consumers may subscribe to the same ``query_uuid``; each gets
        its own queue and receives every notification. The generator ends
        (a plain ``return``, so ``async for`` stops cleanly) when the query is
        killed via :meth:`kill` or the connection is closed via :meth:`close`.

        :raises ConnectionUnavailableError: if the connection drops while the
            subscription is active. That is not a clean end of stream - some
            changes to the table went undelivered - so it is raised rather than
            ending the iteration, matching the blocking transport.
        """
        result_queue: Queue[Any] = Queue()
        suid = str(query_uuid)

        # Auto-register if not already registered
        if suid not in self.live_queues:
            self.live_queues[suid] = []

        self.live_queues[suid].append(result_queue)

        async def _iter() -> AsyncGenerator[dict[str, Any], None]:
            try:
                while True:
                    ret = await result_queue.get()
                    # ``kill`` / ``close`` push this sentinel to wake waiting
                    # consumers so the generator terminates instead of leaking.
                    if ret is _LIVE_QUEUE_CLOSED:
                        return
                    if ret is _LIVE_QUEUE_BROKEN:
                        raise ConnectionUnavailableError(
                            "WebSocket connection closed while subscribed to "
                            f"live query {suid}."
                        )
                    # The server's own end-of-subscription marker. `kill()`
                    # here pushes the sentinel above and never reaches this,
                    # but a query killed by anyone else - another connection,
                    # or the server - arrives only as this notification, and
                    # yielding it handed the consumer a notification whose
                    # `result` was None before iterating on forever.
                    if isinstance(ret, dict) and ret.get("action") == _LIVE_KILLED:
                        return
                    yield ret
            finally:
                # Deregister this consumer's queue when the generator is
                # closed (consumer break, GC, kill, or close).
                queues = self.live_queues.get(suid)
                if queues is not None and result_queue in queues:
                    queues.remove(result_queue)

        subscription = _iter()
        # Registration happens above, before anything is iterated, so release
        # has to be reachable without iterating. A generator that is never
        # started does not run its `finally` on close or GC, so a subscription
        # set up and then abandoned stayed registered for the life of the
        # connection while notifications kept filling a queue nobody drains.
        #
        # Closing over `live_queues` rather than `self`, so the finalizer does
        # not keep the connection alive for as long as the generator.
        weakref.finalize(
            subscription, _release_live_queue, self.live_queues, suid, result_queue
        )
        return subscription

    async def kill(
        self,
        query_uuid: str | UUID,
        session_id: UUID | None = None,
    ) -> None:
        """Kill a running live query by its UUID."""
        kwargs: dict[str, Any] = {"uuid": query_uuid}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.KILL, **kwargs)
        await self._send(message, "kill")
        # Wake any subscribers so their generators terminate, then drop the
        # registration. Each ``_iter`` removes its own queue in its ``finally``.
        suid = str(query_uuid)
        for queue in self.live_queues.get(suid, []):
            queue.put_nowait(_LIVE_QUEUE_CLOSED)
        self.live_queues.pop(suid, None)

    async def attach(self) -> UUID:
        session_id = UUID(str(uuid.uuid4()))
        message = RequestMessage(RequestMethod.ATTACH, session=session_id)
        await self._send(message, "attach")
        return session_id

    async def detach(self, session_id: UUID) -> None:
        message = RequestMessage(RequestMethod.DETACH, session=session_id)
        await self._send(message, "detach")

    async def begin(self, session_id: UUID | None = None) -> UUID:
        kwargs: dict[str, Any] = {}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.BEGIN, **kwargs)
        response = await self._send(message, "begin")
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

    async def commit(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        kwargs: dict[str, Any] = {"txn": txn_id}
        if session_id is not None:
            kwargs["session"] = session_id
        message = RequestMessage(RequestMethod.COMMIT, **kwargs)
        await self._send(message, "commit")

    async def cancel(self, txn_id: UUID, session_id: UUID | None = None) -> None:
        if session_id is not None:
            message = RequestMessage(
                RequestMethod.CANCEL, txn=txn_id, session=session_id
            )
        else:
            message = RequestMessage(RequestMethod.CANCEL, txn=txn_id)
        await self._send(message, "cancel")

    async def new_session(self) -> "AsyncSurrealSession":
        session_id = await self.attach()
        # A freshly attached session starts unauthenticated on the server -
        # it does not inherit the socket's auth automatically. Replay the
        # connection's current token so the new session shares the same
        # identity, matching the documented usage where you sign in once on
        # the connection and then open sessions from it. Callers can still
        # sign in / invalidate on the session to change its identity.
        if self.token is not None:
            await self.authenticate(self.token, session_id=session_id)
        return AsyncSurrealSession(self, session_id)

    async def close(self) -> None:
        """Close the websocket, if one is open. Idempotent.

        Usable from a loop other than the one the connection was opened on,
        unlike every other method: cancelling and awaiting a task that belongs
        to another loop cannot work, so that case falls back to the same
        non-awaiting teardown the destructor uses. Without it the advice
        :meth:`_check_event_loop` gives - build a new connection for this loop -
        left the old one with no way to release its socket.
        """
        # Wake any live subscribers so their generators terminate instead of
        # waiting forever on a socket that is about to disappear.
        for queues in self.live_queues.values():
            for queue in queues:
                queue.put_nowait(_LIVE_QUEUE_CLOSED)

        # Streams get an error rather than a clean-end sentinel: a caller
        # iterating rows asked for all of them, and a socket taken away
        # mid-stream means it will not get them. `close()` does not go through
        # `_fail_pending`, so without this a stream would wait on a queue that
        # nothing will ever fill again - and `_connect_locked` calls `close()`
        # itself when it finds a dead reader on a live socket, so this is
        # reachable without the caller closing anything.
        self._break_streams(
            ConnectionUnavailableError(
                "the connection was closed while a streaming query was open."
            )
        )

        if self.loop is not None and self.loop is not asyncio.get_running_loop():
            _abandon_connection(self.socket, self.recv_task, self.loop)
            self.socket = None
            self.recv_task = None
            self._forget_uncorrelated()
            return

        # Cancel the receive task first
        if self.recv_task and not self.recv_task.done():
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass
            except Exception:
                # Ignore any other exceptions during cleanup
                pass

        # Close the WebSocket connection
        if self.socket is not None:
            try:
                await self.socket.close()
            except Exception:
                # Ignore exceptions during socket closure
                pass
            finally:
                self.socket = None
                self.recv_task = None

        # Unconditionally, not only when there was a socket to close: a new
        # socket is a new conversation, and nothing about the old one may be
        # waiting to be delivered into it.
        self._forget_uncorrelated()

    def __del__(self) -> None:
        """Release the socket if the connection is dropped without ``close()``.

        Each open connection holds a TCP socket and a file descriptor, plus its
        own reader task and the ``websockets`` keepalive task. Nothing else
        released them, so a program that built connections and let them go out
        of scope accumulated all four per connection until the process exited -
        and because ``asyncio.run`` closes its loop, the leftover tasks also
        produced "Task was destroyed but it is pending!" on the way out, which
        reads as a bug in the caller's code rather than in the connection.

        The warning is a ``ResourceWarning``, like the one an unclosed file
        gives: off by default, visible under ``-W default`` and in tests.
        """
        socket = getattr(self, "socket", None)
        recv_task = getattr(self, "recv_task", None)
        if socket is None and recv_task is None:
            return
        # `try`/`except`, not `contextlib.suppress`: this runs in a destructor,
        # and at interpreter shutdown a module-global lookup can already have
        # been torn down - which is the same reason the body below is defensive
        # at all. `BlockingWsSurrealConnection.__del__` is written the same way.
        # No `stacklevel` either: the "caller" of a destructor is whatever
        # happened to drop the last reference, so pointing at it misattributes
        # the warning. `source=self` is what identifies the leaked connection.
        try:  # noqa: SIM105
            warnings.warn(  # noqa: B028 - see the comment above
                f"unclosed connection to {getattr(self, 'raw_url', '?')} - "
                "await close(), or use `async with`",
                ResourceWarning,
                source=self,
            )
        except Exception:
            pass
        _abandon_connection(socket, recv_task, getattr(self, "loop", None))

    async def __aenter__(self) -> "AsyncWsSurrealConnection":
        """
        Asynchronous context manager entry.
        Initializes a websocket connection and returns the connection instance.
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Asynchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        await self.close()

    @property
    def files(self) -> AsyncFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return AsyncFiles(self)


class AsyncSurrealSession:
    def __init__(
        self,
        connection: AsyncWsSurrealConnection,
        session_id: UUID,
    ) -> None:
        self._connection = connection
        self._session_id = session_id

    async def use(self, namespace: str, database: str) -> None:
        await self._connection.use(namespace, database, session_id=self._session_id)

    def query(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> AsyncQueryBuilder:
        return self._connection.query(query, vars, session_id=self._session_id)

    async def query_raw(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> dict[str, Any]:
        return await self._connection.query_raw(
            query, vars, session_id=self._session_id
        )

    async def signin(self, vars: dict[str, Value]) -> Tokens:
        return await self._connection.signin(vars, session_id=self._session_id)

    async def signup(self, vars: dict[str, Value]) -> Tokens:
        return await self._connection.signup(vars, session_id=self._session_id)

    async def authenticate(self, token: str) -> None:
        await self._connection.authenticate(token, session_id=self._session_id)

    async def invalidate(self) -> None:
        await self._connection.invalidate(session_id=self._session_id)

    async def info(self) -> Value:
        return await self._connection.info(session_id=self._session_id)

    async def version(self) -> str:
        return await self._connection.version(session_id=self._session_id)

    async def let(self, key: str, value: Value) -> None:
        await self._connection.let(key, value, session_id=self._session_id)

    async def unset(self, key: str) -> None:
        await self._connection.unset(key, session_id=self._session_id)

    @overload
    def select(
        self, record: RecordID, *, into: type[M]
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self, record: str, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(self, record: RecordID) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(self, record: Table) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def select(self, record: str) -> AsyncCrudBuilder[Value]: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
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
    def create(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def create(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.create(record, data, session_id=self._session_id)
        return self._connection.create(
            record, data, into=into, session_id=self._session_id
        )

    @overload
    def update(
        self, record: RecordID, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def update(
        self, record: Table, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def update(
        self, record: str, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str, data: Value = _UNSET) -> AsyncCrudBuilder[Value]: ...
    def update(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.update(record, data, session_id=self._session_id)
        return self._connection.update(
            record, data, into=into, session_id=self._session_id
        )

    @overload
    def upsert(
        self, record: RecordID, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def upsert(
        self, record: Table, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(
        self, record: str, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str, data: Value = _UNSET) -> AsyncCrudBuilder[Value]: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.upsert(record, data, session_id=self._session_id)
        return self._connection.upsert(
            record, data, into=into, session_id=self._session_id
        )

    @overload
    def delete(
        self, record: RecordID, *, into: type[M]
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self, record: str, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(self, record: RecordID) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(self, record: Table) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> AsyncCrudBuilder[Value]: ...
    def delete(
        self, record: RecordIdType, *, into: type[M] | None = None
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.delete(record, session_id=self._session_id)
        return self._connection.delete(record, into=into, session_id=self._session_id)

    @overload
    def insert(
        self, table: str | Table, data: Value = _UNSET, *, relation: bool = False
    ) -> AsyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M],
        relation: bool = False,
    ) -> AsyncInsertBuilder[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> AsyncInsertBuilder[Any]:
        if into is None:
            return self._connection.insert(
                table, data, relation=relation, session_id=self._session_id
            )
        return self._connection.insert(
            table, data, into=into, relation=relation, session_id=self._session_id
        )

    async def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        return await self._connection.run(
            name, args, version, session_id=self._session_id
        )

    async def live(
        self,
        table: str | Table,
        diff: bool = False,
    ) -> UUID:
        return await self._connection.live(table, diff, session_id=self._session_id)

    async def kill(self, query_uuid: str | UUID) -> None:
        await self._connection.kill(query_uuid, session_id=self._session_id)

    async def subscribe_live(
        self, query_uuid: str | UUID
    ) -> AsyncGenerator[dict[str, Value], None]:
        """Return an async generator of notifications for a live query.

        The session exposed :meth:`live` and :meth:`kill` but not this, so a
        session could start a live query it had no way to consume - callers had
        to reach past the wrapper to the underlying connection. Subscriptions
        are keyed by the live-query id rather than the session, so this
        forwards unchanged.

        Awaited like the connection's own, since that builds the generator and
        returns it rather than being an async generator function itself::

            notifications = await session.subscribe_live(live_id)
            async for change in notifications:
                ...
        """
        return await self._connection.subscribe_live(query_uuid)

    async def begin_transaction(self) -> "AsyncSurrealTransaction":
        txn_id = await self._connection.begin(session_id=self._session_id)
        return AsyncSurrealTransaction(self._connection, self._session_id, txn_id)

    async def close_session(self) -> None:
        await self._connection.detach(self._session_id)

    @property
    def files(self) -> AsyncFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return AsyncFiles(self)


class AsyncSurrealTransaction:
    def __init__(
        self,
        connection: AsyncWsSurrealConnection,
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
    ) -> AsyncQueryBuilder:
        return self._connection.query(
            query,
            vars,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def query_raw(
        self,
        query: str,
        vars: dict[str, Value] | None = None,
    ) -> dict[str, Any]:
        return await self._connection.query_raw(
            query,
            vars,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def info(self) -> Value:
        return await self._connection.info(session_id=self._session_id)

    async def version(self) -> str:
        return await self._connection.version(session_id=self._session_id)

    @overload
    def select(
        self, record: RecordID, *, into: type[M]
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self, record: str, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(self, record: RecordID) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(self, record: Table) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def select(self, record: str) -> AsyncCrudBuilder[Value]: ...
    def select(
        self,
        record: RecordIdType,
        *,
        fields: Sequence[str] | None = None,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
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
    def create(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def create(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.create(
                record, data, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.create(
            record, data, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def update(
        self, record: RecordID, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def update(
        self, record: Table, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def update(
        self, record: str, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str, data: Value = _UNSET) -> AsyncCrudBuilder[Value]: ...
    def update(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.update(
                record, data, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.update(
            record, data, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def upsert(
        self, record: RecordID, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def upsert(
        self, record: Table, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(
        self, record: str, data: Value = _UNSET, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self, record: RecordID, data: Value = _UNSET
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value = _UNSET
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str, data: Value = _UNSET) -> AsyncCrudBuilder[Value]: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.upsert(
                record, data, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.upsert(
            record, data, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def delete(
        self, record: RecordID, *, into: type[M]
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self, record: str, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(self, record: RecordID) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(self, record: Table) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> AsyncCrudBuilder[Value]: ...
    def delete(
        self, record: RecordIdType, *, into: type[M] | None = None
    ) -> AsyncCrudBuilder[Any]:
        if into is None:
            return self._connection.delete(
                record, session_id=self._session_id, txn_id=self._txn_id
            )
        return self._connection.delete(
            record, into=into, session_id=self._session_id, txn_id=self._txn_id
        )

    @overload
    def insert(
        self, table: str | Table, data: Value = _UNSET, *, relation: bool = False
    ) -> AsyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M],
        relation: bool = False,
    ) -> AsyncInsertBuilder[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> AsyncInsertBuilder[Any]:
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

    async def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        return await self._connection.run(
            name,
            args,
            version,
            session_id=self._session_id,
            txn_id=self._txn_id,
        )

    async def let(self, key: str, value: Value) -> None:
        await self._connection.let(
            key, value, session_id=self._session_id, txn_id=self._txn_id
        )

    async def unset(self, key: str) -> None:
        await self._connection.unset(
            key, session_id=self._session_id, txn_id=self._txn_id
        )

    async def commit(self) -> None:
        await self._connection.commit(self._txn_id, session_id=self._session_id)

    async def cancel(self) -> None:
        await self._connection.cancel(self._txn_id, session_id=self._session_id)

    @property
    def files(self) -> AsyncFiles:
        """Typed helpers over the ``file::*`` functions - see `surrealdb.connections.files`."""
        return AsyncFiles(self)
