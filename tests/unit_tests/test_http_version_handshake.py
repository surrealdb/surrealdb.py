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
from tests.unit_tests.fake_surreal import Call, FakeSurrealHttp, jwt


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


def _refuse_anonymous(call: Call) -> int | None:
    return 401 if call.token is None else None


def test_blocking_a_proxy_refusing_the_anonymous_version_request_is_not_a_lockout(
    http: FakeSurrealHttp,
) -> None:
    """The version request goes out without a token, which an auth proxy
    refuses in plain text; the requests that carry one must still get through."""
    http.proxy = _refuse_anonymous
    db = BlockingHttpSurrealConnection(http.url)
    db.token = jwt()

    db.query("RETURN 1").execute()
    db.query("RETURN 1").execute()

    assert http.methods() == ["version", "query", "query"]


async def test_async_a_proxy_refusing_the_anonymous_version_request_is_not_a_lockout(
    http: FakeSurrealHttp,
) -> None:
    http.proxy = _refuse_anonymous
    db = AsyncHttpSurrealConnection(http.url)
    db.token = jwt()

    await db.query("RETURN 1")
    await db.query("RETURN 1")

    assert http.methods() == ["version", "query", "query"]


def test_blocking_a_server_error_on_the_version_request_is_asked_again(
    http: FakeSurrealHttp,
) -> None:
    http.proxy = lambda call: 503 if call.method == "version" else None
    db = BlockingHttpSurrealConnection(http.url)

    db.query("RETURN 1").execute()
    http.proxy = lambda call: None
    db.query("RETURN 1").execute()
    db.query("RETURN 1").execute()

    assert http.methods() == ["version", "query", "version", "query", "query"]
    assert db.version() == "surrealdb-3.0.0"
