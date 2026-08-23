"""Streaming queries over the async websocket, against a real server.

Needs SurrealDB v3.3.0 or later; each test self-skips against an older server
by asking for streaming outright rather than by parsing a version string, since
what matters is whether the method exists.

The differential test is the load-bearing one: it asserts a streamed answer is
the buffered answer, statement for statement and value for value. The rest pin
what only a live server can show - that rows really do arrive before the query
finishes, that a cancel reaches the server, and that a stream shares its
connection without disturbing anything else on it.
"""

import asyncio
import time
from typing import Any
from uuid import UUID

import pytest

from surrealdb import AsyncQueryStream
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.errors import SurrealError, UnsupportedFeatureError

# Every shape a statement's value can take: a row list, a bare value from a
# `RETURN`, a bare record from `SELECT ... FROM ONLY`, and a list that is a
# value rather than a set of rows.
MIXED_SQL = (
    "SELECT * FROM stream_wide ORDER BY id LIMIT 3; "
    "RETURN 42; "
    "SELECT * FROM ONLY stream_wide ORDER BY id LIMIT 1; "
    "RETURN [1, 2, 3]; "
    "SELECT count() FROM stream_wide GROUP ALL;"
)


async def _seed(connection: AsyncWsSurrealConnection, count: int = 120) -> None:
    await connection.query(
        "DEFINE TABLE IF NOT EXISTS stream_wide; DELETE stream_wide; "
        f"CREATE |stream_wide:{count}| SET n = 1 RETURN NONE"
    )


async def _require_streaming(connection: AsyncWsSurrealConnection) -> None:
    """Skip unless this server really streams.

    Only a *refusal* is a reason to skip. The same exception type also carries
    "this server speaks a protocol revision this SDK cannot read", and skipping
    on that would turn a version bump that breaks streaming outright into a
    green run - every test in this file quietly skipped. A refusal is what sets
    the connection's learned flag, so that is what is checked.
    """
    try:
        async for _ in connection.query_stream("RETURN 1", require_streaming=True):
            pass
    except UnsupportedFeatureError as exc:
        if connection._streaming_supported is not False:
            raise
        pytest.skip(f"this server will not stream: {exc}")


async def test_streamed_statements_match_the_buffered_answer(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """The stream carries exactly what `query` returns, in the same order."""
    await _require_streaming(async_ws_connection)
    await _seed(async_ws_connection)

    buffered = await async_ws_connection.query(MIXED_SQL)
    streamed = [
        statement
        async for statement in async_ws_connection.query_stream(MIXED_SQL).statements()
    ]

    assert [statement.value for statement in streamed] == buffered
    assert [statement.index for statement in streamed] == [0, 1, 2, 3, 4]
    # `single` is what tells one bare value from a list of rows, and it has to
    # agree with the shape the buffered answer took.
    assert [statement.single for statement in streamed] == [
        False,
        True,
        True,
        False,
        False,
    ]


async def test_rows_flatten_the_buffered_answer(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await _require_streaming(async_ws_connection)
    await _seed(async_ws_connection)

    buffered = await async_ws_connection.query(MIXED_SQL)
    expected: list[Any] = []
    for result in buffered:
        expected.extend(result if isinstance(result, list) else [result])

    rows = [row async for row in async_ws_connection.query_stream(MIXED_SQL)]
    assert rows == expected


async def test_rows_arrive_before_the_query_finishes(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """The whole point, and the one thing buffering cannot fake.

    A trailing `SLEEP` holds the query open long after the first statement's
    rows exist, so a first row that arrives well before the stream ends can
    only have been delivered mid-query.
    """
    await _require_streaming(async_ws_connection)
    await _seed(async_ws_connection)

    stream = async_ws_connection.query_stream("SELECT * FROM stream_wide; SLEEP 2s;")
    started = time.monotonic()
    iterator = stream.__aiter__()
    first_row = await iterator.__anext__()
    first_row_at = time.monotonic() - started

    assert first_row is not None
    assert first_row_at < 1.0, (
        f"the first row took {first_row_at:.2f}s, which is long enough that the "
        "query may have been buffered rather than streamed"
    )

    remaining = 0
    async for _ in iterator:
        remaining += 1
    assert time.monotonic() - started >= 2.0
    await stream.aclose()


async def test_stopping_early_cancels_the_query_server_side(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """A `break` must reach the server, not wait out a ten-second sleep."""
    await _require_streaming(async_ws_connection)
    await _seed(async_ws_connection)

    started = time.monotonic()
    seen = 0
    async with async_ws_connection.query_stream(
        "SELECT * FROM stream_wide; SLEEP 10s;"
    ) as stream:
        async for _ in stream:
            seen += 1
            if seen == 3:
                break
    elapsed = time.monotonic() - started

    assert seen == 3
    # Clear of `_CANCEL_DRAIN_TIMEOUT` (5s), which is what a cancel that never
    # reaches the server actually costs - the teardown drains and gives up on
    # that deadline rather than waiting out the SLEEP. A bound *at* 5.0 left a
    # ~50ms margin against a measured 0.11s, which is no margin at all.
    assert elapsed < 2.5, f"stopping the stream took {elapsed:.1f}s"
    assert async_ws_connection._streams == {}
    # The connection is untouched by the cancel.
    assert await async_ws_connection.query("RETURN 'alive'") == ["alive"]


async def test_a_buffered_query_answers_while_a_stream_is_open(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await _require_streaming(async_ws_connection)
    await _seed(async_ws_connection)

    started = time.monotonic()
    async with async_ws_connection.query_stream(
        "SLEEP 2s; SELECT * FROM stream_wide LIMIT 2;"
    ) as stream:
        iterator = stream.__aiter__()

        async def first_row() -> Any:
            return await iterator.__anext__()

        pending = asyncio.create_task(first_row())
        await asyncio.sleep(0.2)
        assert await async_ws_connection.query("RETURN 'interleaved'") == [
            "interleaved"
        ]
        answered_at = time.monotonic() - started
        assert not pending.done(), "the stream had already produced its first item"
        await pending
        finished_at = time.monotonic() - started

    # The timing is the whole assertion. Without it a reply starved until the
    # stream's SLEEP completed satisfied the test just as well, only slower -
    # which is precisely the regression the test is named for.
    assert answered_at < 1.0, (
        f"the buffered query was answered {answered_at:.2f}s in, so it waited on "
        "the stream rather than interleaving with it"
    )
    assert finished_at >= 2.0, (
        f"the stream finished after {finished_at:.2f}s, so its SLEEP never ran "
        "and the query was not answered mid-stream"
    )


async def _collect(stream: AsyncQueryStream) -> list[Any]:
    return [row async for row in stream]


async def test_two_streams_run_concurrently_on_one_connection(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """The quick stream must finish while the slow one is still executing.

    Collecting both and checking their contents proves only that two streams
    work in sequence, which is what an earlier version of this test did. What
    makes it a concurrency test is asserting the slow stream has *not* finished
    at the moment the quick one has.
    """
    await _require_streaming(async_ws_connection)
    await _seed(async_ws_connection)

    slow = async_ws_connection.query_stream("SLEEP 3s; SELECT * FROM stream_wide;")
    quick = async_ws_connection.query_stream("RETURN 'quick';")
    try:
        slow_task = asyncio.create_task(_collect(slow))
        # The quick stream is opened second and must complete first.
        assert await _collect(quick) == ["quick"]
        assert not slow_task.done(), (
            "the slow stream had already finished, so the two never overlapped"
        )
        slow_rows = await slow_task
        # SLEEP's own None, then every row `_seed` created. Exact, because a
        # `> 1` bound would accept any amount of frame loss or truncation.
        assert len(slow_rows) == 121, len(slow_rows)
    finally:
        await slow.aclose()
        await quick.aclose()


async def test_a_failed_statement_raises_and_leaves_the_connection_usable(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await _require_streaming(async_ws_connection)
    await _seed(async_ws_connection)

    seen = []
    with pytest.raises(SurrealError, match="boom"):
        async for row in async_ws_connection.query_stream(
            "SELECT * FROM stream_wide LIMIT 2; THROW 'boom'; RETURN 'after';"
        ):
            seen.append(row)

    # The rows delivered before the failure were real, and the failure did not
    # take the connection with it.
    assert len(seen) == 2
    assert async_ws_connection._streams == {}
    assert await async_ws_connection.query("RETURN 'alive'") == ["alive"]


async def test_a_streamed_live_select_reports_its_id_and_delivers(
    async_ws_connection: AsyncWsSurrealConnection,
    async_ws_connection_secondary: AsyncWsSurrealConnection,
) -> None:
    """A `LIVE SELECT` in a stream is a real subscription, not a buffered stub."""
    await _require_streaming(async_ws_connection)
    await async_ws_connection.query("DEFINE TABLE IF NOT EXISTS stream_live")
    await async_ws_connection.query("DELETE stream_live")

    statements = [
        statement
        async for statement in async_ws_connection.query_stream(
            "LIVE SELECT * FROM stream_live;"
        ).statements()
    ]
    assert len(statements) == 1
    assert statements[0].query_type == "live"
    # A statement's value is a `Value`, so the live id needs narrowing before it
    # can be handed to the live-query API - which is exactly what calling code
    # has to do too.
    live_id = statements[0].value
    assert isinstance(live_id, (str, UUID))

    notifications = await async_ws_connection.subscribe_live(live_id)
    await async_ws_connection_secondary.query("CREATE stream_live:one SET v = 1")

    change = await asyncio.wait_for(notifications.__anext__(), 10)
    assert change["action"] == "CREATE"
    await async_ws_connection.kill(live_id)


async def test_variables_reach_a_streamed_query(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await _require_streaming(async_ws_connection)
    rows = [
        row
        async for row in async_ws_connection.query_stream(
            "RETURN $left + $right;", {"left": 40, "right": 2}
        )
    ]
    assert rows == [42]


async def test_query_stream_agrees_with_query_on_any_server(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """Deliberately not gated on streaming support.

    On v3.3.0 and later this streams; on anything older it falls back to a
    buffered query and replays it. The answer has to be the same either way,
    which is the whole promise of the fallback - so this is the one test in the
    file that runs against every server version CI exercises.
    """
    await _seed(async_ws_connection, count=10)

    buffered = await async_ws_connection.query(MIXED_SQL)
    statements = [
        statement
        async for statement in async_ws_connection.query_stream(MIXED_SQL).statements()
    ]
    assert [statement.value for statement in statements] == buffered


async def test_a_failed_statement_stops_the_rest_of_the_query(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """Documents an intended divergence from `query()`, not a bug.

    Iteration raises at the failing statement and the server is asked to
    abandon what is left, so a slow statement after the failure never runs -
    where `query()` executes the whole query and only then raises. Pinned
    because it is a real difference in side effects, and one a caller could be
    caught by: the fix on their side is a transaction, not a retry.
    """
    await _require_streaming(async_ws_connection)
    sql = (
        "CREATE se_div:a SET n = 1; THROW 'stop'; SLEEP 3s; CREATE se_div:b SET n = 2;"
    )

    async def present() -> list[str]:
        rows = await async_ws_connection.query("SELECT * FROM se_div")
        return sorted(str(row["id"]) for row in rows[0])

    async def reset() -> None:
        await async_ws_connection.query(
            "DEFINE TABLE IF NOT EXISTS se_div; DELETE se_div"
        )

    # Matched precisely: "stop" alone also matches the SDK's own teardown error,
    # "The streaming query was stopped before it completed", so a stream that
    # failed for an unrelated reason would have satisfied it.
    thrown = r"An error occurred: stop"

    await reset()
    with pytest.raises(SurrealError, match=thrown):
        await async_ws_connection.query(sql)
    assert await present() == ["se_div:a", "se_div:b"]

    await reset()
    with pytest.raises(SurrealError, match=thrown):
        async for _ in async_ws_connection.query_stream(sql):
            pass
    # Long enough that the trailing CREATE would have landed had the cancel not
    # reached the server.
    await asyncio.sleep(5)
    assert await present() == ["se_div:a"]
