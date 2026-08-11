"""HTTP connections refuse live queries with a ``SurrealError``.

Live queries need a persistent connection to push notifications down, so the
README documents them as WebSocket-only. The HTTP connections inherited the
templates' ``NotImplementedError`` instead of refusing them the way they refuse
sessions and transactions - and ``NotImplementedError`` is not a
``SurrealError``, so the single ``except SurrealError`` the README promises
covers every SDK failure did not catch it, while ``attach()`` on the very same
object was covered.

No server needed: the refusal happens before anything is sent.
"""

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.errors import SurrealError, UnsupportedFeatureError

HTTP_URL = "http://localhost:8000"
LIVE_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def blocking_http() -> BlockingHttpSurrealConnection:
    return BlockingHttpSurrealConnection(HTTP_URL)


@pytest.fixture
def async_http() -> AsyncHttpSurrealConnection:
    return AsyncHttpSurrealConnection(HTTP_URL)


def test_blocking_live_is_refused(
    blocking_http: BlockingHttpSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        blocking_http.live("person")


def test_blocking_kill_is_refused(
    blocking_http: BlockingHttpSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        blocking_http.kill(LIVE_ID)


def test_blocking_subscribe_live_is_refused(
    blocking_http: BlockingHttpSurrealConnection,
) -> None:
    # The refusal lands on the call, not on the first `next()`, so the error
    # points at the line that made the mistake.
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        blocking_http.subscribe_live(LIVE_ID)


async def test_async_live_is_refused(async_http: AsyncHttpSurrealConnection) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        await async_http.live("person")


async def test_async_kill_is_refused(async_http: AsyncHttpSurrealConnection) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        await async_http.kill(LIVE_ID)


async def test_async_subscribe_live_is_refused(
    async_http: AsyncHttpSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        await async_http.subscribe_live(LIVE_ID)


@pytest.mark.parametrize("method", ["live", "kill", "subscribe_live"])
def test_refusal_is_a_surreal_error(
    blocking_http: BlockingHttpSurrealConnection, method: str
) -> None:
    """``except SurrealError`` covers it; ``NotImplementedError`` never did."""
    with pytest.raises(SurrealError):
        getattr(blocking_http, method)(LIVE_ID)
