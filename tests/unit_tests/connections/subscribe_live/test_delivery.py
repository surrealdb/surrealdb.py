"""Every notification is delivered, and a killed query ends the subscription.

Two defects in how live notifications reach a consumer.

**A notification could be dropped before the first ``next()``.** The blocking
``subscribe_live`` was a plain generator function, so its body - including the
registration that says where notifications for this query should go - did not
run until the consumer first iterated. Any notification ``_send`` read off the
shared socket in that window found no queue, and was discarded with no error
and no log. A single RPC between ``live()`` and the first ``next()`` was enough
to lose a change permanently:

    live_id = db.live("person")
    sub = db.subscribe_live(live_id)
    other.create("person", {"name": "first"})
    db.query("RETURN 1").execute()          # <- swallows the notification
    other.create("person", {"name": "second"})
    next(sub)                               # 'second'; 'first' is gone

**A killed query yielded a fake notification and then never ended.** SurrealDB
marks the end of a live query with a ``KILLED`` notification. It reports that
the subscription is over rather than a change to the table - it carries no
record and its ``result`` is ``None`` - but both transports handed it to the
consumer, so ``update["result"]["field"]`` raised ``TypeError``. The generator
then went on waiting for a query that no longer existed.

``kill()`` on the *same* connection was already handled on the async side. This
covers the query being killed from anywhere else, which is the case neither
transport handled.
"""

import asyncio
import threading
import time
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

# Long enough not to flake, far below an indefinite hang.
_DEADLINE = 15.0


def _signals_a_killed_query(version: str) -> bool:
    """Whether this server tells subscribers that a live query has ended.

    3.x sends a ``KILLED`` notification when a query is killed, wherever the
    kill came from. 2.x sends nothing at all - a subscriber to a query killed
    from another connection simply stops hearing anything - so there is no
    signal for the SDK to end the generator on, and it keeps waiting.
    """
    text = (version or "").strip().lower()
    for prefix in ("surrealdb-", "v"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    try:
        return int(text.split(".")[0]) >= 3
    except (ValueError, IndexError):
        return False


# Shorter than the full deadline: on a server that never signals a kill this
# is spent proving a negative, once per test.
_NO_SIGNAL_GRACE = 3.0


def _next_within(subscription: Any, deadline: float = _DEADLINE) -> dict[str, Any]:
    """``next(subscription)``, but a lost notification fails instead of hanging.

    The blocking generator blocks until a notification arrives, so a dropped
    one means ``next()`` never returns. Without a deadline the whole defect
    reads as a hung test - which on CI is a job timeout with nothing pointing
    at the cause - rather than a failed assertion naming what was lost.
    """
    received: list[dict[str, Any]] = []
    failed: list[BaseException] = []

    def pull() -> None:
        try:
            received.append(next(subscription))
        except BaseException as error:  # noqa: BLE001 - re-raised below
            failed.append(error)

    reader = threading.Thread(target=pull, daemon=True)
    reader.start()
    reader.join(timeout=deadline)

    if failed:
        raise failed[0]
    assert received, (
        f"no notification arrived within {deadline}s - it was dropped before "
        "the subscription was registered"
    )
    return received[0]


def test_a_notification_survives_an_rpc_before_the_first_next(
    blocking_ws_connection: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    """The exact window that used to swallow a change."""
    blocking_ws_connection.query("DEFINE TABLE OVERWRITE person SCHEMALESS").execute()

    live_id = blocking_ws_connection.live("person")
    subscription = blocking_ws_connection.subscribe_live(live_id)

    blocking_ws_connection_secondary.create("person", {"name": "first"})
    time.sleep(0.5)

    # Any RPC on the subscribing connection reads from the same socket, so it
    # is what picks the notification up while correlating its own reply.
    blocking_ws_connection.query("RETURN 1").execute()
    time.sleep(0.2)

    try:
        assert _next_within(subscription)["result"]["name"] == "first"
    finally:
        subscription.close()
        blocking_ws_connection_secondary.kill(live_id)


def test_a_notification_arrives_with_no_rpc_in_between(
    blocking_ws_connection: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    """The control: the same sequence without the RPC always worked."""
    blocking_ws_connection.query("DEFINE TABLE OVERWRITE person SCHEMALESS").execute()

    live_id = blocking_ws_connection.live("person")
    subscription = blocking_ws_connection.subscribe_live(live_id)

    blocking_ws_connection_secondary.create("person", {"name": "first"})
    time.sleep(0.5)

    try:
        assert _next_within(subscription)["result"]["name"] == "first"
    finally:
        subscription.close()
        blocking_ws_connection_secondary.kill(live_id)


def test_blocking_subscription_ends_when_the_query_is_killed_elsewhere(
    blocking_ws_connection: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query("DEFINE TABLE OVERWRITE thing SCHEMALESS").execute()
    live_id = blocking_ws_connection.live("thing")

    received: list[dict[str, Any]] = []
    finished: list[bool] = []

    def consume() -> None:
        for notification in blocking_ws_connection.subscribe_live(live_id):
            received.append(notification)
        finished.append(True)

    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    time.sleep(0.4)

    blocking_ws_connection_secondary.create("thing", {"n": 1})
    time.sleep(0.5)
    blocking_ws_connection_secondary.kill(live_id)

    signals = _signals_a_killed_query(blocking_ws_connection.version())
    reader.join(timeout=_DEADLINE if signals else _NO_SIGNAL_GRACE)

    # Whatever the server does, the consumer must never be handed the
    # end-of-subscription marker as though it were a change to the table.
    assert [n["action"] for n in received] == ["CREATE"], (
        "the end-of-subscription marker was handed to the consumer as if it "
        "were a change"
    )
    assert all(n["result"] is not None for n in received)

    if signals:
        assert finished, "the generator never ended after the query was killed"
        assert not reader.is_alive()
    else:
        # 2.x says nothing when a query is killed elsewhere, so there is
        # nothing for the generator to end on. Pinned rather than skipped so
        # a server that starts signalling is visible here.
        assert not finished


async def test_async_subscription_ends_when_the_query_is_killed_elsewhere(
    async_ws_connection: AsyncWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    await async_ws_connection.query("DEFINE TABLE OVERWRITE thing SCHEMALESS").execute()
    live_id = await async_ws_connection.live("thing")
    subscription = await async_ws_connection.subscribe_live(live_id)

    received: list[dict[str, Any]] = []

    async def consume() -> None:
        async for notification in subscription:
            received.append(notification)

    consumer = asyncio.ensure_future(consume())
    await asyncio.sleep(0.4)

    blocking_ws_connection_secondary.create("thing", {"n": 1})
    await asyncio.sleep(0.5)
    blocking_ws_connection_secondary.kill(live_id)

    signals = _signals_a_killed_query(await async_ws_connection.version())
    if signals:
        await asyncio.wait_for(consumer, timeout=_DEADLINE)
    else:
        # See `_signals_a_killed_query`: nothing arrives to end it on 2.x.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(consumer), timeout=_NO_SIGNAL_GRACE)
        consumer.cancel()

    assert [n["action"] for n in received] == ["CREATE"]
    assert all(n["result"] is not None for n in received)


async def test_async_kill_on_the_same_connection_still_ends_cleanly(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """The path that already worked, so the new branch does not disturb it."""
    await async_ws_connection.query("DEFINE TABLE OVERWRITE thing SCHEMALESS").execute()
    live_id = await async_ws_connection.live("thing")
    subscription = await async_ws_connection.subscribe_live(live_id)

    async def consume() -> None:
        async for _ in subscription:
            pass

    consumer = asyncio.ensure_future(consume())
    await asyncio.sleep(0.2)

    await async_ws_connection.kill(live_id)

    # `kill()` here pushes the SDK's own sentinel, so this ends on every
    # server version - it does not depend on the server signalling anything.
    await asyncio.wait_for(consumer, timeout=_DEADLINE)


def test_a_live_query_still_delivers_several_notifications(
    blocking_ws_connection: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
) -> None:
    """Ending on KILLED must not end on anything else.

    Guards the obvious over-reach: a subscription that stops after the first
    notification would pass every test above.
    """
    blocking_ws_connection.query("DEFINE TABLE OVERWRITE thing SCHEMALESS").execute()
    live_id = blocking_ws_connection.live("thing")
    subscription = blocking_ws_connection.subscribe_live(live_id)

    try:
        for index in range(3):
            blocking_ws_connection_secondary.create("thing", {"n": index})

        actions = [_next_within(subscription)["action"] for _ in range(3)]
        assert actions == ["CREATE", "CREATE", "CREATE"]
    finally:
        subscription.close()
        blocking_ws_connection_secondary.kill(live_id)


@pytest.mark.parametrize("action", ["CREATE", "UPDATE", "DELETE"])
def test_real_notifications_are_not_mistaken_for_the_end(
    blocking_ws_connection: BlockingWsSurrealConnection,
    blocking_ws_connection_secondary: BlockingWsSurrealConnection,
    action: str,
) -> None:
    """Every action that is a genuine change still reaches the consumer."""
    # `DEFINE TABLE OVERWRITE` redefines the table but keeps its rows, so the
    # fixed record id below would collide with the previous parametrisation.
    blocking_ws_connection.query(
        "REMOVE TABLE IF EXISTS thing; DEFINE TABLE thing SCHEMALESS;"
    ).execute()
    blocking_ws_connection_secondary.create("thing:target", {"n": 0})

    live_id = blocking_ws_connection.live("thing")
    subscription = blocking_ws_connection.subscribe_live(live_id)

    try:
        if action == "CREATE":
            blocking_ws_connection_secondary.create("thing:fresh", {"n": 1})
        elif action == "UPDATE":
            blocking_ws_connection_secondary.update("thing:target", {"n": 2})
        else:
            blocking_ws_connection_secondary.delete("thing:target")

        notification = _next_within(subscription)
        assert notification["action"] == action
    finally:
        subscription.close()
        blocking_ws_connection_secondary.kill(live_id)
