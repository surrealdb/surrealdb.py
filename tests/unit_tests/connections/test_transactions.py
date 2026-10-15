"""`batch()` on every transport, and `begin_transaction()` and `set()` on the
websocket connections, against a real server."""

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from surrealdb import AsyncSurreal, RecordID, Surreal
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import AlreadyExistsError, ServerError, ThrownError
from surrealdb.features import Features

pytestmark = pytest.mark.network

Blocking = BlockingWsSurrealConnection | BlockingHttpSurrealConnection
Async = AsyncWsSurrealConnection | AsyncHttpSurrealConnection


@pytest.fixture(params=["ws", "http"])
def db(
    request: pytest.FixtureRequest, connection_params: dict[str, Any]
) -> Iterator[Blocking]:
    url = connection_params["ws_url" if request.param == "ws" else "url"]
    connection = Surreal(url)
    connection.signin(connection_params["vars_params"])
    database = f"txn_{uuid.uuid4().hex[:8]}"
    connection.use(connection_params["namespace"], database)
    try:
        yield connection
    finally:
        connection.query(f"REMOVE DATABASE IF EXISTS {database};").execute()
        connection.close()


@pytest.fixture(params=["ws", "http"])
async def adb(
    request: pytest.FixtureRequest, connection_params: dict[str, Any]
) -> AsyncIterator[Async]:
    url = connection_params["ws_url" if request.param == "ws" else "url"]
    connection = AsyncSurreal(url)
    await connection.signin(connection_params["vars_params"])
    database = f"txn_{uuid.uuid4().hex[:8]}"
    await connection.use(connection_params["namespace"], database)
    try:
        yield connection
    finally:
        await connection.query(f"REMOVE DATABASE IF EXISTS {database};")
        await connection.close()


def _count(db: Blocking, table: str) -> Any:
    return db.query(f"RETURN count(SELECT * FROM {table});").first()


def test_a_batch_applies_every_statement(db: Blocking) -> None:
    results = (
        db.batch()
        .query("CREATE account:a SET balance = $start", {"start": 100})
        .query("CREATE account:b SET balance = $start;")
        .query("UPDATE account:a SET balance -= $amount", {"amount": 10})
        .query("UPDATE account:b SET balance += $amount RETURN VALUE balance")
        .execute()
    )
    assert len(results) == 4
    assert results[3] == [110]
    assert db.query("SELECT VALUE balance FROM account:a;").first() == [90]


def test_a_failed_statement_applies_none_and_is_raised(db: Blocking) -> None:
    db.query("CREATE account:a;").execute()
    with pytest.raises(ServerError, match="already exists") as caught:
        db.batch().query("CREATE account:b").query("CREATE account:a").execute()
    if db.is_feature_supported(Features.IMPORT_FAILURE_REPORTING):
        assert isinstance(caught.value, AlreadyExistsError)
    assert _count(db, "account") == 1

    with pytest.raises(ServerError, match="boom"):
        db.batch().query("CREATE account:c").query("THROW 'boom'").execute()
    assert _count(db, "account") == 1


def test_a_batch_refuses_what_it_cannot_send(db: Blocking) -> None:
    with pytest.raises(ValueError, match="empty batch"):
        db.batch().execute()
    with pytest.raises(ValueError, match="needs a statement"):
        db.batch().query("  ;  ")
    with pytest.raises(ValueError, match=r"\$n is already bound"):
        db.batch().query("RETURN $n", {"n": 1}).query("RETURN $n", {"n": 2})
    db.batch().query("RETURN $n", {"n": 1}).query("RETURN $n", {"n": 1}).execute()


async def test_async_batch(adb: Async) -> None:
    results = await (
        adb.batch()
        .query("CREATE thing:1 SET n = $n", {"n": 1})
        .query("SELECT VALUE n FROM thing")
        .execute()
    )
    assert results[1] == [1]
    with pytest.raises(
        ThrownError
        if adb.is_feature_supported(Features.IMPORT_FAILURE_REPORTING)
        else ServerError
    ):
        await adb.batch().query("CREATE thing:2").query("THROW 'no'").execute()
    assert await adb.query("RETURN count(SELECT * FROM thing);").first() == 1


def test_begin_transaction_on_the_root_session(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    db = blocking_ws_connection
    if not db.is_feature_supported(Features.TRANSACTIONS):
        pytest.skip("interactive transactions need SurrealDB 3.0 or later")
    table = f"txn_{uuid.uuid4().hex[:8]}"
    try:
        with db.begin_transaction() as txn:
            txn.set("n", 7)
            txn.query(f"CREATE {table}:1 SET n = $n;").execute()
        assert db.query(f"SELECT VALUE n FROM {table}:1;").first() == [7]

        with pytest.raises(RuntimeError), db.begin_transaction() as txn:
            txn.query(f"CREATE {table}:2;").execute()
            raise RuntimeError("cancel it")
        assert db.select(RecordID(table, 2)).execute() is None
    finally:
        db.query(f"REMOVE TABLE IF EXISTS {table};").execute()


async def test_async_set_and_begin_transaction(
    connection_params: dict[str, Any],
) -> None:
    db = AsyncWsSurrealConnection(connection_params["ws_url"])
    await db.signin(connection_params["vars_params"])
    await db.use(connection_params["namespace"], connection_params["database_name"])
    try:
        await db.set("greeting", "hi")
        assert await db.query("RETURN $greeting;").first() == "hi"
        if not db.is_feature_supported(Features.TRANSACTIONS):
            return
        session = await db.new_session()
        await session.use(
            connection_params["namespace"], connection_params["database_name"]
        )
        await session.set("x", 1)
        assert await session.query("RETURN $x;").first() == 1
        async with await db.begin_transaction() as txn:
            assert await txn.query("RETURN $greeting;").first() == "hi"
        await session.close_session()
    finally:
        await db.close()


def test_a_query_may_hold_several_statements(db: Blocking) -> None:
    results = (
        db.batch()
        .query("CREATE item:a; CREATE item:b")
        .query("SELECT VALUE id FROM item")
        .execute()
    )
    assert len(results) == 3
    assert len(results[2]) == 2  # type: ignore[arg-type]


def test_a_trailing_line_comment_keeps_its_statement_apart(db: Blocking) -> None:
    results = (
        db.batch().query("CREATE item:a -- the first").query("CREATE item:b").execute()
    )
    assert len(results) == 2
    assert _count(db, "item") == 2


def test_a_binding_must_match_in_type_too(db: Blocking) -> None:
    with pytest.raises(ValueError, match=r"\$x is already bound"):
        db.batch().query("RETURN $x", {"x": True}).query("RETURN $x", {"x": 1})
    with pytest.raises(ValueError, match=r"\$x is already bound"):
        db.batch().query("RETURN $x", {"x": [1]}).query("RETURN $x", {"x": [1.0]})


def test_a_refused_query_leaves_the_batch_as_it_was(db: Blocking) -> None:
    batch = db.batch().query("RETURN $x", {"x": 1})
    with pytest.raises(ValueError):
        batch.query("RETURN [$y, $x]", {"y": 2, "x": 3})
    assert batch._variables == {"x": 1}
    assert batch.execute() == [1]


def test_set_is_let_on_every_transport(db: Blocking) -> None:
    db.set("answer", 42)
    assert db.query("RETURN $answer;").first() == 42


async def test_async_set_is_let_on_every_transport(adb: Async) -> None:
    await adb.set("answer", 42)
    assert await adb.query("RETURN $answer;").first() == 42
