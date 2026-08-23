"""`query()` streams without being asked to, and the answer is unchanged.

The differential tests elsewhere prove the streamed answer equals the buffered
one for a stream a caller opened deliberately. These prove the same for callers
who never mentioned streaming: `query`, `select`, `create` and the builders,
which all reach the wire through `query_raw`.

Nothing here skips on an old server. That is the point - the answer has to be
the same whether the server streamed it or not, so every assertion below holds
either way, and the two paths are compared against each other where it matters.
The one exception is the tail of the transaction test, which needs a transaction
the server knows about; the exclusion that test is really about is checked
everywhere.
"""

from typing import Any
from uuid import uuid4

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import NotFoundError, ServerError

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
        # Equal answers would also hold if nothing ever streamed, so witness
        # that the streaming path was taken: attempting it settles the
        # capability either way, and never attempting leaves it unknown.
        assert streamed._streaming_supported is not None
        assert buffered._streaming_supported is None
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
    # The exclusion is a rule of the connection's, so it is checked as one.
    # Reading it off the live connection instead made it a test of the server's
    # version: where the server cannot stream, `_may_stream` is False whatever
    # it is passed, so the transaction clause could be deleted without this
    # noticing. Claiming streaming is available puts the transaction back in
    # charge of the answer, on every server.
    was_supported = async_ws_connection._streaming_supported
    async_ws_connection._streaming_supported = True
    try:
        assert async_ws_connection._may_stream(uuid4()) is False
        assert async_ws_connection._may_stream(None) is True
    finally:
        async_ws_connection._streaming_supported = was_supported
    # The rest needs a transaction the server knows about, and the RPC that
    # opens one arrived in 3.x - on 2.x `begin` is itself Method not found.
    try:
        txn = await async_ws_connection.begin()
    except NotFoundError:
        pytest.skip("client-side transactions over RPC need SurrealDB 3.x")
    try:
        assert async_ws_connection._may_stream(txn) is False
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


def test_blocking_query_returns_the_same_answer_either_way(
    connection_params: dict[str, Any],
) -> None:
    """The blocking transport streams invisibly too, and it is its own code.

    Without this, deleting the streaming branch from the blocking `query_raw`
    broke nothing: the rest of the blocking streaming suite calls
    `query_stream` explicitly, which never consults `_may_stream`.
    """
    streamed = BlockingWsSurrealConnection(connection_params["ws_url"])
    buffered = BlockingWsSurrealConnection(connection_params["ws_url"], streaming=False)
    try:
        for db in (streamed, buffered):
            db.signin(connection_params["vars_params"])
            db.use(connection_params["namespace"], connection_params["database_name"])
        streamed.query(SEED).execute()

        assert (
            streamed.query(MIXED_SQL).execute() == buffered.query(MIXED_SQL).execute()
        )
        assert streamed.select("inv") == buffered.select("inv")

        streamed_raw = streamed.query_raw(MIXED_SQL)
        buffered_raw = buffered.query_raw(MIXED_SQL)
        assert [sorted(st) for st in streamed_raw["result"]] == [
            sorted(st) for st in buffered_raw["result"]
        ], "the rebuilt statements do not carry the same keys"
        assert [st["result"] for st in streamed_raw["result"]] == [
            st["result"] for st in buffered_raw["result"]
        ]
        # Equal answers alone would also be satisfied by never streaming at
        # all, so witness that the path was taken: a connection that tries to
        # stream learns whether it can (True here, False on a server too old),
        # while one that never tries still knows nothing.
        assert streamed._streaming_supported is not None
        assert buffered._streaming_supported is None
        # The off switch reaches the blocking transport as well.
        assert buffered._may_stream(None) is False
        assert buffered._streams == {}
    finally:
        streamed.close()
        buffered.close()


def test_a_blocking_query_in_a_transaction_is_never_streamed(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The same exclusion, separately implemented, so separately tested."""
    blocking_ws_connection.query(SEED).execute()
    was_supported = blocking_ws_connection._streaming_supported
    blocking_ws_connection._streaming_supported = True
    try:
        assert blocking_ws_connection._may_stream(uuid4()) is False
        assert blocking_ws_connection._may_stream(None) is True
    finally:
        blocking_ws_connection._streaming_supported = was_supported
    try:
        txn = blocking_ws_connection.begin()
    except NotFoundError:
        pytest.skip("client-side transactions over RPC need SurrealDB 3.x")
    try:
        assert blocking_ws_connection._may_stream(txn) is False
        rows = blocking_ws_connection.query(
            "SELECT * FROM inv LIMIT 2", txn_id=txn
        ).execute()
        first = rows[0]
        assert isinstance(first, list)
        assert len(first) == 2
    finally:
        blocking_ws_connection.commit(txn)
