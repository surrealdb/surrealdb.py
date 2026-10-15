"""Token and session methods on the embedded engine go to the engine.

The blocking embedded connection inherits ``refresh``, ``revoke`` and
``reset`` from the blocking websocket, whose readiness check opened a socket to
the ``memory`` URL. ``health()`` asks an HTTP endpoint the engine does not have.
"""

import pytest

from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.errors import UnsupportedFeatureError


def test_blocking_refresh_reaches_the_engine() -> None:
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.connect()
    try:
        with pytest.raises(ValueError, match="refresh token"):
            connection.refresh()
    finally:
        connection.close()


def test_blocking_health_is_refused() -> None:
    connection = BlockingEmbeddedSurrealConnection("memory")
    with pytest.raises(UnsupportedFeatureError, match="health"):
        connection.health()


async def test_async_health_is_refused() -> None:
    connection = AsyncEmbeddedSurrealConnection("memory")
    with pytest.raises(UnsupportedFeatureError, match="health"):
        await connection.health()
