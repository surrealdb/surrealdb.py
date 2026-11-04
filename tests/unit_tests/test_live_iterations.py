"""Iterating one live subscription more than once, against a fake server.

A change made between two iterations is delivered to the second. Each
iteration used to subscribe afresh, and its registration went when it ended,
so such a change reached nobody: on async, as soon as the loop finalised the
first iteration; on blocking, once any request read the socket in the gap.
"""

import asyncio
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from tests.unit_tests.fake_surreal import FakeSurreal


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
