"""The embedded engine has no live queries, and says so.

The Rust extension reports ``LQ_SUPPORT = false``, so there is no channel for
notifications to arrive on. ``live()`` and ``kill()`` reached the engine and
came back as "Unable to perform the realtime query", which does not say why;
``subscribe_live()`` raised a bare ``AttributeError`` on ``live_queues``,
because the embedded constructors set a hand-copied subset of the attributes
their parents do and that one was not in it.
"""

import pytest

from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import SurrealError, UnsupportedFeatureError

LIVE_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def blocking_embedded() -> BlockingEmbeddedSurrealConnection:
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.connect()
    connection.use("test_ns", "test_db")
    return connection


@pytest.fixture
async def async_embedded() -> AsyncEmbeddedSurrealConnection:
    connection = AsyncEmbeddedSurrealConnection("memory")
    await connection.connect()
    await connection.use("test_ns", "test_db")
    return connection


def test_blocking_live_is_refused(
    blocking_embedded: BlockingEmbeddedSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        blocking_embedded.live("person")


def test_blocking_kill_is_refused(
    blocking_embedded: BlockingEmbeddedSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        blocking_embedded.kill(LIVE_ID)


def test_blocking_subscribe_live_is_refused(
    blocking_embedded: BlockingEmbeddedSurrealConnection,
) -> None:
    # The refusal lands on the call, not on the first `next()`, so the error
    # points at the line that made the mistake.
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        blocking_embedded.subscribe_live(LIVE_ID)


async def test_async_live_is_refused(
    async_embedded: AsyncEmbeddedSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        await async_embedded.live("person")


async def test_async_kill_is_refused(
    async_embedded: AsyncEmbeddedSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        await async_embedded.kill(LIVE_ID)


async def test_async_subscribe_live_is_refused(
    async_embedded: AsyncEmbeddedSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket"):
        await async_embedded.subscribe_live(LIVE_ID)


def test_refusal_is_a_surreal_error(
    blocking_embedded: BlockingEmbeddedSurrealConnection,
) -> None:
    """``except SurrealError`` covers it; ``AttributeError`` never did."""
    with pytest.raises(SurrealError):
        blocking_embedded.subscribe_live(LIVE_ID)


# --------------------------------------------------------------- root cause


def test_blocking_embedded_has_every_attribute_its_parent_sets() -> None:
    """The subclass constructor must not drop state the inherited methods use.

    Both embedded constructors used to hand-copy a subset of their parent's
    attributes, which is how ``live_queues`` went missing. They now run the
    parent constructor - it opens nothing, it only sets attributes - and this
    catches any future divergence.
    """
    parent = BlockingWsSurrealConnection("ws://localhost:8000")
    embedded = BlockingEmbeddedSurrealConnection("memory")

    missing = set(vars(parent)) - set(vars(embedded))

    assert not missing, f"embedded connection is missing {sorted(missing)}"


def test_async_embedded_has_every_attribute_its_parent_sets() -> None:
    parent = AsyncWsSurrealConnection("ws://localhost:8000")
    embedded = AsyncEmbeddedSurrealConnection("memory")

    missing = set(vars(parent)) - set(vars(embedded))

    assert not missing, f"embedded connection is missing {sorted(missing)}"
