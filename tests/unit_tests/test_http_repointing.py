"""``connect(url)`` on an HTTP connection starts afresh with the new server."""

from collections.abc import Iterator

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from tests.unit_tests.fake_surreal import FakeSurrealHttp


@pytest.fixture
def http() -> Iterator[FakeSurrealHttp]:
    server = FakeSurrealHttp()
    try:
        yield server
    finally:
        server.close()


def test_blocking_repointing_starts_again_in_plain_cbor(http: FakeSurrealHttp) -> None:
    """A connection that talked `cbor.2` to a 4.x server would otherwise send
    the next server's version request in it, whatever that server reads."""
    db = BlockingHttpSurrealConnection(http.url)
    db._v2 = True
    db.connect(http.url)
    assert [call.content_type for call in http.calls] == ["application/cbor"]


async def test_async_repointing_starts_again_in_plain_cbor(
    http: FakeSurrealHttp,
) -> None:
    db = AsyncHttpSurrealConnection(http.url)
    db._v2 = True
    await db.connect(http.url)
    assert [call.content_type for call in http.calls] == ["application/cbor"]
