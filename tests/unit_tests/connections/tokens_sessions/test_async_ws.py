"""Refresh, revoke, reset, session listing and forking, partial `use` and
`health()` on the async websocket, against a real server."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from surrealdb import Null
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.errors import (
    ConnectionUnavailableError,
    ServerError,
    UnavailableFeatureError,
)
from surrealdb.features import Features


@pytest.fixture
async def db(
    connection_params: dict[str, Any],
) -> AsyncIterator[AsyncWsSurrealConnection]:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    try:
        yield connection
    finally:
        await connection.close()


async def _root(
    db: AsyncWsSurrealConnection, connection_params: dict[str, Any]
) -> None:
    await db.signin(connection_params["vars_params"])
    await db.use(connection_params["namespace"], connection_params["database_name"])


async def test_refresh_exchanges_the_held_tokens(
    db: AsyncWsSurrealConnection, record_user: dict[str, Any]
) -> None:
    first = await db.signup(record_user)
    assert first.refresh is not None

    renewed = await db.refresh()

    assert renewed.access is not None
    assert renewed.refresh is not None
    assert renewed.refresh != first.refresh
    assert db.token == renewed.access
    assert await db.query("RETURN $access;").first() == record_user["access"]
    # The old refresh token was spent.
    with pytest.raises(ServerError):
        await db.refresh(first)


async def test_revoke_spends_the_refresh_token(
    db: AsyncWsSurrealConnection, record_user: dict[str, Any]
) -> None:
    await db.signup(record_user)
    tokens = await db.signin(record_user)

    await db.revoke()

    # Revoking does not sign out...
    assert await db.query("RETURN $access;").first() == record_user["access"]
    # ...but the refresh token is gone, here and on the server.
    with pytest.raises(ValueError, match="refresh token"):
        await db.refresh()
    with pytest.raises(ServerError):
        await db.refresh(tokens)


async def test_refresh_without_a_refresh_token_says_what_to_pass(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    with pytest.raises(ValueError, match="WITH REFRESH"):
        await db.refresh()


async def test_reset_clears_the_session(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    await db.let("answer", 42)
    heard: list[tuple[str, tuple[Any, ...]]] = []
    db.subscribe("using", lambda *a: heard.append(("using", a)))
    db.subscribe("auth", lambda *a: heard.append(("auth", a)))

    await db.reset()

    assert db.namespace is None
    assert db.database is None
    assert db.token is None
    assert heard == [("using", (None, None, None)), ("auth", (None, None))]
    await db.use(connection_params["namespace"], connection_params["database_name"])
    assert await db.query("RETURN $answer;").first() is None


async def test_sessions_lists_the_attached_sessions(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    session = await db.new_session()
    assert session.id in await db.sessions()
    await session.close_session()
    assert session.id not in await db.sessions()


async def test_fork_copies_the_session_and_then_goes_its_own_way(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    await db.let("where", "root")

    fork = await db.fork_session()
    assert await fork.query(
        "RETURN [$where, session::ns(), session::db()];"
    ).first() == [
        "root",
        connection_params["namespace"],
        connection_params["database_name"],
    ]
    assert isinstance(await fork.query("INFO FOR ROOT;").first(), dict)

    await fork.let("where", "fork")
    await fork.use(database="fork_db")
    assert await db.query("RETURN [$where, session::db()];").first() == [
        "root",
        connection_params["database_name"],
    ]

    second = await fork.fork()
    assert await second.query("RETURN [$where, session::db()];").first() == [
        "fork",
        "fork_db",
    ]
    await second.close_session()
    await fork.close_session()


async def test_use_changes_only_what_it_is_given(
    db: AsyncWsSurrealConnection, connection_params: dict[str, Any]
) -> None:
    await _root(db, connection_params)

    await db.use(database="other_db")
    assert await db.query("RETURN [session::ns(), session::db()];").first() == [
        connection_params["namespace"],
        "other_db",
    ]
    assert db.namespace == connection_params["namespace"]
    assert db.database == "other_db"

    await db.use(namespace="other_ns")
    assert await db.query("RETURN session::ns();").first() == "other_ns"
    assert db.database == "other_db"


async def test_use_null_clears_the_selection(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    await db.use(Null, Null)
    assert db.namespace is None
    assert db.database is None
    assert await db.query("RETURN session::ns();").first() is None


async def test_health(
    db: AsyncWsSurrealConnection, connection_params: dict[str, Any]
) -> None:
    await db.health()
    nowhere = AsyncWsSurrealConnection("ws://127.0.0.1:1")
    with pytest.raises(ConnectionUnavailableError, match="health"):
        await nowhere.health()


async def test_v2_refuses_before_sending(
    db: AsyncWsSurrealConnection, connection_params: dict[str, Any]
) -> None:
    await _root(db, connection_params)
    if db.is_feature_supported(Features.SESSIONS):
        pytest.skip("needs a SurrealDB 2.x server")
    for call in (db.refresh, db.revoke, db.reset, db.sessions, db.fork_session):
        with pytest.raises(UnavailableFeatureError):
            await call()


async def test_reset_ends_the_session_live_queries(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    await db.query("DEFINE TABLE IF NOT EXISTS reset_live;").execute()
    live_id = await db.live("reset_live")
    notifications = await db.subscribe_live(live_id)
    await db.reset()
    assert str(live_id) not in db._registry.live
    assert [n async for n in notifications] == []


async def test_fork_keeps_no_rejected_credentials(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    db._registry.root.access = "not.a.token"
    fork = await db.fork_session()
    assert db._registry.state(fork.id).access is None
    await fork.close_session()


async def test_cannot_fork_a_closed_session(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    session = await db.new_session()
    await session.close_session()
    with pytest.raises(ValueError, match="not attached"):
        await session.fork()
    assert session.id not in db._registry.sessions


async def test_token_methods_on_a_closed_session_do_not_reopen_it(
    db: AsyncWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    await _root(db, connection_params)
    session = await db.new_session()
    await session.close_session()
    with pytest.raises(ValueError, match="does not hold"):
        await session.refresh()
    with pytest.raises(ValueError, match="does not hold"):
        await session.revoke()
    assert session.id not in db._registry.sessions
