"""Server-independent unit tests for streaming queries (``query_stream``).

The frame protocol's rules are the part that cannot be checked against a live
server without contriving failures the server will not produce on demand -
a retraction, a torn-down stream, a protocol revision from the future, a tag
this SDK has never seen. Those are driven here through an in-memory frame
channel, and the transport-level tests use the same fake sockets as
``test_ws_live_lifecycle``.

The differential proof that streaming and buffering agree lives with the
integration tests, against a real v3.3.0 server; what is pinned here is
everything that proof cannot reach.
"""

import asyncio
import gc
import queue
import threading
import time
import uuid
from dataclasses import replace
from typing import Any
from unittest import mock

import pytest
from websockets.protocol import State

from surrealdb import streaming
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.cbor import decode, encode
from surrealdb.errors import (
    ConnectionUnavailableError,
    NotFoundError,
    SurrealError,
    ThrownError,
    TransportTimeoutError,
    UnexpectedResponseError,
    UnsupportedFeatureError,
    ValidationError,
)
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.streaming import (
    UNSUPPORTED_BY_POLICY,
    UNSUPPORTED_BY_SERVER,
    AsyncQueryStream,
    AsyncStreamOps,
    QueryStream,
    StatementResult,
    SyncStreamOps,
    buffered_statements,
    stream_broken,
    streaming_refused,
)

WS_URL = "ws://localhost:8000"
HTTP_URL = "http://localhost:8000"


# --------------------------------------------------------------------------- #
#  Frame builders - the wire shapes a v3.3.0 server actually sends             #
# --------------------------------------------------------------------------- #


def _frame(payload: dict[str, Any], request_id: str = "req") -> dict[str, Any]:
    return {"id": request_id, "result": payload}


def begin(statements: int, version: int | None = 1) -> dict[str, Any]:
    payload: dict[str, Any] = {"stream": "begin", "statements": statements}
    if version is not None:
        payload["version"] = version
    return _frame(payload)


def rows(index: int, values: list[Any]) -> dict[str, Any]:
    return _frame({"stream": "rows", "index": index, "values": values})


def value(index: int, val: Any) -> dict[str, Any]:
    return _frame({"stream": "value", "index": index, "value": val})


def finished(
    index: int,
    *,
    single: bool = False,
    error: dict[str, Any] | None = None,
    query_type: str | None = None,
    time: str = "1.5ms",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stream": "finished",
        "index": index,
        "single": single,
        "time": time,
        "type": query_type,
    }
    if error is not None:
        payload["error"] = error
    return _frame(payload)


def end(
    results: int, *, error: dict[str, Any] | None = None, time: str = "2ms"
) -> dict[str, Any]:
    payload: dict[str, Any] = {"stream": "end", "results": results, "time": time}
    if error is not None:
        payload["error"] = error
    return _frame(payload)


STOPPED = {
    "cause": None,
    "code": -32000,
    "kind": "Internal",
    "message": "The streaming query was stopped before it completed",
}


def thrown(message: str = "boom") -> dict[str, Any]:
    """A statement failure exactly as a v3.3.0 server renders it on a frame."""
    return {"cause": None, "code": -32006, "kind": "Thrown", "message": message}


# --------------------------------------------------------------------------- #
#  In-memory frame channels                                                    #
# --------------------------------------------------------------------------- #


class _AsyncChannel:
    """An async transport whose stream is a pre-filled queue of frames."""

    def __init__(
        self,
        frames: list[Any],
        *,
        buffered: list[dict[str, Any]] | None = None,
        supported: bool | None = None,
        open_timeout: float = 0.25,
        answer_cancel: bool = True,
    ) -> None:
        self.answer_cancel = answer_cancel
        self.open_timeout = open_timeout
        self.refusal: str | None = None
        self._frames = frames
        self._buffered = buffered or []
        self.supported_flag = supported
        self.registry: dict[str, asyncio.Queue[Any]] = {}
        self.sent: list[RequestMessage] = []
        self.cancelled: list[str] = []
        self.released: list[str] = []
        self.buffered_calls = 0

    def ops(self) -> AsyncStreamOps:
        return AsyncStreamOps(
            registry=self.registry,
            open_timeout=self.open_timeout,
            open=self._open,
            release=self._release,
            send=self._send,
            cancel=self._cancel,
            buffered=self._buffered_query,
            supported=lambda: self.supported_flag,
            set_supported=self._set_supported,
            refusal=lambda: self.refusal,
        )

    async def _open(self, request_id: str) -> asyncio.Queue[Any]:
        frames: asyncio.Queue[Any] = asyncio.Queue()
        for frame in self._frames:
            frames.put_nowait(frame)
        self.registry[request_id] = frames
        return frames

    def _release(self, request_id: str) -> None:
        self.released.append(request_id)
        self.registry.pop(request_id, None)

    async def _send(self, message: RequestMessage) -> None:
        self.sent.append(message)

    async def _cancel(self, request_id: str) -> None:
        # Awaits, because a real cancel is a round trip and the suspension is
        # load-bearing: the teardown being *parked* is what a second, racing
        # `aclose()` collides with. A fake that returned immediately closed that
        # window and made the abandonment tests unable to fail.
        await asyncio.sleep(0.01)
        self.cancelled.append(request_id)
        # A real server answers a cancel with a terminal frame carrying the
        # stopped error, which is what lets the drain finish promptly instead of
        # waiting out its grace period. Modelling that keeps these tests honest
        # about the ordering as well as fast - but a server that has gone quiet
        # answers nothing, which `answer_cancel=False` covers.
        frames = self.registry.get(request_id)
        if frames is not None and self.answer_cancel:
            frames.put_nowait(end(0, error=STOPPED))

    async def _buffered_query(self, *_args: Any) -> list[dict[str, Any]]:
        self.buffered_calls += 1
        return self._buffered

    def _set_supported(self, supported: bool, reason: str | None) -> None:
        self.supported_flag = supported
        self.refusal = reason


class _SyncChannel(_AsyncChannel):
    """The blocking counterpart; ``pump`` is a no-op over a pre-filled queue."""

    def ops(self) -> SyncStreamOps:  # type: ignore[override]
        return SyncStreamOps(
            registry=self.sync_registry,
            open_timeout=self.open_timeout,
            open=self._sync_open,
            release=self._release,
            send=self._sync_send,
            pump=self._pump,
            cancel=self._sync_cancel,
            buffered=self._sync_buffered,
            supported=lambda: self.supported_flag,
            set_supported=self._set_supported,
            refusal=lambda: self.refusal,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.sync_registry: dict[str, queue.Queue[Any]] = {}
        self.pumps = 0

    def _sync_open(self, request_id: str) -> queue.Queue[Any]:
        frames: queue.Queue[Any] = queue.Queue()
        for frame in self._frames:
            frames.put(frame)
        self.sync_registry[request_id] = frames
        return frames

    def _sync_send(self, message: RequestMessage) -> None:
        self.sent.append(message)

    def _sync_cancel(self, request_id: str) -> None:
        self.cancelled.append(request_id)
        frames = self.sync_registry.get(request_id)
        if frames is not None:
            frames.put(end(0, error=STOPPED))

    def _sync_buffered(self, *_args: Any) -> list[dict[str, Any]]:
        self.buffered_calls += 1
        return self._buffered

    def _pump(self, _timeout: float) -> None:
        self.pumps += 1
        if self.pumps > 50:
            raise AssertionError("the stream asked for frames that never came")

    def _release(self, request_id: str) -> None:
        self.released.append(request_id)
        self.sync_registry.pop(request_id, None)


async def collect_rows(frames: list[Any], **kwargs: Any) -> list[Any]:
    channel = _AsyncChannel(frames, **kwargs)
    return [row async for row in AsyncQueryStream(channel.ops(), "SELECT 1")]


async def collect_statements(frames: list[Any], **kwargs: Any) -> list[StatementResult]:
    channel = _AsyncChannel(frames, **kwargs)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    return [statement async for statement in stream.statements()]


# --------------------------------------------------------------------------- #
#  The two views agree with each other and with the wire                       #
# --------------------------------------------------------------------------- #


async def test_rows_view_yields_every_row_in_order() -> None:
    result = await collect_rows(
        [
            begin(1),
            rows(0, [{"n": 1}, {"n": 2}]),
            rows(0, [{"n": 3}]),
            finished(0),
            end(1),
        ]
    )
    assert result == [{"n": 1}, {"n": 2}, {"n": 3}]


async def test_statements_view_concatenates_a_statements_rows() -> None:
    statements = await collect_statements(
        [begin(1), rows(0, [1, 2]), rows(0, [3]), finished(0), end(1)]
    )
    assert [s.value for s in statements] == [[1, 2, 3]]
    assert statements[0].single is False
    assert statements[0].index == 0
    assert statements[0].time == "1.5ms"


async def test_a_single_statement_is_its_bare_value_not_a_list() -> None:
    """``single`` is what tells one bare value from a list of one row."""
    statements = await collect_statements(
        [begin(1), value(0, 42), finished(0, single=True), end(1)]
    )
    assert statements[0].value == 42
    assert statements[0].single is True

    # The row view yields that bare value as one item, so iterating rows over
    # `RETURN 42` produces 42 rather than nothing.
    assert await collect_rows(
        [begin(1), value(0, 42), finished(0, single=True), end(1)]
    ) == [42]


async def test_a_statement_with_no_payload_frames_is_an_empty_list() -> None:
    statements = await collect_statements([begin(1), finished(0), end(1)])
    assert statements[0].value == []


async def test_a_live_select_reports_its_query_type() -> None:
    live_id = str(uuid.uuid4())
    statements = await collect_statements(
        [
            begin(1),
            value(0, live_id),
            finished(0, single=True, query_type="live"),
            end(1),
        ]
    )
    assert statements[0].query_type == "live"
    assert statements[0].value == live_id


async def test_an_ordinary_statement_has_no_query_type() -> None:
    """The server sends ``type: null`` for anything that is not live or kill."""
    statements = await collect_statements(
        [begin(1), value(0, 1), finished(0, single=True), end(1)]
    )
    assert statements[0].query_type is None


# --------------------------------------------------------------------------- #
#  Rows are provisional until their statement's terminal frame                 #
# --------------------------------------------------------------------------- #


async def test_rows_arrive_before_their_statement_finishes() -> None:
    """The whole point: a row is delivered without waiting for the terminal frame."""
    channel = _AsyncChannel([begin(1), rows(0, [{"n": 1}])])
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    iterator = stream.__aiter__()

    # No `finished` and no `end` are queued, so this can only be answered by a
    # row that the accumulator was willing to hand over early.
    assert await iterator.__anext__() == {"n": 1}
    await stream.aclose()


async def test_a_failed_statement_raises_and_retracts_its_rows() -> None:
    frames = [
        begin(2),
        rows(0, [{"n": 1}]),
        finished(0, error=thrown()),
        value(1, "after"),
        finished(1, single=True),
        end(2),
    ]
    # The statements view never sees the failed statement: its rows were
    # retracted, so there is no result to hand over.
    with pytest.raises(ThrownError, match="boom"):
        await collect_statements(frames)


async def test_a_failed_statement_raises_out_of_row_iteration() -> None:
    """Rows already yielded are void, which the caller learns by the raise."""
    channel = _AsyncChannel(
        [begin(1), rows(0, [{"n": 1}]), finished(0, error=thrown("gone")), end(1)]
    )
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    seen = []
    with pytest.raises(ThrownError, match="gone"):
        async for row in stream:
            seen.append(row)
    assert seen == [{"n": 1}]


async def test_a_statement_error_keeps_its_server_error_type() -> None:
    """A frame's error is the full wire object, so it parses to the same class."""
    missing_table = {
        "cause": None,
        "code": -32000,
        "details": {"details": {"name": "nope"}, "kind": "Table"},
        "kind": "NotFound",
        "message": "The table 'nope' does not exist",
    }
    with pytest.raises(NotFoundError) as caught:
        await collect_rows([begin(1), finished(0, error=missing_table), end(1)])
    assert caught.value.table_name == "nope"


# --------------------------------------------------------------------------- #
#  A stream that was stopped rather than answered says so                      #
# --------------------------------------------------------------------------- #


async def test_an_errored_end_frame_raises() -> None:
    """A cancelled or timed-out stream reports the failure on ``end``."""
    stopped = {
        "cause": None,
        "code": -32000,
        "kind": "Internal",
        "message": "The streaming query was stopped before it completed",
    }
    with pytest.raises(SurrealError, match="stopped before it completed"):
        await collect_rows([begin(2), rows(0, [1]), end(0, error=stopped)])


async def test_an_errored_end_still_raises_after_every_statement_finished() -> None:
    """The live-query-disowned case: results stand, but the loss is reported.

    A statement that already finished cannot be retracted, so an errored ``end``
    after a complete set of results is naming something lost afterwards - a
    ``LIVE SELECT`` whose session ended, whose ids will never deliver. Treating
    that ``end`` as success would leave the caller believing in a subscription
    that is already dead.
    """
    disowned = {
        "cause": None,
        "code": -32000,
        "kind": "Internal",
        "message": "These live queries were discarded because their session ended",
    }
    channel = _AsyncChannel(
        [
            begin(1),
            value(0, "some-live-id"),
            finished(0, single=True, query_type="live"),
            end(1, error=disowned),
        ]
    )
    stream = AsyncQueryStream(channel.ops(), "LIVE SELECT * FROM t")
    seen = []
    with pytest.raises(SurrealError, match="discarded"):
        async for row in stream:
            seen.append(row)
    assert seen == ["some-live-id"]


# --------------------------------------------------------------------------- #
#  Forward compatibility: unknown tags and fields are ignored, not fatal       #
# --------------------------------------------------------------------------- #


async def test_an_unknown_frame_tag_is_ignored() -> None:
    """The protocol may add tags within a revision, so one must not be an error."""
    result = await collect_rows(
        [
            begin(1),
            _frame({"stream": "some_future_tag", "whatever": True}),
            rows(0, [1]),
            finished(0),
            end(1),
        ]
    )
    assert result == [1]


async def test_unknown_fields_on_a_known_frame_are_ignored() -> None:
    extra = _frame(
        {"stream": "rows", "index": 0, "values": [1], "future_field": "ignored"}
    )
    assert await collect_rows([begin(1), extra, finished(0), end(1)]) == [1]


async def test_a_begin_without_a_version_is_revision_one() -> None:
    """A server predating the field speaks revision 1 and must still be read."""
    assert await collect_rows(
        [begin(1, version=None), rows(0, [1]), finished(0), end(1)]
    ) == [1]


async def test_a_future_protocol_revision_is_refused() -> None:
    """A higher revision means an incompatible change, so misreading it is worse."""
    with pytest.raises(UnsupportedFeatureError, match="revision 2"):
        await collect_rows([begin(1, version=2), rows(0, [1]), finished(0), end(1)])


async def test_a_finished_frame_is_terminal_for_its_statement() -> None:
    """Nothing after it may carry that index, so a repeat is ignored.

    A second `finished` would otherwise report the same statement twice - the
    second time with an empty value, its rows having already been handed over -
    and a `rows` frame arriving afterwards would revive a statement the caller
    was already told was final.
    """
    statements = await collect_statements(
        [
            begin(1),
            rows(0, [1, 2]),
            finished(0),
            rows(0, [3]),
            finished(0),
            end(1),
        ]
    )
    assert [s.value for s in statements] == [[1, 2]]


async def test_rows_after_a_statement_finished_are_ignored() -> None:
    assert await collect_rows(
        [begin(1), rows(0, [1]), finished(0), rows(0, [2]), end(1)]
    ) == [1]


async def test_statements_are_counted_by_their_finished_frames() -> None:
    """``begin.statements`` is an upper bound - control flow can skip the tail."""
    statements = await collect_statements(
        [begin(5), value(0, 1), finished(0, single=True), end(1)]
    )
    assert len(statements) == 1


# --------------------------------------------------------------------------- #
#  Malformed frames                                                            #
# --------------------------------------------------------------------------- #


async def test_a_payload_that_is_not_a_frame_is_rejected() -> None:
    with pytest.raises(UnexpectedResponseError, match="not a stream frame"):
        await collect_rows([_frame({"unexpected": True})])


async def test_a_frame_with_a_bad_index_is_rejected() -> None:
    with pytest.raises(UnexpectedResponseError, match="index"):
        await collect_rows(
            [begin(1), _frame({"stream": "rows", "index": -1, "values": [1]})]
        )


async def test_a_rows_frame_without_a_list_is_rejected() -> None:
    with pytest.raises(UnexpectedResponseError, match="expected a list"):
        await collect_rows(
            [begin(1), _frame({"stream": "rows", "index": 0, "values": "nope"})]
        )


async def test_a_single_statement_that_sent_no_value_is_rejected() -> None:
    with pytest.raises(UnexpectedResponseError, match="sent no value frame"):
        await collect_statements([begin(1), finished(0, single=True), end(1)])


async def test_a_response_without_a_result_is_rejected() -> None:
    with pytest.raises(UnexpectedResponseError, match="without a result"):
        await collect_rows([{"id": "req"}])


async def test_a_broken_channel_raises_its_error() -> None:
    """The socket going away mid-stream is not a clean end of stream."""
    broken = stream_broken(ConnectionUnavailableError("socket went away"))
    with pytest.raises(ConnectionUnavailableError, match="socket went away"):
        await collect_rows([begin(1), rows(0, [1]), broken])


# --------------------------------------------------------------------------- #
#  A stream is read once                                                       #
# --------------------------------------------------------------------------- #


async def test_a_stream_cannot_be_iterated_twice() -> None:
    channel = _AsyncChannel([begin(1), value(0, 1), finished(0, single=True), end(1)])
    stream = AsyncQueryStream(channel.ops(), "RETURN 1")
    assert [row async for row in stream] == [1]
    with pytest.raises(SurrealError, match="already been consumed"):
        [row async for row in stream]


async def test_the_two_views_cannot_both_be_read() -> None:
    """Both draw from the same frames, so reading one consumes the other."""
    channel = _AsyncChannel([begin(1), value(0, 1), finished(0, single=True), end(1)])
    stream = AsyncQueryStream(channel.ops(), "RETURN 1")
    assert [row async for row in stream] == [1]
    with pytest.raises(SurrealError, match="already been consumed"):
        [s async for s in stream.statements()]


# --------------------------------------------------------------------------- #
#  Nothing is sent until iteration starts, and stopping cancels                 #
# --------------------------------------------------------------------------- #


async def test_building_a_stream_sends_nothing() -> None:
    channel = _AsyncChannel([begin(1), finished(0), end(1)])
    AsyncQueryStream(channel.ops(), "SELECT 1")
    assert channel.sent == []
    assert channel.registry == {}


async def test_stopping_early_cancels_and_deregisters() -> None:
    """An abandoned stream is still executing on the server, holding a slot."""
    channel = _AsyncChannel([begin(1), rows(0, [1, 2, 3])])
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    async with stream:
        async for _ in stream:
            break
    request_id = channel.sent[0].id
    assert channel.cancelled == [request_id]
    assert channel.released == [request_id]
    assert channel.registry == {}


async def test_breaking_without_closing_does_not_raise_from_the_loop() -> None:
    """The most ordinary usage there is, and it used to log an unhandled error.

    Two nested generators - a view wrapping the driver - became garbage in the
    same collection, and asyncio scheduled ``aclose()`` for each independently:
    one found the other suspended inside its teardown and raised
    ``RuntimeError: aclose(): asynchronous generator is already running``. The
    loop reported it as unhandled, so nothing a caller wrote could catch it.
    With the driver the only generator in the chain, a break closes one thing.
    """
    caught: list[str] = []
    asyncio.get_running_loop().set_exception_handler(
        lambda loop, context: caught.append(str(context.get("exception")))
    )
    try:
        channel = _AsyncChannel([begin(1), rows(0, [1, 2, 3])])
        async for _ in AsyncQueryStream(channel.ops(), "SELECT 1"):
            break
        for _ in range(3):
            gc.collect()
            await asyncio.sleep(0)
        assert caught == []
        assert channel.registry == {}
    finally:
        asyncio.get_running_loop().set_exception_handler(None)


def test_sync_breaking_without_closing_still_cancels_at_once() -> None:
    """Refcounting has to be what cleans up, not the cyclic collector.

    Holding the view strongly closed a cycle only a collection could break, so
    an abandoned stream went on executing on the server - holding one of the
    connection's slots - until one happened to come along. The collector is
    disabled here so that only refcount finalisation can pass this test.
    """
    gc.disable()
    try:
        channel = _SyncChannel([begin(1), rows(0, [1, 2, 3])])
        for _ in QueryStream(channel.ops(), "SELECT 1"):
            break
        assert channel.cancelled == [channel.sent[0].id]
        assert channel.sync_registry == {}
    finally:
        gc.enable()


async def test_a_completed_stream_is_not_cancelled() -> None:
    """There is nothing to stop once the terminal frame has arrived."""
    channel = _AsyncChannel([begin(1), value(0, 1), finished(0, single=True), end(1)])
    stream = AsyncQueryStream(channel.ops(), "RETURN 1")
    assert [row async for row in stream] == [1]
    assert channel.cancelled == []
    assert channel.released == [channel.sent[0].id]


async def test_a_cancel_that_is_never_answered_gives_up_on_its_deadline() -> None:
    """The drain must not wait forever on a server that has gone quiet.

    Every other test here has the fake answer a cancel with a terminal frame,
    which is what a live server does - so the drain's own deadline was never
    reached by anything. Patched down to keep the test quick; what is being
    pinned is that the deadline exists and releases the stream.
    """
    channel = _AsyncChannel([begin(1), rows(0, [1, 2])], answer_cancel=False)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    with mock.patch.object(streaming, "_CANCEL_DRAIN_TIMEOUT", 0.15):
        started = time.monotonic()
        async with stream:
            async for _ in stream:
                break
        elapsed = time.monotonic() - started

    assert channel.cancelled == [channel.sent[0].id]
    assert channel.registry == {}, "the stream was released despite no terminal frame"
    assert elapsed < 2.0, f"the drain took {elapsed:.2f}s, so its deadline did not fire"


async def test_a_value_frame_after_its_statement_finished_is_ignored() -> None:
    """The converse of the rows guard, and it needs its own test.

    Without it a late `value` frame would revive a statement the caller has
    already been told was final - and, because `single` is read from the
    terminal frame, hand back a value the server never attributed to it.
    """
    statements = await collect_statements(
        [
            begin(1),
            value(0, 1),
            finished(0, single=True),
            value(0, 999),
            end(1),
        ]
    )
    assert [s.value for s in statements] == [1]


async def test_the_fallback_surfaces_a_top_level_error() -> None:
    """A buffered answer can fail outright, and that must not read as no rows.

    `buffered_statements` is the only thing checking this, so without a test an
    ignored `error` would turn a failed query into a silent empty stream.
    """
    channel = _AsyncChannel([METHOD_NOT_FOUND], supported=False)
    channel._buffered = []  # unused: the raw response is what fails

    async def failing(*_args: Any) -> list[dict[str, Any]]:
        return buffered_statements(
            {"error": {"code": -32000, "kind": "Internal", "message": "kv store gone"}}
        )

    ops = replace(channel.ops(), buffered=failing)
    with pytest.raises(SurrealError, match="kv store gone"):
        [row async for row in AsyncQueryStream(ops, "SELECT 1")]


def test_buffered_statements_rejects_a_non_list_result() -> None:
    with pytest.raises(UnexpectedResponseError, match="list of statement results"):
        buffered_statements({"result": {"not": "a list"}})


async def test_aclose_is_safe_on_a_stream_that_was_never_iterated() -> None:
    channel = _AsyncChannel([])
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    await stream.aclose()
    await stream.aclose()
    assert channel.sent == []


async def test_a_timeout_before_the_first_frame_still_cancels() -> None:
    """A request that was accepted must be stopped even if no frame arrived.

    Gating the cancel on having seen a frame leaked the stream: the server had
    accepted the request and was executing it, holding one of the connection's
    slots, and nothing ever told it to stop.
    """
    channel = _AsyncChannel([])  # nothing will ever arrive
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    with pytest.raises(TransportTimeoutError):
        [row async for row in stream]
    assert channel.cancelled == [channel.sent[0].id]
    assert channel.registry == {}


async def test_a_rejected_request_is_not_cancelled() -> None:
    """Nothing of ours is running, so there is nothing to stop.

    This matters most for a duplicate request id: the stream that does exist
    belongs to the other request, and cancelling would stop something this call
    never started.
    """
    duplicate = {
        "id": "req",
        "error": {
            "code": -32603,
            "details": {"kind": "InvalidParams"},
            "kind": "Validation",
            "message": "A streaming query with this request id is already in progress",
        },
    }
    channel = _AsyncChannel([duplicate])
    with pytest.raises(SurrealError, match="already in progress"):
        [row async for row in AsyncQueryStream(channel.ops(), "SELECT 1")]
    assert channel.cancelled == []
    assert channel.registry == {}


async def test_a_broken_connection_is_not_cancelled() -> None:
    """There is nothing left to send a cancel down."""
    broken = stream_broken(ConnectionUnavailableError("gone"))
    channel = _AsyncChannel([begin(1), rows(0, [1]), broken])
    with pytest.raises(ConnectionUnavailableError):
        [row async for row in AsyncQueryStream(channel.ops(), "SELECT 1")]
    assert channel.cancelled == []
    assert channel.registry == {}


async def test_an_end_that_undercounts_its_results_is_rejected() -> None:
    """The protocol's own integrity check, which was being parsed and ignored.

    ``results`` is the number of statements whose terminal frame the server
    delivered, so a successful ``end`` that disagrees with what arrived means
    the answer is short - and reporting it complete is the one failure the frame
    contract lets a client catch.
    """
    with pytest.raises(UnexpectedResponseError, match="answer is incomplete"):
        await collect_statements([begin(2), rows(0, [1]), end(2)])


async def test_an_errored_end_is_not_held_to_the_count() -> None:
    """Statements without a terminal frame are retracted, so the count differs."""
    stopped = {"code": -32000, "kind": "Internal", "message": "stopped"}
    with pytest.raises(SurrealError, match="stopped"):
        await collect_rows([begin(2), rows(0, [1]), end(0, error=stopped)])


async def test_a_value_frame_contradicting_single_is_rejected() -> None:
    """Trusting ``single`` here would hand over an empty list and drop the value."""
    with pytest.raises(UnexpectedResponseError, match="finished as a list of rows"):
        await collect_statements(
            [begin(1), value(0, 42), finished(0, single=False), end(1)]
        )


async def test_a_missing_time_reads_as_empty_not_as_the_word_none() -> None:
    statements = await collect_statements(
        [
            begin(1),
            value(0, 1),
            _frame({"stream": "finished", "index": 0, "single": True}),
            end(1),
        ]
    )
    assert statements[0].time == ""


# --------------------------------------------------------------------------- #
#  Falling back to a buffered query                                            #
# --------------------------------------------------------------------------- #

METHOD_NOT_FOUND = {
    "id": "req",
    "error": {
        "cause": None,
        "code": -32601,
        "details": {"details": {"name": "unknown"}, "kind": "Method"},
        "kind": "NotFound",
        "message": "Method not found",
    },
}

DENIED = {
    "id": "req",
    "error": {
        "cause": None,
        "code": -32602,
        "details": {"details": {"name": "query_stream"}, "kind": "Method"},
        "kind": "NotAllowed",
        "message": "Method not allowed",
    },
}

BUFFERED: list[dict[str, Any]] = [
    {"status": "OK", "time": "1ms", "type": None, "result": [{"n": 1}, {"n": 2}]},
    {"status": "OK", "time": "2ms", "type": None, "result": 42},
]


def test_method_not_found_is_recognised_without_reading_the_message() -> None:
    """The predicate keys on the code and the detail kind, never on wording.

    A server old enough to lack the method reports ``name: "unknown"`` rather
    than the name that was sent, so matching the name would never fire.
    """
    from surrealdb.errors import parse_rpc_error

    error = parse_rpc_error(METHOD_NOT_FOUND["error"])
    assert streaming_refused(error) == UNSUPPORTED_BY_SERVER
    assert isinstance(error, NotFoundError)
    assert error.method_name == "unknown"


def test_a_denied_capability_counts_as_streaming_being_unavailable() -> None:
    """`--deny-rpc query_stream` answers -32602 naming the method.

    The operator denied streaming, not querying, so running the query the
    buffered way honours them and the caller both - and it is reported with its
    own reason, because "upgrade to v3.3.0" would be wrong advice here.
    """
    from surrealdb.errors import parse_rpc_error

    error = parse_rpc_error(DENIED["error"])
    assert streaming_refused(error) == UNSUPPORTED_BY_POLICY


def test_a_missing_table_is_not_mistaken_for_a_missing_method() -> None:
    from surrealdb.errors import parse_rpc_error

    error = parse_rpc_error(
        {
            "code": -32000,
            "kind": "NotFound",
            "details": {"kind": "Table", "details": {"name": "t"}},
            "message": "no table",
        }
    )
    assert streaming_refused(error) is None


def test_a_denied_scripting_capability_is_not_a_streaming_refusal() -> None:
    """-32602 alone is not enough; the denial has to name a method."""
    from surrealdb.errors import parse_rpc_error

    error = parse_rpc_error(
        {
            "code": -32602,
            "kind": "NotAllowed",
            "details": {"kind": "Scripting"},
            "message": "Scripting is not allowed",
        }
    )
    assert streaming_refused(error) is None


async def test_a_denied_capability_falls_back_and_says_why() -> None:
    channel = _AsyncChannel([DENIED], buffered=BUFFERED)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    assert [row async for row in stream] == [{"n": 1}, {"n": 2}, 42]
    assert channel.supported_flag is False

    channel = _AsyncChannel([DENIED], buffered=BUFFERED)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1", require_streaming=True)
    with pytest.raises(UnsupportedFeatureError, match="capability configuration"):
        [row async for row in stream]


async def test_an_unknown_method_falls_back_to_a_buffered_query() -> None:
    channel = _AsyncChannel([METHOD_NOT_FOUND], buffered=BUFFERED)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    assert [row async for row in stream] == [{"n": 1}, {"n": 2}, 42]
    assert channel.buffered_calls == 1
    # The answer is learned once, so a second stream does not pay for a probe.
    assert channel.supported_flag is False


async def test_the_fallback_replays_statements_with_the_right_single_flag() -> None:
    """A buffered list is a row list; anything else is one bare value."""
    channel = _AsyncChannel([METHOD_NOT_FOUND], buffered=BUFFERED)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    statements = [s async for s in stream.statements()]
    assert [(s.index, s.single, s.value) for s in statements] == [
        (0, False, [{"n": 1}, {"n": 2}]),
        (1, True, 42),
    ]


async def test_a_learned_refusal_keeps_its_reason_for_later_calls() -> None:
    """Otherwise the second call advises upgrading a server that has the method.

    The refusal is learned once per connection, so the reason has to be
    remembered with it - a denied capability is not fixed by an upgrade.
    """
    channel = _AsyncChannel([DENIED], buffered=BUFFERED)
    assert [row async for row in AsyncQueryStream(channel.ops(), "SELECT 1")] == [
        {"n": 1},
        {"n": 2},
        42,
    ]
    assert channel.refusal == UNSUPPORTED_BY_POLICY

    # A second stream on the same connection never reaches the wire, and must
    # still report why.
    later = AsyncQueryStream(channel.ops(), "SELECT 1", require_streaming=True)
    with pytest.raises(UnsupportedFeatureError, match="capability configuration"):
        [row async for row in later]


async def test_a_learned_unsupported_server_skips_the_probe_entirely() -> None:
    channel = _AsyncChannel([], buffered=BUFFERED, supported=False)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    assert [row async for row in stream] == [{"n": 1}, {"n": 2}, 42]
    assert channel.sent == []
    assert channel.registry == {}


async def test_require_streaming_refuses_the_fallback() -> None:
    channel = _AsyncChannel([METHOD_NOT_FOUND], buffered=BUFFERED)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1", require_streaming=True)
    with pytest.raises(UnsupportedFeatureError, match=r"v3\.3\.0 or later"):
        [row async for row in stream]
    assert channel.buffered_calls == 0


async def test_a_failed_statement_in_the_fallback_still_raises() -> None:
    failing: list[dict[str, Any]] = [
        {"status": "OK", "time": "1ms", "result": [1]},
        {"status": "ERR", "time": "1ms", "result": "An error occurred: boom"},
    ]
    channel = _AsyncChannel([METHOD_NOT_FOUND], buffered=failing)
    stream = AsyncQueryStream(channel.ops(), "SELECT 1")
    seen = []
    with pytest.raises(SurrealError, match="boom"):
        async for row in stream:
            seen.append(row)
    assert seen == [1]


async def test_an_error_that_is_not_method_not_found_is_not_swallowed() -> None:
    """The concurrency cap, a denied capability, a duplicate id: all real errors."""
    too_many = {
        "id": "req",
        "error": {
            "code": -32603,
            "details": {"kind": "InvalidParams"},
            "kind": "Validation",
            "message": "Too many concurrent streaming queries",
        },
    }
    channel = _AsyncChannel([too_many], buffered=BUFFERED)
    with pytest.raises(SurrealError, match="Too many concurrent"):
        [row async for row in AsyncQueryStream(channel.ops(), "SELECT 1")]
    assert channel.buffered_calls == 0


# --------------------------------------------------------------------------- #
#  The blocking views behave identically                                       #
# --------------------------------------------------------------------------- #


def test_sync_rows_and_statements_agree_with_the_async_views() -> None:
    frames = [begin(2), rows(0, [1, 2]), finished(0), value(1, 9)]
    frames += [finished(1, single=True), end(2)]

    channel = _SyncChannel(frames)
    assert list(QueryStream(channel.ops(), "SELECT 1")) == [1, 2, 9]

    channel = _SyncChannel(frames)
    statements = list(QueryStream(channel.ops(), "SELECT 1").statements())
    assert [(s.single, s.value) for s in statements] == [(False, [1, 2]), (True, 9)]


def test_sync_stopping_early_cancels_and_deregisters() -> None:
    channel = _SyncChannel([begin(1), rows(0, [1, 2, 3])])
    stream = QueryStream(channel.ops(), "SELECT 1")
    with stream:
        for _ in stream:
            break
    request_id = channel.sent[0].id
    assert channel.cancelled == [request_id]
    assert channel.sync_registry == {}


def test_sync_falls_back_to_a_buffered_query() -> None:
    channel = _SyncChannel([METHOD_NOT_FOUND], buffered=BUFFERED)
    assert list(QueryStream(channel.ops(), "SELECT 1")) == [{"n": 1}, {"n": 2}, 42]
    assert channel.supported_flag is False


def test_sync_require_streaming_refuses_the_fallback() -> None:
    channel = _SyncChannel([METHOD_NOT_FOUND], buffered=BUFFERED)
    stream = QueryStream(channel.ops(), "SELECT 1", require_streaming=True)
    with pytest.raises(UnsupportedFeatureError):
        list(stream)


def test_sync_a_failed_statement_raises() -> None:
    channel = _SyncChannel(
        [begin(1), rows(0, [1]), finished(0, error=thrown()), end(1)]
    )
    with pytest.raises(ThrownError, match="boom"):
        list(QueryStream(channel.ops(), "SELECT 1"))


# --------------------------------------------------------------------------- #
#  Request encoding                                                            #
# --------------------------------------------------------------------------- #


def test_query_stream_encodes_the_same_params_as_query() -> None:
    stream = decode(
        RequestMessage(
            RequestMethod.QUERY_STREAM, query="RETURN $x", params={"x": 1}
        ).WS_CBOR_DESCRIPTOR
    )
    buffered = decode(
        RequestMessage(
            RequestMethod.QUERY, query="RETURN $x", params={"x": 1}
        ).WS_CBOR_DESCRIPTOR
    )
    assert stream["method"] == "query_stream"
    assert stream["params"] == buffered["params"]


def test_query_stream_forwards_session_and_txn() -> None:
    session, txn = uuid.uuid4(), uuid.uuid4()
    encoded = decode(
        RequestMessage(
            RequestMethod.QUERY_STREAM,
            query="RETURN 1",
            params={},
            session=session,
            txn=txn,
        ).WS_CBOR_DESCRIPTOR
    )
    assert encoded["session"] == str(session)
    assert encoded["txn"] == str(txn)


def test_query_cancel_names_the_stream_and_forwards_session_only() -> None:
    """``txn`` is withheld deliberately - see ``prep_query_cancel``."""
    session = uuid.uuid4()
    encoded = decode(
        RequestMessage(
            RequestMethod.QUERY_CANCEL,
            stream="req-1",
            session=session,
            txn=uuid.uuid4(),
        ).WS_CBOR_DESCRIPTOR
    )
    assert encoded["method"] == "query_cancel"
    assert encoded["params"] == ["req-1"]
    assert encoded["session"] == str(session)
    assert "txn" not in encoded


def test_query_cancel_refuses_to_encode_without_a_stream_id() -> None:
    """A missing or misnamed keyword would cancel nothing and report success.

    The validator only checks that ``params`` holds one item, so ``[None]``
    passes it and the server answers that no such stream is in progress - which
    reads as "already finished" rather than "you asked for the wrong thing".
    """
    with pytest.raises(ValueError, match="query_cancel requires stream"):
        _ = RequestMessage(RequestMethod.QUERY_CANCEL).WS_CBOR_DESCRIPTOR
    with pytest.raises(ValueError, match="query_cancel requires stream"):
        _ = RequestMessage(
            RequestMethod.QUERY_CANCEL, request_id="typo"
        ).WS_CBOR_DESCRIPTOR


# --------------------------------------------------------------------------- #
#  Transport routing                                                           #
# --------------------------------------------------------------------------- #


def _register_async_stream(
    conn: AsyncWsSurrealConnection, request_id: str
) -> "asyncio.Queue[Any]":
    """Register a stream on *conn* without connecting.

    Deliberately not `_stream_open`, which calls `connect()` and opens a real
    socket. These tests assert routing against a fake one, and calling the real
    thing made them pass only because a server happened to be listening on the
    default port - in CI, where the file's own docstring promises they need no
    server, they failed with `Connection refused`.
    """
    frames: asyncio.Queue[Any] = asyncio.Queue()
    conn._streams[request_id] = frames
    return frames


def _register_sync_stream(
    conn: BlockingWsSurrealConnection, request_id: str
) -> "queue.Queue[Any]":
    """The blocking counterpart of :func:`_register_async_stream`."""
    frames: queue.Queue[Any] = queue.Queue()
    conn._streams[request_id] = frames
    return frames


class _RecordingAsyncSocket:
    """Accepts sends and records them; delivers nothing on its own."""

    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, data: Any) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        pass


async def test_async_routing_sends_frames_to_the_stream_not_the_query_map() -> None:
    """A future resolves once; a stream's id must stay registered for N frames."""
    conn = AsyncWsSurrealConnection(WS_URL)
    conn.loop = asyncio.get_running_loop()
    conn.socket = _RecordingAsyncSocket()

    frames = _register_async_stream(conn, "stream-1")
    conn.qry["stream-1"] = conn.loop.create_future()

    for payload in (begin(1), rows(0, [1]), finished(0), end(1)):
        conn._route_frame(encode({**payload, "id": "stream-1"}))

    assert frames.qsize() == 4
    assert not conn.qry["stream-1"].done()
    conn._stream_release("stream-1")


async def test_async_a_buffered_reply_still_reaches_its_caller_mid_stream() -> None:
    conn = AsyncWsSurrealConnection(WS_URL)
    conn.loop = asyncio.get_running_loop()
    conn.socket = _RecordingAsyncSocket()

    frames = _register_async_stream(conn, "stream-1")
    reply: asyncio.Future[dict[str, Any]] = conn.loop.create_future()
    conn.qry["query-1"] = reply

    conn._route_frame(encode({**rows(0, [1]), "id": "stream-1"}))
    conn._route_frame(encode({"id": "query-1", "result": [{"status": "OK"}]}))

    assert frames.qsize() == 1
    assert reply.result()["id"] == "query-1"
    conn._stream_release("stream-1")


async def test_async_closing_the_connection_breaks_an_open_stream() -> None:
    """`_connect_locked` closes on a dead reader, so this is not caller-only."""
    conn = AsyncWsSurrealConnection(WS_URL)
    conn.loop = asyncio.get_running_loop()
    conn.socket = _RecordingAsyncSocket()

    frames = _register_async_stream(conn, "stream-1")
    await conn.close()

    payload = frames.get_nowait()
    assert isinstance(payload.error, ConnectionUnavailableError)
    assert "streaming query was open" in str(payload.error)


async def test_async_an_idless_error_reaches_a_lone_stream() -> None:
    """A rejected frame arrives with no id, and a stream has to be told.

    The server answers a frame it could not parse far enough to correlate with
    no ``id`` at all. That was only ever attributed among `self.qry`, so a
    connection whose sole request was a stream held the error for a pending
    call that did not exist - and the stream blamed its opening deadline for
    what was a parse error, thirty seconds later.
    """
    conn = AsyncWsSurrealConnection(WS_URL)
    conn.loop = asyncio.get_running_loop()
    conn.socket = _RecordingAsyncSocket()
    frames = _register_async_stream(conn, "stream-1")

    conn._route_frame(
        encode(
            {
                "error": {
                    "code": -32700,
                    "kind": "Validation",
                    "details": {"kind": "Parse"},
                    "message": "Parse error: unexpected token",
                }
            }
        )
    )

    payload = frames.get_nowait()
    assert isinstance(payload.error, ValidationError)
    assert payload.error.is_parse_error
    conn._stream_release("stream-1")


async def test_async_a_dead_reader_breaks_every_open_stream() -> None:
    conn = AsyncWsSurrealConnection(WS_URL)
    conn.loop = asyncio.get_running_loop()
    conn.socket = _RecordingAsyncSocket()

    first = _register_async_stream(conn, "stream-1")
    second = _register_async_stream(conn, "stream-2")
    conn._reader_stopped()

    for frames in (first, second):
        payload = frames.get_nowait()
        assert isinstance(payload.error, ConnectionUnavailableError)


def _reply(request_id: str) -> bytes:
    return encode({"id": request_id, "result": [{"status": "OK", "result": []}]})


class _FakeSyncSocket:
    def __init__(self, frames: list[bytes]) -> None:
        self._frames = list(frames)
        self.sent: list[Any] = []
        # `connect()` reads this to decide whether the socket behind the
        # attribute is still usable.
        self.state = State.OPEN

    def send(self, data: Any) -> None:
        self.sent.append(data)

    def recv(self, timeout: float | None = None, decode: bool | None = None) -> bytes:
        if not self._frames:
            raise TimeoutError
        return self._frames.pop(0)

    def close(self) -> None:
        pass


def test_blocking_send_routes_a_streams_frames_instead_of_failing() -> None:
    """This used to raise ``Response ID mismatch`` and break both callers."""
    conn = BlockingWsSurrealConnection(WS_URL)
    message = RequestMessage(RequestMethod.QUERY, query="SELECT 1", params={})
    frames = _register_sync_stream(conn, "stream-1")
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [encode({**rows(0, [1]), "id": "stream-1"}), _reply(message.id)]
    )

    response = conn._send(message, "query", bypass=True)

    assert response["id"] == message.id
    assert frames.qsize() == 1
    conn._stream_release("stream-1")


def test_blocking_a_live_iterator_routes_a_streams_frames() -> None:
    """The live loop dropped every response carrying an id, frames included."""
    conn = BlockingWsSurrealConnection(WS_URL)
    live_id = str(uuid.uuid4())
    frames = _register_sync_stream(conn, "stream-1")
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [
            encode({**rows(0, [1]), "id": "stream-1"}),
            encode({"result": {"id": live_id, "action": "CREATE", "result": {"n": 1}}}),
        ]
    )

    generator = conn.subscribe_live(live_id)
    try:
        assert next(generator)["action"] == "CREATE"
    finally:
        generator.close()

    assert frames.qsize() == 1
    conn._stream_release("stream-1")


def test_blocking_the_pump_routes_while_holding_the_lock() -> None:
    """Frame order depends on this, and only the lock enforces it.

    Decoding and routing after releasing the lock let a second reader on the
    connection deliver a *later* frame first - a `finished` ahead of the rows it
    terminates, which the accumulator then reports as an empty statement, with
    no error. Every other reader routes from inside its lock hold; this pins
    that the pump does too.
    """
    conn = BlockingWsSurrealConnection(WS_URL)
    frames = _register_sync_stream(conn, "stream-1")
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [encode({**rows(0, [1]), "id": "stream-1"})]
    )

    locked_while_routing: list[bool] = []
    original = conn._route_foreign

    def spy(response: dict[str, Any]) -> None:
        locked_while_routing.append(conn._lock.locked())
        original(response)

    conn._route_foreign = spy  # type: ignore[method-assign]
    conn._stream_pump(0.1)

    assert locked_while_routing == [True]
    assert frames.qsize() == 1
    conn._stream_release("stream-1")


class _SignallingSocket:
    """A socket with nothing to deliver, which blocks for its whole timeout.

    The blocking is the point: a fake that returned immediately released the
    lock immediately too, whatever the code under test intended, so the test it
    served could not fail. A real socket with no data waits out the timeout it
    was given, and that is what decides whether the lock is held meanwhile.
    """

    def __init__(self, entered: threading.Event) -> None:
        self._entered = entered
        self.state = State.OPEN

    def send(self, data: Any) -> None:
        pass

    def recv(self, timeout: float | None = None, decode: bool | None = None) -> bytes:
        self._entered.set()
        time.sleep(timeout if timeout is not None else 0)
        raise TimeoutError

    def close(self) -> None:
        pass


def test_blocking_the_pump_does_not_hold_the_lock_while_waiting() -> None:
    """Waiting for a frame must happen with the connection lock released.

    Held for the whole slice, the lock was free for microseconds out of every
    hundred milliseconds, and another thread wanting to run a query could be
    starved for as long as the stream stayed quiet - which is what a stream does
    while a slow statement runs. CI measured 2.4s.

    Deterministic on purpose. The wall-clock version of this only failed on a
    slow machine: on a fast one the starved query still got through in ~50ms,
    so it passed while the defect was present. Here the fake socket controls the
    timing, so the assertion turns on the lock discipline rather than on how
    many cores the runner has.
    """
    conn = BlockingWsSurrealConnection(WS_URL)
    entered = threading.Event()
    conn.socket = _SignallingSocket(entered)  # type: ignore[assignment]

    acquired: list[bool] = []

    def waiter() -> None:
        # The pump is inside `recv`, so it holds the lock if it is going to.
        entered.wait(5)
        got = conn._lock.acquire(timeout=0.5)
        acquired.append(got)
        if got:
            conn._lock.release()

    thread = threading.Thread(target=waiter)
    thread.start()
    try:
        # A slice far longer than the waiter's patience: the pump must spend
        # almost all of it asleep with the lock released.
        conn._stream_pump(1.5)
    finally:
        thread.join(timeout=10)

    assert acquired == [True], (
        "another thread could not take the connection lock while the pump was "
        "waiting for a frame"
    )


def test_blocking_the_live_iterator_routes_while_holding_the_lock() -> None:
    """The live loop reads the same socket, so it owes streams the same order."""
    conn = BlockingWsSurrealConnection(WS_URL)
    live_id = str(uuid.uuid4())
    _register_sync_stream(conn, "stream-1")
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [
            encode({**rows(0, [1]), "id": "stream-1"}),
            encode({"result": {"id": live_id, "action": "CREATE", "result": {"n": 1}}}),
        ]
    )

    locked_while_routing: list[bool] = []
    original = conn._route_foreign

    def spy(response: dict[str, Any]) -> None:
        locked_while_routing.append(conn._lock.locked())
        original(response)

    conn._route_foreign = spy  # type: ignore[method-assign]
    generator = conn.subscribe_live(live_id)
    try:
        assert next(generator)["action"] == "CREATE"
    finally:
        generator.close()

    assert locked_while_routing == [True]
    conn._stream_release("stream-1")


def test_blocking_an_unknown_id_is_dropped_rather_than_raised_on() -> None:
    """A released stream leaves frames in flight that belong to nobody."""
    conn = BlockingWsSurrealConnection(WS_URL)
    message = RequestMessage(RequestMethod.QUERY, query="SELECT 1", params={})
    conn.socket = _FakeSyncSocket(  # type: ignore[assignment]
        [encode({**rows(0, [1]), "id": "long-gone"}), _reply(message.id)]
    )

    response = conn._send(message, "query", bypass=True)

    assert response["id"] == message.id


def test_blocking_closing_the_connection_breaks_an_open_stream() -> None:
    conn = BlockingWsSurrealConnection(WS_URL)
    conn.socket = _FakeSyncSocket([])  # type: ignore[assignment]
    frames = _register_sync_stream(conn, "stream-1")

    conn.close()

    payload = frames.get_nowait()
    assert isinstance(payload.error, ConnectionUnavailableError)


# --------------------------------------------------------------------------- #
#  Transports that cannot stream at all                                        #
# --------------------------------------------------------------------------- #


def test_http_streams_by_buffering_and_says_so_when_asked() -> None:
    """Parity, so calling code can change transport without changing shape."""
    conn = BlockingHttpSurrealConnection(HTTP_URL)
    captured: list[str] = []

    def fake_query_raw(query: str, vars: Any = None) -> dict[str, Any]:
        captured.append(query)
        return {"result": BUFFERED}

    conn.query_raw = fake_query_raw  # type: ignore[method-assign]

    assert list(conn.query_stream("SELECT 1")) == [{"n": 1}, {"n": 2}, 42]
    assert captured == ["SELECT 1"]

    with pytest.raises(UnsupportedFeatureError, match="HTTP transport cannot stream"):
        list(conn.query_stream("SELECT 1", require_streaming=True))
