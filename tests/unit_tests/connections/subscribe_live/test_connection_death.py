"""A live subscription ends when the connection under it dies.

``_recv_task`` failed every pending RPC future when it stopped, but live
subscribers do not wait on futures - they wait on a queue, and nothing was ever
put in theirs again. ``async for`` simply never came back, with no timeout
anywhere on the path, so a program whose server restarted sat there for as long
as anyone let it.

It raises rather than returning quietly. A silent ``return`` is what
:meth:`kill` and :meth:`close` produce, and a consumer that cannot tell those
apart from a dropped connection goes on believing it has seen every change to
the table. The blocking transport has always raised here; this is the async
side catching up.
"""

import asyncio
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.errors import ConnectionUnavailableError

# Long enough to be certain a hang is a hang, short enough that a broken
# implementation does not stall the suite for a minute.
_DEADLINE = 15.0


async def test_async_subscriber_is_woken_when_the_socket_dies(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )

    query_uuid = await connection.live("user")
    subscription = await connection.subscribe_live(query_uuid)

    async def drain() -> None:
        async for _ in subscription:
            pass

    consumer = asyncio.ensure_future(drain())
    await asyncio.sleep(0.2)

    # The peer goes away underneath us. Deliberately not `connection.close()`:
    # that is the orderly path, and it already woke subscribers.
    await connection.socket.close()

    with pytest.raises(ConnectionUnavailableError):
        await asyncio.wait_for(consumer, timeout=_DEADLINE)

    await connection.close()


async def test_close_still_ends_the_subscription_quietly(
    connection_params: dict[str, Any],
) -> None:
    """The orderly path must not start raising now that the broken one does.

    ``close()`` wakes subscribers before it cancels the reader, and a queue is
    FIFO, so the clean sentinel is always the one a consumer sees first.
    """
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )

    query_uuid = await connection.live("user")
    subscription = await connection.subscribe_live(query_uuid)

    async def drain() -> None:
        async for _ in subscription:
            pass

    consumer = asyncio.ensure_future(drain())
    await asyncio.sleep(0.2)

    await connection.close()

    # No exception: a deliberate close is a clean end of stream.
    await asyncio.wait_for(consumer, timeout=_DEADLINE)


async def test_kill_still_ends_the_subscription_quietly(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )

    query_uuid = await connection.live("user")
    subscription = await connection.subscribe_live(query_uuid)

    async def drain() -> None:
        async for _ in subscription:
            pass

    consumer = asyncio.ensure_future(drain())
    await asyncio.sleep(0.2)

    await connection.kill(query_uuid)

    await asyncio.wait_for(consumer, timeout=_DEADLINE)
    await connection.close()
