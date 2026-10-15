"""`live()` subscriptions and `live_of()`, against a real server."""

import asyncio
import copy
import threading
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID

import pytest

from surrealdb import AsyncLiveSubscription, LiveSubscription, RecordID
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import UnsupportedFeatureError
from surrealdb.features import parse_version


@pytest.fixture
async def adb(
    connection_params: dict[str, Any],
) -> AsyncIterator[AsyncWsSurrealConnection]:
    db = AsyncWsSurrealConnection(connection_params["ws_url"])
    await db.signin(connection_params["vars_params"])
    await db.use(connection_params["namespace"], connection_params["database_name"])
    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
def table(blocking_ws_connection: BlockingWsSurrealConnection) -> Iterator[str]:
    name = f"live_{uuid.uuid4().hex[:8]}"
    blocking_ws_connection.query(f"DEFINE TABLE {name} SCHEMALESS;").execute()
    yield name
    blocking_ws_connection.query(f"REMOVE TABLE IF EXISTS {name};").execute()


async def _first(sub: AsyncLiveSubscription, seconds: float = 10) -> Any:
    async def take() -> Any:
        async for notification in sub:
            return notification
        return None

    return await asyncio.wait_for(take(), seconds)


async def test_a_subscription_is_still_the_query_id(
    adb: AsyncWsSurrealConnection, table: str
) -> None:
    sub = await adb.live(table)
    assert isinstance(sub, UUID) and isinstance(sub, AsyncLiveSubscription)
    assert sub.id == UUID(str(sub)) and type(sub.id) is UUID
    assert sub.managed and sub.is_alive
    assert type(copy.copy(sub)) is UUID and copy.copy(sub) == sub.id
    notifications = await adb.subscribe_live(sub)
    await adb.create(RecordID(table, 1), {"n": 1})
    change = await asyncio.wait_for(anext(notifications), 10)
    assert change["action"] == "CREATE"
    await adb.kill(sub)


async def test_iterating_and_killing_a_subscription(
    adb: AsyncWsSurrealConnection, table: str
) -> None:
    sub = await adb.live(table)
    seen: list[Any] = []

    async def consume() -> None:
        async for notification in sub:
            seen.append(notification)

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.2)
    await adb.create(RecordID(table, 1), {"n": 1})
    for _ in range(100):
        if seen:
            break
        await asyncio.sleep(0.05)
    await sub.kill()
    await asyncio.wait_for(consumer, 10)
    assert [change["action"] for change in seen] == ["CREATE"]
    assert not sub.is_alive
    await sub.kill()


async def test_async_with_kills_on_exit(
    adb: AsyncWsSurrealConnection, table: str
) -> None:
    async with await adb.live(table) as sub:
        assert sub.is_alive
    assert not sub.is_alive
    assert str(sub) not in adb.live_queues


async def test_live_of_attaches_to_a_live_select(
    adb: AsyncWsSurrealConnection, table: str
) -> None:
    live_id: Any = await adb.query(f"LIVE SELECT * FROM {table};").first()
    sub = adb.live_of(live_id)
    assert not sub.managed
    task = asyncio.create_task(_first(sub))
    await asyncio.sleep(0.2)
    await adb.create(RecordID(table, "x"), {"n": 2})
    change = await task
    assert change["action"] == "CREATE"
    await sub.kill()


async def test_a_query_killed_on_the_server_ends_the_subscription(
    adb: AsyncWsSurrealConnection, table: str
) -> None:
    version = parse_version(adb.server_version or "")
    if version is not None and version < (3, 0, 0):
        pytest.skip("SurrealDB 2 sends no KILLED notification")
    sub = await adb.live(table)
    consumer = asyncio.create_task(_first(sub))
    await asyncio.sleep(0.2)
    await adb.query("KILL $id;", {"id": sub.id})
    assert await consumer is None
    assert not sub.is_alive


def test_blocking_subscription(
    blocking_ws_connection: BlockingWsSurrealConnection, table: str
) -> None:
    db = blocking_ws_connection
    with db.live(table) as sub:
        assert isinstance(sub, LiveSubscription) and isinstance(sub, UUID)
        notifications = iter(sub)
        db.create(RecordID(table, 1), {"n": 1})
        assert next(notifications)["action"] == "CREATE"
    assert not sub.is_alive
    assert list(notifications) == []

    live_id: Any = db.query(f"LIVE SELECT * FROM {table};").first()
    attached = db.live_of(live_id)
    notifications = iter(attached)
    db.create(RecordID(table, 2), {"n": 2})
    assert next(notifications)["action"] == "CREATE"
    attached.kill()


def test_http_has_no_live_queries(connection_params: dict[str, Any]) -> None:
    from surrealdb import Surreal

    db = Surreal(connection_params["url"])
    with pytest.raises(UnsupportedFeatureError):
        db.live_of(uuid.uuid4())


async def test_iterating_a_killed_subscription_ends_at_once(
    adb: AsyncWsSurrealConnection, table: str
) -> None:
    sub = await adb.live(table)
    await sub.kill()
    assert await asyncio.wait_for(_first(sub), 5) is None


def test_blocking_iterating_a_killed_subscription_ends_at_once(
    blocking_ws_connection: BlockingWsSurrealConnection, table: str
) -> None:
    sub = blocking_ws_connection.live(table)
    sub.kill()
    assert list(sub) == []


async def test_a_failed_kill_leaves_the_subscription_alive(
    adb: AsyncWsSurrealConnection, table: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub = await adb.live(table)
    real_kill = adb.kill

    async def failing_kill(*_args: Any, **_kwargs: Any) -> None:
        raise ConnectionError("the socket dropped")

    monkeypatch.setattr(adb, "kill", failing_kill)
    with pytest.raises(ConnectionError):
        await sub.kill()
    assert sub.is_alive
    monkeypatch.setattr(adb, "kill", real_kill)
    await sub.kill()
    assert not sub.is_alive


async def test_is_alive_follows_the_connection(
    connection_params: dict[str, Any], table: str
) -> None:
    db = AsyncWsSurrealConnection(connection_params["ws_url"])
    await db.signin(connection_params["vars_params"])
    await db.use(connection_params["namespace"], connection_params["database_name"])
    killed = await db.live(table)
    await db.kill(killed)
    assert not killed.is_alive
    left = await db.live(table)
    attached = db.live_of(await db.live(table))
    await db.close()
    assert not left.is_alive and not attached.is_alive


def test_blocking_is_alive_follows_the_connection(
    connection_params: dict[str, Any], table: str
) -> None:
    db = BlockingWsSurrealConnection(connection_params["ws_url"])
    db.signin(connection_params["vars_params"])
    db.use(connection_params["namespace"], connection_params["database_name"])
    killed = db.live(table)
    db.kill(killed)
    assert not killed.is_alive
    left = db.live(table)
    db.close()
    assert not left.is_alive


def test_blocking_close_ends_a_subscription_cleanly(
    connection_params: dict[str, Any], table: str
) -> None:
    db = BlockingWsSurrealConnection(connection_params["ws_url"])
    db.signin(connection_params["vars_params"])
    db.use(connection_params["namespace"], connection_params["database_name"])
    sub = db.live(table)
    outcome: list[Any] = []
    notifications = iter(sub)

    def consume() -> None:
        try:
            outcome.append(list(notifications))
        except Exception as exc:
            outcome.append(exc)

    reader = threading.Thread(target=consume)
    reader.start()
    db.close()
    reader.join(10)
    assert outcome == [[]]
