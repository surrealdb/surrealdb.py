import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.errors import UnsupportedFeatureError


# The URLs below are never connected to: each of these methods raises before it
# would reach the network, which is the whole point of the test. They are not
# taken from `connection_params` because there is nothing to reach.
def test_async_http_attach_raises() -> None:
    conn = AsyncHttpSurrealConnection("http://localhost:8000")

    async def _run() -> None:
        with pytest.raises(
            UnsupportedFeatureError,
            match="Multi-session and client-side transactions are only supported for WebSocket connections",
        ):
            await conn.attach()

    import asyncio

    asyncio.run(_run())


def test_async_http_new_session_raises() -> None:
    conn = AsyncHttpSurrealConnection("http://localhost:8000")

    async def _run() -> None:
        with pytest.raises(
            UnsupportedFeatureError,
            match="Multi-session and client-side transactions are only supported for WebSocket connections",
        ):
            await conn.new_session()

    import asyncio

    asyncio.run(_run())


def test_blocking_http_attach_raises() -> None:
    conn = BlockingHttpSurrealConnection("http://localhost:8000")
    with pytest.raises(
        UnsupportedFeatureError,
        match="Multi-session and client-side transactions are only supported for WebSocket connections",
    ):
        conn.attach()


def test_blocking_http_new_session_raises() -> None:
    conn = BlockingHttpSurrealConnection("http://localhost:8000")
    with pytest.raises(
        UnsupportedFeatureError,
        match="Multi-session and client-side transactions are only supported for WebSocket connections",
    ):
        conn.new_session()
