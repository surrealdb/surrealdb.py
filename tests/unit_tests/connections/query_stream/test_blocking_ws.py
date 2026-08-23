"""Streaming queries over the blocking websocket, against a real server.

Frames only arrive on this transport while somebody reads the socket, so what
these add over the async suite is that the reading is done by the iterating
thread without shutting anyone else out: a stream and an ordinary query on the
same connection, from two threads, both make progress.
"""

import threading
import time
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import SurrealError, UnsupportedFeatureError

MIXED_SQL = (
    "SELECT * FROM stream_wide ORDER BY id LIMIT 3; "
    "RETURN 42; "
    "SELECT * FROM ONLY stream_wide ORDER BY id LIMIT 1; "
    "RETURN [1, 2, 3];"
)


def _seed(connection: BlockingWsSurrealConnection, count: int = 120) -> None:
    connection.query(
        "DEFINE TABLE IF NOT EXISTS stream_wide; DELETE stream_wide; "
        f"CREATE |stream_wide:{count}| SET n = 1 RETURN NONE"
    ).execute()


def _require_streaming(connection: BlockingWsSurrealConnection) -> None:
    """Skip unless this server really streams - see the async suite's note."""
    try:
        for _ in connection.query_stream("RETURN 1", require_streaming=True):
            pass
    except UnsupportedFeatureError as exc:
        if connection._streaming_supported is not False:
            raise
        pytest.skip(f"this server will not stream: {exc}")


def test_streamed_statements_match_the_buffered_answer(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    _require_streaming(blocking_ws_connection)
    _seed(blocking_ws_connection)

    buffered = blocking_ws_connection.query(MIXED_SQL).execute()
    streamed = list(blocking_ws_connection.query_stream(MIXED_SQL).statements())

    assert [statement.value for statement in streamed] == buffered
    assert [statement.single for statement in streamed] == [False, True, True, False]


def test_rows_arrive_before_the_query_finishes(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    _require_streaming(blocking_ws_connection)
    _seed(blocking_ws_connection)

    stream = blocking_ws_connection.query_stream("SELECT * FROM stream_wide; SLEEP 2s;")
    started = time.monotonic()
    iterator = iter(stream)
    first_row = next(iterator)
    first_row_at = time.monotonic() - started

    assert first_row is not None
    assert first_row_at < 1.0, (
        f"the first row took {first_row_at:.2f}s, which is long enough that the "
        "query may have been buffered rather than streamed"
    )
    stream.close()


def test_stopping_early_cancels_the_query_server_side(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    _require_streaming(blocking_ws_connection)
    _seed(blocking_ws_connection)

    started = time.monotonic()
    seen = 0
    with blocking_ws_connection.query_stream(
        "SELECT * FROM stream_wide; SLEEP 10s;"
    ) as stream:
        for _ in stream:
            seen += 1
            if seen == 3:
                break
    elapsed = time.monotonic() - started

    assert seen == 3
    # See the async twin: clear of `_CANCEL_DRAIN_TIMEOUT`, which is what a
    # cancel that never reaches the server costs.
    assert elapsed < 2.5, f"stopping the stream took {elapsed:.1f}s"
    assert blocking_ws_connection._streams == {}
    assert blocking_ws_connection.query("RETURN 'alive'").execute() == ["alive"]


def test_another_thread_keeps_working_while_a_stream_is_open(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The stream reads the socket in slices rather than holding the lock.

    The stream is drained on its own thread, so it is *actively pumping* for the
    whole of the trailing sleep - which is the only arrangement that can detect
    lock hogging. An earlier version of this test called ``iter(stream)`` on the
    main thread and then waited: nothing is sent until the first ``next()``, so
    no stream was running while the other thread queried and the assertion below
    could not fail.
    """
    _require_streaming(blocking_ws_connection)
    _seed(blocking_ws_connection)

    streamed: dict[str, Any] = {}

    def consume() -> None:
        started = time.monotonic()
        with blocking_ws_connection.query_stream(
            "SELECT * FROM stream_wide; SLEEP 3s;"
        ) as stream:
            streamed["rows"] = sum(1 for _ in stream)
        streamed["elapsed"] = time.monotonic() - started

    consumer = threading.Thread(target=consume)
    consumer.start()
    try:
        # Long enough that the stream is past its rows and into the sleep,
        # pumping the socket in slices while it waits.
        time.sleep(0.5)
        started = time.monotonic()
        answer = blocking_ws_connection.query(
            "RETURN 'from the other thread'"
        ).execute()
        elapsed = time.monotonic() - started
    finally:
        consumer.join(timeout=30)

    assert not consumer.is_alive()
    assert answer == ["from the other thread"]
    # The stream really was mid-flight: it took the sleep's full three seconds.
    assert streamed["elapsed"] >= 3.0, streamed
    assert streamed["rows"] > 1
    # Relative to the stream's own duration, not an absolute wall clock. An
    # absolute bound made this a machine-speed test: the starved query still got
    # through in ~50ms on a fast laptop and 2.4s on CI's two cores, so the same
    # defect passed locally and failed there. The deterministic proof of the
    # lock discipline is
    # `test_blocking_the_pump_does_not_hold_the_lock_while_waiting`; this is the
    # end-to-end smoke test that the two threads really do share a connection.
    assert elapsed < streamed["elapsed"] / 3, (
        f"the query waited {elapsed:.2f}s of the stream's "
        f"{streamed['elapsed']:.1f}s, so it was contending with the stream for "
        "the connection lock rather than interleaving with it"
    )


def test_a_failed_statement_raises_and_leaves_the_connection_usable(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    _require_streaming(blocking_ws_connection)
    _seed(blocking_ws_connection)

    seen = []
    with pytest.raises(SurrealError, match="boom"):
        for row in blocking_ws_connection.query_stream(
            "SELECT * FROM stream_wide LIMIT 2; THROW 'boom';"
        ):
            seen.append(row)

    assert len(seen) == 2
    assert blocking_ws_connection._streams == {}
    assert blocking_ws_connection.query("RETURN 'alive'").execute() == ["alive"]


def test_a_stream_hands_a_notification_it_read_to_the_live_subscriber(
    blocking_ws_connection: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    """The stream's pump reads the socket, so it owes the subscriber what it finds.

    Deliberately no live iterator running: ``_iter_live`` reads the socket
    itself and yields its own notifications directly, so a version of this test
    that drained concurrently passed with ``_route_live_notification`` gutted -
    the live iterator simply won the race to read. With the stream as the only
    reader, a notification arriving mid-stream can *only* reach the subscriber
    by being routed, which is the invariant the blocking transport's shared
    router exists for.

    ``subscribe_live`` registers its queue eagerly, so the queue is there to
    receive without anything iterating it yet.
    """
    _require_streaming(blocking_ws_connection)
    _seed(blocking_ws_connection)

    live_id = blocking_ws_connection.live("stream_wide")
    notifications = blocking_ws_connection.subscribe_live(live_id)

    def write() -> None:
        time.sleep(0.5)
        blocking_ws_connection_secondary.query(
            "CREATE stream_wide:mid SET n = 2"
        ).execute()

    writer = threading.Thread(target=write)
    try:
        writer.start()
        # The trailing SLEEP keeps the stream pumping past the write, so the
        # notification lands while this is the only thing reading the socket.
        rows = list(
            blocking_ws_connection.query_stream("SELECT * FROM stream_wide; SLEEP 2s;")
        )
        writer.join(timeout=30)
        assert 121 <= len(rows) <= 122, len(rows)

        # Read off the subscriber's own queue with a deadline, not by iterating
        # the generator. `next()` would fall through to reading the socket when
        # the queue is empty and block there forever, so a routing regression
        # made this test *hang* rather than fail - which is worse than not
        # having it. The queue is what the pump routes into, so it is also the
        # most direct statement of the invariant.
        queues = blocking_ws_connection.live_queues[str(live_id)]
        assert len(queues) == 1
        change = queues[0].get(timeout=10)
        assert change["action"] == "CREATE"
        assert str(change["result"]["id"]) == "stream_wide:mid"
    finally:
        notifications.close()
        blocking_ws_connection.kill(live_id)


def test_variables_reach_a_streamed_query(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    _require_streaming(blocking_ws_connection)
    rows = list(
        blocking_ws_connection.query_stream(
            "RETURN $left + $right;", {"left": 40, "right": 2}
        )
    )
    assert rows == [42]


def test_query_stream_agrees_with_query_on_any_server(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Deliberately not gated on streaming support.

    On v3.3.0 and later this streams; on anything older it falls back to a
    buffered query and replays it. The answer has to be the same either way,
    which is the whole promise of the fallback.
    """
    _seed(blocking_ws_connection, count=10)

    buffered = blocking_ws_connection.query(MIXED_SQL).execute()
    statements = list(blocking_ws_connection.query_stream(MIXED_SQL).statements())
    assert [statement.value for statement in statements] == buffered
