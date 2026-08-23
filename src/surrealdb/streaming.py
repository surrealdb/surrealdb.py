"""Streaming query answers: the frame protocol and the views over it.

SurrealDB v3.3.0 added the ``query_stream`` RPC method to the WebSocket
protocol. Where ``query`` answers with one response holding every statement's
results, ``query_stream`` answers with a *sequence* of responses - all carrying
the originating request's id - each holding one frame of the answer:

===============  ==============================================================
``begin``        the stream is open; carries an upper bound on the statement
                 count and the protocol revision
``rows``         rows produced by one statement; more may follow
``value``        one statement's whole value, when it is not a list of rows
``finished``     one statement is final; terminal for that statement's index
``end``          the stream is complete; nothing follows
===============  ==============================================================

This module holds the parts that do not depend on a transport: the frame rules,
the state machine that turns frames into events, and the two views a caller
iterates. The transports supply a channel of decoded frames and nothing more.

Forward compatibility is part of the protocol rather than a courtesy. Within a
revision the server guarantees that a ``stream`` tag never changes meaning, and
that new tags and new fields may be added - so a client must *ignore* a tag or
a field it does not know rather than treat either as an error, which is what
makes adding one backwards compatible. A ``begin`` frame carrying no ``version``
predates the field and speaks revision 1.
"""

from __future__ import annotations

import asyncio
import queue
import time
import weakref
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterator,
)
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from surrealdb.errors import (
    NotAllowedError,
    NotFoundError,
    ServerError,
    SurrealError,
    TransportTimeoutError,
    UnexpectedResponseError,
    UnsupportedFeatureError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Value

# The key that tags a frame object, holding the frame's kind. Frames are only
# ever sent in answer to a ``query_stream`` request, and every one carries that
# request's id, so a frame is recognised by looking its id up in our own stream
# registry - never by inspecting the shape of an arbitrary response payload,
# which user data is free to imitate.
STREAM_FRAME_KEY = "stream"

# The frame-protocol revision this SDK implements. The server states its own on
# the ``begin`` frame; a higher one means a change that is not backwards
# compatible, so we refuse rather than misread it.
QUERY_STREAM_VERSION = 1

# How long to wait for the terminal frame after cancelling a stream. Short on
# purpose: once cancelled, nothing the stream still sends is wanted, and the
# only thing this delays is releasing the registration.
_CANCEL_DRAIN_TIMEOUT = 5.0

# How long a blocking stream holds the connection lock in one read before
# giving it up. A stream may legitimately wait minutes for its next frame - a
# slow statement produces none while it runs - and holding the lock for that
# would stop every other caller on the connection. Reading in slices keeps the
# connection usable throughout, at ten wakeups a second.
#
# The same value the live-query iterator slices by, and it bounds the same
# thing: the read is not the only work done under the lock - decoding the frame
# is too, because routing it requires knowing which stream it belongs to and
# that is inside the encoded body - so this is the worst case another caller
# waits, not merely the idle case.
_SYNC_PUMP_SLICE = 0.1

# Why streaming is unavailable, for the error ``require_streaming=True`` raises.
# The distinction matters to whoever reads it: one is fixed by upgrading the
# server, the other cannot be fixed without changing transport.
UNSUPPORTED_BY_SERVER = (
    "this SurrealDB server does not support streaming queries, which need "
    "v3.3.0 or later. Upgrade the server, or use query() instead"
)
UNSUPPORTED_BY_POLICY = (
    "this SurrealDB server does not allow streaming queries: its capability "
    "configuration denies the query_stream RPC method. Ask the operator to "
    "allow it, or use query() instead"
)
UNSUPPORTED_BY_HTTP = (
    "the HTTP transport cannot stream query results: its wire format carries "
    "one response per request. Connect over a websocket URL (ws:// or wss://) "
    "to stream, or use query() instead"
)
UNSUPPORTED_BY_EMBEDDED = (
    "the embedded engine does not stream query results through this SDK: it "
    "answers one response per request. Use query() instead"
)


@dataclass(frozen=True)
class StatementResult:
    """One statement's completed result, as ``statements()`` yields it.

    Attributes:
        index: The statement's zero-based position in the query.
        value: The statement's value - a list of rows, or a bare value when
            ``single`` is true.
        time: The server-reported execution time, verbatim (``"1.5ms"``).
            Text rather than a :class:`surrealdb.Duration` because the server
            renders fractional units that ``Duration`` deliberately rejects,
            and because the buffered path reports its own ``time`` the same way.
        query_type: ``"live"`` for a ``LIVE SELECT``, ``"kill"`` for a
            ``KILL``, and ``None`` for every ordinary statement.
        single: True when ``value`` is one bare value rather than a list of
            rows - ``SELECT ... FROM ONLY``, ``RETURN 1 + 2``, a block.
    """

    index: int
    value: Value
    time: str
    query_type: str | None
    single: bool


# -- Events ---------------------------------------------------------- #
#
# The state machine turns each frame into zero or more of these, so both views
# share one implementation of the protocol's rules.


@dataclass(frozen=True)
class _Row:
    """A row - or a single statement's whole value - is available now."""

    index: int
    value: Value


@dataclass(frozen=True)
class _Completed:
    """A statement finished successfully. Only raised when rows are retained."""

    result: StatementResult


@dataclass(frozen=True)
class _Failed:
    """A statement failed; every row already delivered for it is retracted."""

    index: int
    error: ServerError


@dataclass(frozen=True)
class _Ended:
    """The stream is over. ``error`` set means it did not simply finish."""

    results: int
    error: ServerError | None


_Event = _Row | _Completed | _Failed | _Ended


@dataclass(frozen=True)
class _ChannelBroken:
    """Put on a frame channel when no more frames are coming."""

    error: BaseException


def stream_broken(error: BaseException) -> object:
    """The sentinel a transport puts on a stream's queue to end it.

    Streams wait on a queue rather than on a future, so a transport whose
    socket has gone cannot reach them by failing pending calls; it puts this
    there instead, and the stream raises *error* out of the caller's iteration.
    """
    return _ChannelBroken(error)


def streaming_refused(error: BaseException) -> str | None:
    """Why the server will not serve ``query_stream``, when that is what *error* says.

    This is the whole of the streaming feature detection: no version handshake,
    just what one rejected request says. Two answers mean the same thing to a
    caller, and both are properties of the server rather than of the request, so
    both are learned once per connection:

    * **Method not found** (``-32601``) - the server predates v3.3.0.
    * **Method not allowed** (``-32602`` naming a method) - the server has ``query_stream`` and its
      capability configuration denies it. Answering that by running the query the buffered way
      honours the operator, who denied streaming rather than querying, and the caller, whose
      ``query`` is still permitted. ``require_streaming=True`` is how a caller who must stream
      hears about it instead.

    Deliberately not matched on the message text, and deliberately not on the
    reported method *name* either: a server old enough to lack the method parses
    it as unknown and reports ``name: "unknown"`` rather than what was sent.
    """
    if not isinstance(error, ServerError):
        return None
    if isinstance(error, NotAllowedError) and error.method_name is not None:
        return UNSUPPORTED_BY_POLICY
    if error.code == -32601 or (
        isinstance(error, NotFoundError) and error.method_name is not None
    ):
        return UNSUPPORTED_BY_SERVER
    return None


def _index_of(frame: dict[str, Any]) -> int:
    """Read the statement index off *frame*."""
    value = frame.get("index")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UnexpectedResponseError(
            f"a stream {frame.get(STREAM_FRAME_KEY)!r} frame carried "
            f"index={value!r}, expected a non-negative integer"
        )
    return value


def _time_of(frame: dict[str, Any]) -> str:
    """Read the ``time`` field off *frame* as text.

    Absent reads as empty rather than as the string ``"None"``, which is what
    stringifying the missing value produced - and which the buffered path,
    defaulting to ``""``, never produced for the same gap.
    """
    value = frame.get("time")
    return value if isinstance(value, str) else ""


def _error_of(frame: dict[str, Any]) -> ServerError | None:
    """Parse a frame's optional ``error`` field.

    Frames carry the full wire error object - ``code``, ``message``, ``kind``
    and optional ``details`` - which is what the RPC-level parser already
    understands, so a statement that fails mid-stream surfaces as the same
    typed error as anything else the server rejects.
    """
    raw = frame.get("error")
    if raw is None:
        return None
    return parse_rpc_error(raw)


class _Accumulator:
    """The frame protocol's rules, as a state machine over decoded frames.

    Feed it frames with :meth:`feed`, which returns the events they imply. Two
    invariants drive everything here, both from the server's own contract:

    * A statement's rows are **provisional** until its ``finished`` frame. A ``finished`` carrying
      an error retracts every row that preceded it for that statement.
    * A failure belonging to no single statement rides on ``end`` and retracts every statement that
      has not already finished. Statements that *did* finish stand - an outcome already delivered is
      never taken back - so an errored ``end`` can follow a complete set of results, naming
      something lost afterwards (a ``LIVE SELECT`` whose session ended).

    Set *retain_rows* only for the ``statements()`` view, which has to hold a
    statement's rows until it can hand over the whole value. The row view must
    not: holding every row would defeat the reason to stream at all.
    """

    def __init__(self, *, retain_rows: bool) -> None:
        self._retain_rows = retain_rows
        self._rows: dict[int, list[Value]] = {}
        self._singles: dict[int, Value] = {}
        self._finished: set[int] = set()
        self.statements: int | None = None
        self.version: int = QUERY_STREAM_VERSION
        self.ended = False

    def feed(self, payload: Any) -> list[_Event]:
        """Turn one frame into the events it implies.

        A frame carrying a ``stream`` tag this SDK does not know produces no
        events: the protocol reserves the right to add tags within a revision,
        so a client that raised on one would break the moment the server used
        it.
        """
        if not isinstance(payload, dict) or not isinstance(
            payload.get(STREAM_FRAME_KEY), str
        ):
            raise UnexpectedResponseError(
                "a streaming query answered with a payload that is not a "
                f"stream frame: {payload!r}"
            )
        frame: dict[str, Any] = payload
        tag = frame[STREAM_FRAME_KEY]
        if tag == "begin":
            return self._begin(frame)
        if tag == "rows":
            return self._rows_frame(frame)
        if tag == "value":
            return self._value_frame(frame)
        if tag == "finished":
            return self._finished_frame(frame)
        if tag == "end":
            return self._end(frame)
        return []

    def _begin(self, frame: dict[str, Any]) -> list[_Event]:
        version = frame.get("version")
        if isinstance(version, int) and not isinstance(version, bool):
            self.version = version
        if self.version > QUERY_STREAM_VERSION:
            raise UnsupportedFeatureError(
                f"the server speaks streaming-query protocol revision "
                f"{self.version} and this SDK implements revision "
                f"{QUERY_STREAM_VERSION}. A higher revision means a change "
                "that is not backwards compatible - upgrade the surrealdb "
                "package, or use query() instead of query_stream()."
            )
        statements = frame.get("statements")
        if isinstance(statements, int) and not isinstance(statements, bool):
            self.statements = statements
        return []

    def _rows_frame(self, frame: dict[str, Any]) -> list[_Event]:
        index = _index_of(frame)
        if index in self._finished:
            return []
        values = frame.get("values")
        if not isinstance(values, list):
            raise UnexpectedResponseError(
                f"a stream 'rows' frame for statement {index} carried "
                f"values={values!r}, expected a list"
            )
        rows: list[Value] = values
        if self._retain_rows:
            self._rows.setdefault(index, []).extend(rows)
        return [_Row(index, row) for row in rows]

    def _value_frame(self, frame: dict[str, Any]) -> list[_Event]:
        index = _index_of(frame)
        if index in self._finished:
            return []
        value: Value = frame.get("value")
        if self._retain_rows:
            self._singles[index] = value
        return [_Row(index, value)]

    def _finished_frame(self, frame: dict[str, Any]) -> list[_Event]:
        index = _index_of(frame)
        # `finished` is terminal for its index: the contract says no further
        # frame carries that statement. Enforcing it here rather than trusting
        # it means a statement's outcome can only ever be reported once, so a
        # repeat cannot deliver a second - and, with its rows already handed
        # over, empty - result for a statement the caller has already seen.
        if index in self._finished:
            return []
        self._finished.add(index)
        error = _error_of(frame)
        if error is not None:
            # Retraction. The rows this statement produced are void, so they
            # must not reach the statements view as a result.
            self._rows.pop(index, None)
            self._singles.pop(index, None)
            return [_Failed(index, error)]
        if not self._retain_rows:
            return []
        single = frame.get("single") is True
        if single:
            if index not in self._singles:
                raise UnexpectedResponseError(
                    f"statement {index} finished as a single value but sent no "
                    "value frame"
                )
            value: Value = self._singles.pop(index)
        elif index in self._singles:
            # The converse, and it has to be just as loud: a `value` frame
            # arrived but the terminal frame calls the statement a row list.
            # Taking `single` at its word here would hand over the empty list
            # that `self._rows` holds and throw the real value away - a wrong
            # answer, silently, which is worse than either an error or the
            # value itself.
            raise UnexpectedResponseError(
                f"statement {index} sent a value frame but finished as a list of rows"
            )
        else:
            value = self._rows.pop(index, [])
        query_type = frame.get("type")
        return [
            _Completed(
                StatementResult(
                    index=index,
                    value=value,
                    time=_time_of(frame),
                    query_type=query_type if isinstance(query_type, str) else None,
                    single=single,
                )
            )
        ]

    def _end(self, frame: dict[str, Any]) -> list[_Event]:
        self.ended = True
        error = _error_of(frame)
        raw = frame.get("results")
        counted = len(self._finished)
        results = raw if isinstance(raw, int) and not isinstance(raw, bool) else counted
        if error is None and results != counted:
            # The server states `results` as the number of statements whose
            # terminal frame it delivered, "so it agrees with what the consumer
            # counted" - which makes this the protocol's own check that no
            # statement went missing on the way. A successful `end` that
            # disagrees means the answer is short, and reporting it complete
            # would be the one failure the frame contract lets us catch.
            raise UnexpectedResponseError(
                f"a streaming query ended reporting {results} results after "
                f"delivering {counted}: the answer is incomplete"
            )
        return [_Ended(results=results, error=error)]


def buffered_statements(response: dict[str, Any]) -> list[dict[str, Any]]:
    """The per-statement results of a buffered ``query`` answer.

    What a transport hands back for :attr:`AsyncStreamOps.buffered`, so the
    fallback reads a server without streaming through the same checks the
    buffered path applies.
    """
    error = response.get("error")
    if error is not None:
        raise parse_rpc_error(error)
    result = response.get("result")
    if not isinstance(result, list):
        raise UnexpectedResponseError(
            f"query expected a list of statement results, got {type(result).__name__}"
        )
    statements: list[dict[str, Any]] = result
    return statements


def _buffered_events(
    statements: list[dict[str, Any]], *, retain_rows: bool
) -> Iterator[_Event]:
    """Replay a buffered ``query`` answer as the events a stream would emit.

    What a server without ``query_stream`` gives us, shaped so the two views
    read it exactly as they read a real stream. A statement whose value is a
    list is a row list; anything else is one bare value - the same distinction
    the ``single`` flag draws on the wire.
    """
    for index, statement in enumerate(statements):
        if statement.get("status") == "ERR":
            yield _Failed(index, parse_query_error(statement))
            return
        result: Value = statement.get("result")
        rows: list[Value] = result if isinstance(result, list) else [result]
        single = not isinstance(result, list)
        for row in rows:
            yield _Row(index, row)
        if retain_rows:
            query_type = statement.get("type")
            yield _Completed(
                StatementResult(
                    index=index,
                    value=result,
                    time=str(statement.get("time", "")),
                    query_type=query_type if isinstance(query_type, str) else None,
                    single=single,
                )
            )
    yield _Ended(results=len(statements), error=None)


# -- What the transports provide ------------------------------------- #
#
# The transports hand over bound callables rather than themselves, so a stream
# reaches only what it needs: it cannot connect, close, or touch the pending
# request map, and the transport keeps its internals private.


@dataclass(frozen=True)
class AsyncStreamOps:
    """The async transport operations a stream drives.

    Attributes:
        registry: The transport's stream registry, so a finaliser can drop an
            abandoned registration without holding the connection alive.
        open_timeout: How long to wait for the opening answer, in seconds.
        open: Register a request id, connecting if needed, and return the queue
            its frames arrive on.
        release: Deregister a request id. Safe to call twice.
        send: Send a message without waiting for a reply.
        cancel: Ask the server to stop a stream by its request id.
        buffered: Run a query the buffered way, for a server without streaming.
        supported: Whether streaming is known to work; ``None`` until an
            attempt settles it.
        set_supported: Record what an attempt discovered, so it is learned once.
    """

    registry: dict[str, asyncio.Queue[Any]]
    open_timeout: float
    open: Callable[[str], Awaitable[asyncio.Queue[Any]]]
    release: Callable[[str], None]
    send: Callable[[RequestMessage], Awaitable[None]]
    cancel: Callable[[str], Awaitable[None]]
    buffered: Callable[
        [str, dict[str, Value], UUID | None, UUID | None],
        Awaitable[list[dict[str, Any]]],
    ]
    supported: Callable[[], bool | None]
    set_supported: Callable[[bool, str | None], None]
    refusal: Callable[[], str | None]
    reason: str = UNSUPPORTED_BY_SERVER

    @classmethod
    def never_streams(
        cls,
        buffered: Callable[
            [str, dict[str, Value], UUID | None, UUID | None],
            Awaitable[list[dict[str, Any]]],
        ],
        reason: str,
    ) -> AsyncStreamOps:
        """Ops for a transport that can only ever answer the buffered way.

        The streaming members are stubs, and provably unreachable: ``supported``
        answers False, which the driver checks before it touches anything else.
        """
        return cls(
            registry={},
            open_timeout=0.0,
            open=_unreachable,
            release=_ignore,
            send=_unreachable,
            cancel=_unreachable,
            buffered=buffered,
            supported=lambda: False,
            set_supported=_ignore,
            refusal=lambda: reason,
            reason=reason,
        )


@dataclass(frozen=True)
class SyncStreamOps:
    """The blocking transport operations a stream drives.

    Mirrors :class:`AsyncStreamOps`, with one addition: frames only arrive on
    the blocking transport while somebody reads the socket, so ``pump`` is how
    the iterating thread advances its own stream.

    Attributes:
        pump: Read and route whatever the socket has, for at most the given
            number of seconds. Takes the connection lock for the read and gives
            it back before returning, so a stream waiting a long time for its
            next frame does not lock out other callers.
    """

    registry: dict[str, queue.Queue[Any]]
    open_timeout: float
    open: Callable[[str], queue.Queue[Any]]
    release: Callable[[str], None]
    send: Callable[[RequestMessage], None]
    pump: Callable[[float], None]
    cancel: Callable[[str], None]
    buffered: Callable[
        [str, dict[str, Value], UUID | None, UUID | None],
        list[dict[str, Any]],
    ]
    supported: Callable[[], bool | None]
    set_supported: Callable[[bool, str | None], None]
    refusal: Callable[[], str | None]
    reason: str = UNSUPPORTED_BY_SERVER

    @classmethod
    def never_streams(
        cls,
        buffered: Callable[
            [str, dict[str, Value], UUID | None, UUID | None],
            list[dict[str, Any]],
        ],
        reason: str,
    ) -> SyncStreamOps:
        """Ops for a transport that can only ever answer the buffered way."""
        return cls(
            registry={},
            open_timeout=0.0,
            open=_unreachable,
            release=_ignore,
            send=_unreachable,
            pump=_unreachable,
            cancel=_unreachable,
            buffered=buffered,
            supported=lambda: False,
            set_supported=_ignore,
            refusal=lambda: reason,
            reason=reason,
        )


def _unreachable(*_args: object) -> Any:
    """A streaming operation on a transport that reported it cannot stream."""
    raise AssertionError(
        "a transport that reports no streaming support was asked to stream"
    )


def _ignore(*_args: object) -> None:
    """Accept and discard: there is no registration to release or record."""


def _release_stream(registry: dict[str, Any], request_id: str) -> None:
    """Drop a stream's registration. Safe to call twice.

    A module-level function taking the registry dict rather than the
    connection, so the finaliser that calls it does not keep the connection -
    and therefore its socket and reader task - alive for as long as an
    abandoned stream object.
    """
    registry.pop(request_id, None)


class _StreamBase:
    """Bookkeeping and protocol rules shared by both stream objects."""

    def __init__(
        self,
        query: str,
        variables: dict[str, Value] | None,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
        require_streaming: bool = False,
        reason: str = UNSUPPORTED_BY_SERVER,
    ) -> None:
        self._query = query
        self._variables: dict[str, Value] = dict(variables) if variables else {}
        self._session_id = session_id
        self._txn_id = txn_id
        self._require_streaming = require_streaming
        self._reason = reason
        self._claimed = False
        self._open = False
        # Whether a stream may be executing on the server that we are
        # responsible for stopping. Set once the request is on the wire, and
        # cleared the moment we learn there is nothing to stop. Gating the
        # cancel on "we saw a frame" instead left a real leak: a request that
        # was accepted but whose opening frame never arrived - a timeout, a
        # cancelled task, a frame that would not decode - was torn down
        # without a cancel, so the query ran on holding one of the
        # connection's stream slots until the connection itself went away.
        self._cancellable = False

    def _claim(self) -> None:
        """Refuse a second pass over a stream that can only be read once.

        Both views draw from the same frames, so reading one consumes the
        other. Saying so is better than the alternative, which is a second
        iteration that silently yields nothing.
        """
        if self._claimed:
            raise SurrealError(
                "this query stream has already been consumed - a stream is "
                "read once, and row iteration and .statements() draw from the "
                "same frames. Call query_stream() again for another pass."
            )
        self._claimed = True

    def _message(self) -> RequestMessage:
        kwargs: dict[str, Any] = {"query": self._query, "params": self._variables}
        if self._session_id is not None:
            kwargs["session"] = self._session_id
        if self._txn_id is not None:
            kwargs["txn"] = self._txn_id
        return RequestMessage(RequestMethod.QUERY_STREAM, **kwargs)

    def _unsupported(self, reason: str | None = None) -> UnsupportedFeatureError:
        return UnsupportedFeatureError(
            f"{reason or self._reason}, or drop require_streaming=True to let "
            "query_stream() fall back to a buffered query."
        )

    def _decode(self, payload: Any, accumulator: _Accumulator) -> list[_Event]:
        """Interpret one item taken off the frame channel."""
        if isinstance(payload, _ChannelBroken):
            raise payload.error
        if not isinstance(payload, dict):
            raise UnexpectedResponseError(
                f"a streaming query answered with {payload!r}"
            )
        response: dict[str, Any] = payload
        error = response.get("error")
        if error is not None:
            # Before the stream opens, this is how every rejection arrives: an
            # unknown method, a duplicate request id, the concurrency cap, a
            # denied capability. Once open, the server reports failures on the
            # `end` frame instead, so either way nothing further is coming.
            raise parse_rpc_error(error)
        if "result" not in response:
            raise UnexpectedResponseError(
                f"a streaming query answered without a result: {response!r}"
            )
        return accumulator.feed(response["result"])

    def _apply(self, event: _Event) -> None:
        """Raise what an event says failed. Returns for anything deliverable."""
        if isinstance(event, _Failed):
            raise event.error
        if isinstance(event, _Ended) and event.error is not None:
            raise event.error

    def _terminal(self, payload: Any) -> bool:
        """Whether *payload* is the last thing a cancelled stream will send."""
        if isinstance(payload, _ChannelBroken):
            return True
        if not isinstance(payload, dict):
            return False
        response: dict[str, Any] = payload
        if response.get("error") is not None:
            return True
        result = response.get("result")
        return isinstance(result, dict) and result.get(STREAM_FRAME_KEY) == "end"


# Returned by a view's picker when an event is not one that view yields.
_SKIP: Any = object()


def _pick_row(event: _Event) -> Any:
    return event.value if isinstance(event, _Row) else _SKIP


def _pick_statement(event: _Event) -> Any:
    return event.result if isinstance(event, _Completed) else _SKIP


class _AsyncView:
    """One view over a driver's events - rows, or completed statements.

    A plain async iterator rather than an async generator, which is the whole
    point of it. A generator wrapping another generator meant both became
    garbage in the same collection and asyncio scheduled ``aclose()`` for each
    independently: one then found the other suspended inside its teardown and
    raised ``RuntimeError: aclose(): asynchronous generator is already
    running``, which the event loop reported as an unhandled error on the most
    ordinary usage there is - ``async for`` with a ``break`` and no
    ``async with``. With the driver as the only generator in the chain, a
    ``break`` closes exactly one thing, in order.
    """

    def __init__(
        self,
        events: AsyncGenerator[_Event, None],
        pick: Callable[[_Event], Any],
    ) -> None:
        self._events = events
        self._pick = pick

    def __aiter__(self) -> _AsyncView:
        return self

    async def __anext__(self) -> Any:
        while True:
            # `StopAsyncIteration` from the driver is this view's end too, so it
            # is deliberately left to propagate.
            picked = self._pick(await self._events.__anext__())
            if picked is not _SKIP:
                return picked

    async def aclose(self) -> None:
        await self._events.aclose()


class _SyncView:
    """The blocking counterpart of :class:`_AsyncView`."""

    def __init__(
        self,
        events: Generator[_Event, None, None],
        pick: Callable[[_Event], Any],
    ) -> None:
        self._events = events
        self._pick = pick

    def __iter__(self) -> _SyncView:
        return self

    def __next__(self) -> Any:
        while True:
            picked = self._pick(next(self._events))
            if picked is not _SKIP:
                return picked

    def close(self) -> None:
        self._events.close()


class AsyncQueryStream(_StreamBase):
    """A streaming query answer, iterated for rows or for statements.

    Returned by ``query_stream`` on the async transports. Nothing is sent until
    iteration starts, so building one costs nothing.

    Iterate it directly for **rows**, as they arrive::

        async for row in db.query_stream("SELECT * FROM person"):
            ...

    or call :meth:`statements` for one completed result per statement::

        async for statement in db.query_stream(sql).statements():
            print(statement.index, statement.value)

    A stream is read once, and the two views draw from the same frames.

    Rows are delivered before the statement that produced them has finished -
    that is the point of streaming - so a row is **provisional** until
    iteration completes without raising. A statement that fails after emitting
    rows raises, and the rows it already yielded are void. :meth:`statements`
    carries no such caveat: it yields a statement's value only once the server
    has called that statement final.

    Use ``async with``, or call :meth:`aclose`, to stop early and have the
    server abandon the query rather than run it to completion::

        async with db.query_stream(sql) as stream:
            async for row in stream:
                if enough(row):
                    break
    """

    def __init__(
        self,
        ops: AsyncStreamOps,
        query: str,
        variables: dict[str, Value] | None = None,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
        require_streaming: bool = False,
    ) -> None:
        super().__init__(
            query,
            variables,
            session_id=session_id,
            txn_id=txn_id,
            require_streaming=require_streaming,
            reason=ops.reason,
        )
        self._ops = ops
        # A strong reference, unlike the blocking stream's weak one, and the
        # difference is forced by the language: a sync generator is finalised
        # the moment its last reference goes, so a weak reference there still
        # gets the teardown run at the point of abandonment - while an async
        # generator's finalisation is handed to the event loop, so dropping the
        # only strong reference defers the cancel to a later loop turn. Holding
        # it is what lets `aclose()` and `async with` stop the query *before*
        # they return, which is what this class documents.
        self._view: _AsyncView | None = None

    def __aiter__(self) -> AsyncIterator[Value]:
        # Claimed here rather than on first iteration. Deferring it meant a
        # second view could be built and replace the first before anything
        # refused it, so `aclose()` closed the view that had never run and left
        # the one that had - holding a stream on the server - open. It also
        # reports the mistake at the call that made it.
        self._claim()
        self._view = _AsyncView(self._drive(retain_rows=False), _pick_row)
        return self._view

    def statements(self) -> AsyncIterator[StatementResult]:
        """Yield one :class:`StatementResult` per statement, as each finishes."""
        self._claim()
        self._view = _AsyncView(self._drive(retain_rows=True), _pick_statement)
        return self._view

    async def __aenter__(self) -> AsyncQueryStream:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Stop the stream, asking the server to abandon the query.

        Idempotent, and safe on a stream that was never iterated.
        """
        view = self._view
        self._view = None
        if view is not None:
            await view.aclose()

    async def _drive(self, *, retain_rows: bool) -> AsyncGenerator[_Event, None]:
        """Open the stream and walk its frames, applying the protocol's rules."""
        ops = self._ops

        if ops.supported() is False:
            if self._require_streaming:
                # The reason this server refused, remembered from the request
                # that learned it - so a later call is not told to upgrade a
                # server that has the method and denies it.
                raise self._unsupported(ops.refusal())
            for event in await self._buffered(retain_rows=retain_rows):
                self._apply(event)
                yield event
            return

        accumulator = _Accumulator(retain_rows=retain_rows)
        message = self._message()
        request_id = message.id
        frames = await ops.open(request_id)
        # The finaliser only deregisters. Telling the server to stop needs the
        # socket, which is what `aclose` is for; this is the backstop that
        # keeps a stream abandoned without closing from leaving an entry - and
        # the queue behind it - in the registry for the life of the connection.
        finalizer = weakref.finalize(self, _release_stream, ops.registry, request_id)
        try:
            await ops.send(message)
            self._cancellable = True
            while True:
                payload = await self._next_payload(frames)
                if isinstance(payload, _ChannelBroken):
                    # The connection is gone, so there is nothing to send a
                    # cancel down and nothing to drain.
                    self._cancellable = False
                try:
                    events = self._decode(payload, accumulator)
                except ServerError as exc:
                    if not self._open:
                        # Rejected before any frame: an unknown method, the
                        # concurrency cap, a denied capability, or a duplicate
                        # request id. None of them left a stream of ours
                        # running - and for the duplicate the stream that does
                        # exist belongs to the *other* request, so cancelling
                        # would stop something we did not start.
                        self._cancellable = False
                    refused = None if self._open else streaming_refused(exc)
                    if refused is not None:
                        ops.set_supported(False, refused)
                        if self._require_streaming:
                            raise self._unsupported(refused) from exc
                        for event in await self._buffered(retain_rows=retain_rows):
                            self._apply(event)
                            yield event
                        return
                    raise
                if not self._open:
                    self._open = True
                    ops.set_supported(True, None)
                for event in events:
                    self._apply(event)
                    yield event
                    if isinstance(event, _Ended):
                        return
        finally:
            finalizer.detach()
            await self._teardown(request_id, frames, ended=accumulator.ended)

    async def _next_payload(self, frames: asyncio.Queue[Any]) -> Any:
        """Take the next item off *frames*.

        Only the opening answer is given a deadline. After that a stream may
        legitimately go quiet for as long as a statement takes to produce its
        next row, and a deadline there would kill working queries; a connection
        that actually dies breaks the channel instead, which the reader does
        for every stream at once.
        """
        if self._open:
            return await frames.get()
        timeout = self._ops.open_timeout
        try:
            return await asyncio.wait_for(frames.get(), timeout)
        except asyncio.TimeoutError as exc:
            # Reported the way every other bounded wait on the transports is,
            # rather than as a bare asyncio error a caller cannot catch with
            # `except SurrealError`.
            raise TransportTimeoutError(
                "timed out waiting for a streaming query to start: no frame "
                f"within {timeout}s"
            ) from exc

    async def _buffered(self, *, retain_rows: bool) -> list[_Event]:
        statements = await self._ops.buffered(
            self._query, self._variables, self._session_id, self._txn_id
        )
        return list(_buffered_events(statements, retain_rows=retain_rows))

    async def _teardown(
        self, request_id: str, frames: asyncio.Queue[Any], *, ended: bool
    ) -> None:
        """Release the stream, cancelling it server-side if it is still open.

        A stream abandoned mid-flight is still executing on the server, with a
        transaction open and one of the connection's stream slots held, so
        stopping it is not merely tidiness. The drain afterwards is what lets
        the server's terminal frame land instead of arriving after we stopped
        listening.
        """
        try:
            if self._cancellable and not ended:
                try:
                    await self._ops.cancel(request_id)
                except SurrealError:
                    # Nothing left to stop: it finished between our last frame
                    # and this call, or was never registered. Either way no
                    # terminal frame is coming, so waiting for one would just
                    # spend the drain's whole grace period.
                    return
                await self._drain(frames)
        finally:
            self._ops.release(request_id)

    async def _drain(self, frames: asyncio.Queue[Any]) -> None:
        """Read what a cancelled stream still sends, up to its terminal frame."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _CANCEL_DRAIN_TIMEOUT
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            try:
                payload = await asyncio.wait_for(frames.get(), remaining)
            except asyncio.TimeoutError:
                # `asyncio.TimeoutError`, not the builtin: they are the same
                # class from Python 3.11 but distinct on 3.10, which this
                # package still supports, and `wait_for` raises the asyncio one
                # there. Catching only the builtin let the drain's own deadline
                # escape as an unhandled error out of a caller's `aclose()`.
                #
                # `CancelledError` is deliberately NOT caught here. Giving up
                # the drain is the right response to it, but swallowing it
                # would leave the task looking uncancelled to everything above,
                # so it propagates and the registration is released by the
                # caller's `finally` regardless.
                return
            if self._terminal(payload):
                return


class QueryStream(_StreamBase):
    """A streaming query answer on the blocking transport.

    The blocking counterpart of :class:`AsyncQueryStream`, with identical
    semantics; see that class. Iterate for rows::

        for row in db.query_stream("SELECT * FROM person"):
            ...

    or use :meth:`statements` for one completed result per statement. Use
    ``with``, or :meth:`close`, to stop early and have the server abandon the
    query.

    Frames arrive only while somebody reads the socket, so a stream is advanced
    by the thread iterating it. It takes the connection lock in short slices
    rather than holding it, so other callers on the same connection keep
    working for as long as a stream is open.
    """

    def __init__(
        self,
        ops: SyncStreamOps,
        query: str,
        variables: dict[str, Value] | None = None,
        *,
        session_id: UUID | None = None,
        txn_id: UUID | None = None,
        require_streaming: bool = False,
    ) -> None:
        super().__init__(
            query,
            variables,
            session_id=session_id,
            txn_id=txn_id,
            require_streaming=require_streaming,
            reason=ops.reason,
        )
        self._ops = ops
        # Weak on purpose - see the note on `AsyncQueryStream.__init__`. A
        # strong reference here closed a cycle (stream -> view -> generator ->
        # frame -> stream) that only the cyclic collector could break, so a
        # `for row in ...: break` with no `close()` left the query running on
        # the server, holding one of the connection's stream slots, until a
        # collection happened to come along. Weak, the generator is finalised
        # by refcount at the moment the caller lets go of it, which runs the
        # cancel there and then.
        self._view: weakref.ReferenceType[_SyncView] | None = None

    def __iter__(self) -> Iterator[Value]:
        # See :meth:`AsyncQueryStream.__aiter__` for why this claims here.
        self._claim()
        view = _SyncView(self._drive(retain_rows=False), _pick_row)
        self._view = weakref.ref(view)
        return view

    def statements(self) -> Iterator[StatementResult]:
        """Yield one :class:`StatementResult` per statement, as each finishes."""
        self._claim()
        view = _SyncView(self._drive(retain_rows=True), _pick_statement)
        self._view = weakref.ref(view)
        return view

    def __enter__(self) -> QueryStream:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Stop the stream, asking the server to abandon the query.

        Idempotent, and safe on a stream that was never iterated.
        """
        ref, self._view = self._view, None
        view = ref() if ref is not None else None
        if view is not None:
            view.close()

    def _drive(self, *, retain_rows: bool) -> Generator[_Event, None, None]:
        """Open the stream and walk its frames, applying the protocol's rules."""
        ops = self._ops

        if ops.supported() is False:
            if self._require_streaming:
                raise self._unsupported(ops.refusal())
            yield from self._replay(self._buffered(retain_rows=retain_rows))
            return

        accumulator = _Accumulator(retain_rows=retain_rows)
        message = self._message()
        request_id = message.id
        frames = ops.open(request_id)
        finalizer = weakref.finalize(self, _release_stream, ops.registry, request_id)
        try:
            ops.send(message)
            self._cancellable = True
            while True:
                payload = self._next_payload(frames)
                if isinstance(payload, _ChannelBroken):
                    self._cancellable = False
                try:
                    events = self._decode(payload, accumulator)
                except ServerError as exc:
                    if not self._open:
                        # See the async driver: nothing of ours is running.
                        self._cancellable = False
                    refused = None if self._open else streaming_refused(exc)
                    if refused is not None:
                        ops.set_supported(False, refused)
                        if self._require_streaming:
                            raise self._unsupported(refused) from exc
                        yield from self._replay(self._buffered(retain_rows=retain_rows))
                        return
                    raise
                if not self._open:
                    self._open = True
                    ops.set_supported(True, None)
                for event in events:
                    self._apply(event)
                    yield event
                    if isinstance(event, _Ended):
                        return
        finally:
            finalizer.detach()
            self._teardown(request_id, frames, ended=accumulator.ended)

    def _replay(self, events: list[_Event]) -> Generator[_Event, None, None]:
        for event in events:
            self._apply(event)
            yield event

    def _next_payload(self, frames: queue.Queue[Any]) -> Any:
        """Take the next item off *frames*, reading the socket to fill it.

        Only the opening answer is given a deadline, for the reason given on
        :meth:`AsyncQueryStream._next_payload`.
        """
        open_timeout = self._ops.open_timeout
        deadline = None if self._open else time.monotonic() + open_timeout
        while True:
            try:
                return frames.get_nowait()
            except queue.Empty:
                pass
            if deadline is None:
                self._ops.pump(_SYNC_PUMP_SLICE)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportTimeoutError(
                    "timed out waiting for a streaming query to start: no "
                    f"frame within {open_timeout}s"
                )
            self._ops.pump(min(_SYNC_PUMP_SLICE, remaining))

    def _buffered(self, *, retain_rows: bool) -> list[_Event]:
        statements = self._ops.buffered(
            self._query, self._variables, self._session_id, self._txn_id
        )
        return list(_buffered_events(statements, retain_rows=retain_rows))

    def _teardown(
        self, request_id: str, frames: queue.Queue[Any], *, ended: bool
    ) -> None:
        try:
            if self._cancellable and not ended:
                try:
                    self._ops.cancel(request_id)
                except SurrealError:
                    # See the async teardown.
                    return
                self._drain(frames)
        finally:
            self._ops.release(request_id)

    def _drain(self, frames: queue.Queue[Any]) -> None:
        """Read what a cancelled stream still sends, up to its terminal frame."""
        deadline = time.monotonic() + _CANCEL_DRAIN_TIMEOUT
        while time.monotonic() < deadline:
            try:
                payload = frames.get_nowait()
            except queue.Empty:
                try:
                    self._ops.pump(_SYNC_PUMP_SLICE)
                except SurrealError:
                    return
                continue
            if self._terminal(payload):
                return
