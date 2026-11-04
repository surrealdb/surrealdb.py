from collections.abc import Iterator

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


@pytest.fixture
def no_version_handshake(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Skip the version request a connection sends when it opens.

    For tests driven through fake sockets or mocked HTTP endpoints, which
    script the exact requests they expect and are not about the handshake.
    The connection records the version as unknown, which gates nothing.
    """

    def _sync(
        self: BlockingWsSurrealConnection | BlockingHttpSurrealConnection,
    ) -> None:
        self._adopt_server_version(None)

    async def _async(
        self: AsyncWsSurrealConnection | AsyncHttpSurrealConnection,
    ) -> None:
        self._adopt_server_version(None)

    monkeypatch.setattr(BlockingWsSurrealConnection, "_handshake_locked", _sync)
    monkeypatch.setattr(BlockingHttpSurrealConnection, "_handshake", _sync)
    monkeypatch.setattr(AsyncWsSurrealConnection, "_handshake", _async)
    monkeypatch.setattr(AsyncHttpSurrealConnection, "_handshake", _async)
    yield
