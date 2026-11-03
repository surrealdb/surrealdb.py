"""How an HTTP connection asks a server for its version and wire format.

Once per server: when the first requests race each other, and again when
``connect(url)`` points the connection at another server.
"""

import asyncio
import threading
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


def test_blocking_concurrent_first_requests_ask_the_version_once(
    http: FakeSurrealHttp,
) -> None:
    db = BlockingHttpSurrealConnection(http.url)
    threads = [
        threading.Thread(target=lambda: db.query("RETURN 1").execute())
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert http.methods().count("version") == 1
    assert http.methods().count("query") == 8


async def test_async_concurrent_first_requests_ask_the_version_once(
    http: FakeSurrealHttp,
) -> None:
    db = AsyncHttpSurrealConnection(http.url)
    await asyncio.gather(*(db.query("RETURN 1") for _ in range(8)))
    assert http.methods().count("version") == 1
    assert http.methods().count("query") == 8
