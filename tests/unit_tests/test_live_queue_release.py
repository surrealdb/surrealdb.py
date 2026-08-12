"""A subscription that is never iterated releases its queue.

``subscribe_live`` registers the consumer's queue eagerly, before anything is
iterated - it has to, because a notification arriving between ``live()`` and the
first ``next()`` would otherwise find no queue and be dropped.

Deregistration lived in the generator's ``finally``, which a generator that was
never started does not run, on ``close()`` or on garbage collection. So a
subscription set up and then abandoned - on an early error, behind a conditional
consumer, in a retry loop that re-subscribes - stayed registered for the life of
the connection, and every notification for that live id kept being routed into a
queue nobody would ever drain.

Server-free: registration and release are bookkeeping on the connection object,
and the generator is deliberately never started, so no socket is ever opened.
"""

import asyncio
import gc
import uuid

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

WS_URL = "ws://localhost:8000"
LIVE_ID = str(uuid.UUID(int=1))


def test_blocking_registers_before_anything_is_iterated() -> None:
    """The property the eager registration exists for."""
    connection = BlockingWsSurrealConnection(WS_URL)

    subscription = connection.subscribe_live(LIVE_ID)

    assert len(connection.live_queues[LIVE_ID]) == 1, (
        "the queue is registered only once the consumer iterates, so a "
        "notification arriving before that is dropped"
    )
    subscription.close()


def test_blocking_releases_a_subscription_that_was_never_iterated() -> None:
    connection = BlockingWsSurrealConnection(WS_URL)
    subscription = connection.subscribe_live(LIVE_ID)
    assert len(connection.live_queues[LIVE_ID]) == 1

    del subscription
    gc.collect()

    assert not connection.live_queues.get(LIVE_ID), (
        "the queue outlived the subscription; notifications will accumulate in "
        "it for the life of the connection"
    )


def test_blocking_releases_on_close_without_iterating() -> None:
    """``close()`` on a never-started generator also has to release."""
    connection = BlockingWsSurrealConnection(WS_URL)
    subscription = connection.subscribe_live(LIVE_ID)

    subscription.close()
    del subscription
    gc.collect()

    assert not connection.live_queues.get(LIVE_ID)


def test_blocking_releases_only_its_own_queue() -> None:
    """Two subscribers on one query: dropping one must not unregister the other."""
    connection = BlockingWsSurrealConnection(WS_URL)
    first = connection.subscribe_live(LIVE_ID)
    second = connection.subscribe_live(LIVE_ID)
    assert len(connection.live_queues[LIVE_ID]) == 2

    del first
    gc.collect()

    assert len(connection.live_queues[LIVE_ID]) == 1
    second.close()


def test_the_finalizer_adds_no_reference_of_its_own() -> None:
    """Dropping both the subscription and the connection collects both.

    The generator itself holds the connection - it comes from a bound method,
    and it needs the connection to read from - so a live subscription keeping
    one alive is correct. What must not happen is the *finalizer* adding a
    reference beyond that, which a bound-method callback would: the connection
    would then outlive both, kept alive by its own cleanup.
    """
    import weakref

    connection = BlockingWsSurrealConnection(WS_URL)
    subscription = connection.subscribe_live(LIVE_ID)
    ref = weakref.ref(connection)

    del subscription
    del connection
    gc.collect()

    assert ref() is None, "the connection outlived both references to it"


async def test_async_releases_a_subscription_that_was_never_iterated() -> None:
    connection = AsyncWsSurrealConnection(WS_URL)
    subscription = await connection.subscribe_live(LIVE_ID)
    assert len(connection.live_queues[LIVE_ID]) == 1

    del subscription
    gc.collect()
    # An un-started async generator schedules its close on the loop.
    await asyncio.sleep(0)
    gc.collect()

    assert not connection.live_queues.get(LIVE_ID)


async def test_async_registers_before_anything_is_iterated() -> None:
    connection = AsyncWsSurrealConnection(WS_URL)

    subscription = await connection.subscribe_live(LIVE_ID)

    assert len(connection.live_queues[LIVE_ID]) == 1
    await subscription.aclose()


def test_kill_wakes_its_own_subscribers_locally() -> None:
    """``kill()`` ends the caller's own subscription without the server's help.

    3.x announces a kill with a ``KILLED`` notification, so waiting for the
    server worked there. 2.x sends nothing at all, and the caller's own
    subscription - on the very query it had just killed itself - blocked
    forever. The sentinel is pushed locally so this holds on every version,
    which is what the async transport has always done.

    Asserted on the queue rather than through a server, so it is the local
    mechanism being tested and not 3.x's notification masking its absence.
    """
    from surrealdb.connections import blocking_ws

    connection = BlockingWsSurrealConnection(WS_URL)
    # Held deliberately: dropping it would release the queue, which is what the
    # tests above are for.
    subscription = connection.subscribe_live(LIVE_ID)
    queue = connection.live_queues[LIVE_ID][0]
    assert queue.empty()

    # `kill()` sends an RPC; stub it out so no socket is needed.
    connection._send = lambda *args, **kwargs: {"result": None}  # type: ignore[method-assign]
    connection.kill(LIVE_ID)

    assert not queue.empty(), "kill() left its own subscriber waiting"
    assert queue.get_nowait()["action"] == blocking_ws._LIVE_KILLED
    subscription.close()
