"""`query()` streams without being asked to, and the answer is unchanged.

The differential tests elsewhere prove the streamed answer equals the buffered
one for a stream a caller opened deliberately. These prove the same for callers
who never mentioned streaming: `query`, `select`, `create` and the builders,
which all reach the wire through `query_raw`.

Nothing here skips on an old server. That is the point - the answer has to be
the same whether the server streamed it or not, so every assertion below holds
either way, and the two paths are compared against each other where it matters.
"""

from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.errors import ServerError

MIXED_SQL = (
    "SELECT * FROM inv ORDER BY id LIMIT 3; RETURN 42; "
    "SELECT * FROM ONLY inv ORDER BY id LIMIT 1; RETURN [1, 2, 3];"
)

SEED = (
    "DEFINE TABLE IF NOT EXISTS inv; DELETE inv; CREATE |inv:6| SET n = 1 RETURN NONE"
)


async def test_query_returns_the_same_answer_either_way(
    connection_params: dict[str, Any],
) -> None:
    """The load-bearing test for invisible adoption: same answer, both paths."""
    streamed = AsyncWsSurrealConnection(connection_params["ws_url"])
    buffered = AsyncWsSurrealConnection(connection_params["ws_url"], streaming=False)
    try:
        for db in (streamed, buffered):
            await db.signin(connection_params["vars_params"])
            await db.use(
                namespace=connection_params["namespace"],
                database=connection_params["database_name"],
            )
        await streamed.query(SEED)

        assert await streamed.query(MIXED_SQL) == await buffered.query(MIXED_SQL)
        assert await streamed.select("inv") == await buffered.select("inv")
        # The raw responses are not compared whole: `time` is the server's own
        # measurement and differs per call. The keys and the values are what
        # have to match, and those are compared below.

        streamed_raw = await streamed.query_raw(MIXED_SQL)
        buffered_raw = await buffered.query_raw(MIXED_SQL)
        assert [sorted(st) for st in streamed_raw["result"]] == [
            sorted(st) for st in buffered_raw["result"]
        ], "the rebuilt statements do not carry the same keys"
        assert [st["result"] for st in streamed_raw["result"]] == [
            st["result"] for st in buffered_raw["result"]
        ]
    finally:
        await streamed.close()
        await buffered.close()


async def test_a_failing_statement_reports_the_same_either_way(
    connection_params: dict[str, Any],
) -> None:
    """Including the error's type and code, which the frame carries and a
    buffered result does not."""
    sql = "RETURN 1; THROW 'boom'; RETURN 'after';"
    streamed = AsyncWsSurrealConnection(connection_params["ws_url"])
    buffered = AsyncWsSurrealConnection(connection_params["ws_url"], streaming=False)
    try:
        for db in (streamed, buffered):
            await db.signin(connection_params["vars_params"])
            await db.use(
                namespace=connection_params["namespace"],
                database=connection_params["database_name"],
            )

        errors: list[ServerError] = []
        for db in (streamed, buffered):
            with pytest.raises(ServerError) as caught:
                await db.query(sql)
            errors.append(caught.value)

        first, second = errors
        assert type(first) is type(second)
        assert str(first) == str(second)
        assert first.code == second.code == 0
        assert first.kind == second.kind

        # Both paths still return every statement, the failure included.
        for db in (streamed, buffered):
            raw = await db.query_raw(sql)
            assert [st["status"] for st in raw["result"]] == ["OK", "ERR", "OK"]
    finally:
        await streamed.close()
        await buffered.close()


async def test_a_query_in_a_transaction_is_never_streamed(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """A commit arriving mid-stream would commit a prefix of the query.

    Requests on one connection are served concurrently, so nothing stops a
    `commit` landing while a streamed query is still executing on the same
    transaction. Excluding them removes the hazard rather than documenting it.
    """
    await async_ws_connection.query(SEED)
    txn = await async_ws_connection.begin()
    try:
        assert async_ws_connection._may_stream(txn) is False
        # And it is the transaction doing the excluding, not the server - but
        # only a server that can stream can show that. Asserting it
        # unconditionally made this a test of the server's version: against
        # v2.x and v3.0.5 the connection had already learned it cannot stream,
        # so the "without a transaction it would" half was simply false.
        if async_ws_connection._streaming_supported is not False:
            assert async_ws_connection._may_stream(None) is True
        # And the query still works, on the buffered path.
        rows = await async_ws_connection.query("SELECT * FROM inv LIMIT 2", txn_id=txn)
        first = rows[0]
        assert isinstance(first, list)
        assert len(first) == 2
    finally:
        await async_ws_connection.commit(txn)


async def test_the_off_switch_puts_every_query_back_on_the_buffered_path(
    connection_params: dict[str, Any],
) -> None:
    db = AsyncWsSurrealConnection(connection_params["ws_url"], streaming=False)
    try:
        await db.signin(connection_params["vars_params"])
        await db.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        await db.query(SEED)
        assert db._may_stream(None) is False
        records = await db.select("inv")
        assert isinstance(records, list)
        assert len(records) == 6
        # Nothing was ever registered as a stream.
        assert db._streams == {}
    finally:
        await db.close()
