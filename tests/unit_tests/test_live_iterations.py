"""Iterating one live subscription more than once, against a fake server.

A change made between two iterations is delivered to the second. Each
iteration used to subscribe afresh, and its registration went when it ended,
so such a change reached nobody: on async, as soon as the loop finalised the
first iteration; on blocking, once any request read the socket in the gap.
"""

import asyncio
import threading
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.reconnect import ReconnectOptions
from surrealdb.errors import ConnectionUnavailableError
from tests.unit_tests.fake_surreal import FakeSurreal

FAST = ReconnectOptions(retry_delay=0.01, retry_delay_max=0.02, retry_delay_jitter=0)


@pytest.fixture
def fake() -> Iterator[FakeSurreal]:
    server = FakeSurreal()
    try:
        yield server
    finally:
        server.close()


def _next_within(iterator: Iterator[Any], seconds: float) -> Any:
    """The next item, read on a thread so a missing one fails rather than hangs."""
    got: list[Any] = []
    reader = threading.Thread(target=lambda: got.append(next(iterator)), daemon=True)
    reader.start()
    reader.join(seconds)
    assert got, f"nothing arrived within {seconds}s"
    return got[0]


async def test_async_a_change_between_two_iterations_reaches_the_second(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=False)
    try:
        sub = await db.live("person")
        fake.notify(sub, "CREATE", {"n": 1})
        async for change in sub:
            assert change["result"] == {"n": 1}
            break
        fake.notify(sub, "CREATE", {"n": 2})
        await asyncio.sleep(0.1)
        change = await asyncio.wait_for(sub.__aiter__().__anext__(), 2)
        assert change["result"] == {"n": 2}
    finally:
        await db.close()


def test_blocking_a_change_between_two_iterations_reaches_the_second(
    fake: FakeSurreal,
) -> None:
    db = BlockingWsSurrealConnection(fake.url, reconnect=False)
    try:
        sub = db.live("person")
        fake.notify(sub, "CREATE", {"n": 1})
        for change in sub:
            assert change["result"] == {"n": 1}
            break
        fake.notify(sub, "CREATE", {"n": 2})
        db.version()
        change = _next_within(iter(sub), 2)
        assert change["result"] == {"n": 2}
    finally:
        db.close()


async def test_async_overlapping_iterations_each_receive_every_change(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=False)
    try:
        sub = await db.live("person")
        first, second = sub.__aiter__(), sub.__aiter__()
        pending = [asyncio.ensure_future(it.__anext__()) for it in (first, second)]
        await asyncio.sleep(0.1)
        fake.notify(sub, "CREATE", {"n": 1})
        results = await asyncio.wait_for(asyncio.gather(*pending), 2)
        assert [change["result"] for change in results] == [{"n": 1}, {"n": 1}]
    finally:
        await db.close()


async def test_async_an_iteration_after_a_kill_yields_nothing(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=False)
    try:
        sub = await db.live("person")
        fake.notify(sub, "CREATE", {"n": 1})
        async for _ in sub:
            break
        await sub.kill()
        assert [change async for change in sub] == []
        assert not sub.is_alive
    finally:
        await db.close()


async def _until(predicate: Any, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def test_async_a_subscription_the_drop_ended_raises_when_read_later(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=False)
    try:
        sub = await db.live("person")
        fake.drop()
        await _until(lambda: db.status == "disconnected")
        assert not sub.is_alive
        with pytest.raises(ConnectionUnavailableError, match="was lost"):
            [change async for change in sub]
    finally:
        await db.close()


async def test_async_a_live_of_subscription_a_reconnect_left_raises_when_read(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        await db.connect()
        sub = db.live_of(uuid.uuid4())
        sockets = fake.sockets_opened
        fake.drop()
        await _until(lambda: fake.sockets_opened > sockets and db.status == "connected")
        with pytest.raises(ConnectionUnavailableError, match="was lost"):
            [change async for change in sub]
    finally:
        await db.close()


def test_blocking_a_subscription_the_drop_ended_raises_when_read_later(
    fake: FakeSurreal,
) -> None:
    db = BlockingWsSurrealConnection(fake.url, reconnect=False)
    try:
        sub = db.live("person")
        fake.drop()
        fake.wait_for(lambda: db.socket is not None and db.socket.state.name != "OPEN")
        db.version()
        assert not sub.is_alive
        changes = iter(sub)
        with pytest.raises(ConnectionUnavailableError, match="was lost"):
            next(changes)
        with pytest.raises(ConnectionUnavailableError, match="was lost"):
            list(sub)
    finally:
        db.close()


async def test_async_a_killed_subscription_still_ends_cleanly_after_a_drop(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=False)
    try:
        sub = await db.live("person")
        await sub.kill()
        fake.drop()
        await _until(lambda: db.status == "disconnected")
        assert [change async for change in sub] == []
    finally:
        await db.close()


def test_blocking_a_live_read_that_finds_the_socket_closed_reports_it(
    fake: FakeSurreal,
) -> None:
    db = BlockingWsSurrealConnection(fake.url, reconnect=False)
    events: list[str] = []
    db.subscribe("disconnected", lambda *_: events.append("disconnected"))
    try:
        changes = iter(db.live("person"))
        fake.drop()
        with pytest.raises(ConnectionUnavailableError):
            next(changes)
        assert db.status == "disconnected"
        assert not db.is_connected
        assert events == ["disconnected"]
    finally:
        db.close()
