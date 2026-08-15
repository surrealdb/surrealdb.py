"""Every transport failure surfaces as a ``SurrealError`` (issue #298).

Non-2xx ``/rpc`` responses, unreachable hosts, timeouts and undecodable
bodies used to escape as ``requests``/``aiohttp``/``websockets`` exceptions,
so ``except SurrealError`` did not actually cover server failures.

These need no live SurrealDB server: the blocking HTTP transport is stubbed
with ``responses``, the async HTTP transport is pointed at a throwaway local
``aiohttp`` server (see :func:`_running_server`), and the websocket transports
are pointed at a closed port.
"""

import asyncio
import socket
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
import pytest
import requests
import responses
from aiohttp import web
from aiohttp.test_utils import TestServer

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.cbor import encode
from surrealdb.errors import (
    ConnectionUnavailableError,
    HttpStatusError,
    NotAllowedError,
    SurrealError,
    TransportError,
    TransportTimeoutError,
    UnexpectedResponseError,
)

URL = "http://localhost:8000"
RPC = f"{URL}/rpc"


def _closed_port() -> int:
    """Return a port with nothing listening on it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


@asynccontextmanager
async def _running_server(handler: Handler) -> AsyncIterator[str]:
    """Serve *handler* on an ephemeral local port, yielding its base URL.

    The async HTTP transport is driven purely by URL, so pointing a connection
    at this server exercises the real ``aiohttp`` request path - headers,
    status codes, body decoding and connection failures all behave exactly as
    they do against a live server. A handler can return anything at all
    (arbitrary statuses, undecodable bodies, or nothing until released), which
    is what makes it a drop-in for transport-level mocking.

    The route is pinned to ``POST /rpc`` rather than registered as a catch-all:
    that is the only request the transport should ever make, and pinning it
    keeps the implicit assertion the previous mock enforced by refusing to
    match anything else. A transport that changed method or path would fall
    through to aiohttp's 404 and fail these tests, instead of being silently
    answered.
    """
    app = web.Application()
    app.router.add_route("POST", "/rpc", handler)
    server = TestServer(app)
    await server.start_server()
    try:
        yield str(server.make_url(""))
    finally:
        await server.close()


@pytest.fixture
def short_http_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the client timeout the async HTTP transport asks ``aiohttp`` for.

    ``AsyncHttpSurrealConnection`` hard-codes ``ClientTimeout(total=30)``, so a
    genuinely unresponsive server would stall the timeout test for half a
    minute. Patching the ``aiohttp.ClientTimeout`` the SDK looks up (aiohttp's
    own internals use their module-local name, so they are unaffected) keeps
    the real timeout machinery in play while making it fire promptly.
    """
    client_timeout = aiohttp.ClientTimeout

    def _short_timeout(*args: Any, **kwargs: Any) -> aiohttp.ClientTimeout:
        kwargs["total"] = 0.25
        return client_timeout(*args, **kwargs)

    monkeypatch.setattr(aiohttp, "ClientTimeout", _short_timeout)


# ------------------------------------------------------------------ #
#  Hierarchy                                                           #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "error_class",
    [ConnectionUnavailableError, TransportTimeoutError, HttpStatusError],
)
def test_transport_errors_are_surreal_errors(
    error_class: type[TransportError],
) -> None:
    assert issubclass(error_class, TransportError)
    assert issubclass(error_class, SurrealError)


# ------------------------------------------------------------------ #
#  Blocking HTTP                                                       #
# ------------------------------------------------------------------ #


@responses.activate
def test_blocking_http_non_2xx_raises_http_status_error() -> None:
    """A 401 with a plain-text body reports the status, not ``HTTPError``."""
    responses.add(responses.POST, RPC, body=b"InvalidToken", status=401)

    connection = BlockingHttpSurrealConnection(URL)
    connection.token = "not-a-valid-bearer-token"

    with pytest.raises(HttpStatusError) as exc_info:
        connection.version()

    error = exc_info.value
    assert isinstance(error, SurrealError)
    assert error.status == 401
    assert error.body == "InvalidToken"
    assert error.url == RPC


@responses.activate
def test_blocking_http_non_2xx_json_body_is_preserved() -> None:
    """The JSON envelope a 400 carries is kept on the error for triage."""
    body = b'{"code":400,"information":"Parse error"}'
    responses.add(responses.POST, RPC, body=body, status=400)

    connection = BlockingHttpSurrealConnection(URL)

    with pytest.raises(HttpStatusError) as exc_info:
        connection.version()

    assert exc_info.value.status == 400
    assert "Parse error" in exc_info.value.body


@responses.activate
def test_blocking_http_non_2xx_with_rpc_body_keeps_server_error() -> None:
    """A structured RPC error still maps to its ``ServerError`` subclass."""
    body = encode(
        {
            "id": "1",
            "error": {
                "kind": "NotAllowed",
                "code": -32002,
                "message": "There was a problem with authentication",
            },
        }
    )
    responses.add(responses.POST, RPC, body=body, status=403)

    connection = BlockingHttpSurrealConnection(URL)

    with pytest.raises(NotAllowedError) as exc_info:
        connection.version()

    assert exc_info.value.kind == "NotAllowed"


@responses.activate
def test_blocking_http_unreachable_host_raises_connection_unavailable() -> None:
    responses.add(
        responses.POST, RPC, body=requests.exceptions.ConnectionError("refused")
    )

    connection = BlockingHttpSurrealConnection(URL)

    with pytest.raises(ConnectionUnavailableError):
        connection.version()


@responses.activate
def test_blocking_http_timeout_raises_transport_timeout() -> None:
    responses.add(responses.POST, RPC, body=requests.exceptions.ReadTimeout("slow"))

    connection = BlockingHttpSurrealConnection(URL)

    with pytest.raises(TransportTimeoutError):
        connection.version()


@responses.activate
def test_blocking_http_undecodable_2xx_body_raises_unexpected_response() -> None:
    """A 200 the SDK cannot decode is an SDK error, not a CBOR error."""
    responses.add(responses.POST, RPC, body=b'{"not":"cbor"}', status=200)

    connection = BlockingHttpSurrealConnection(URL)

    with pytest.raises(UnexpectedResponseError):
        connection.version()


@responses.activate
def test_blocking_http_success_is_unaffected() -> None:
    responses.add(
        responses.POST, RPC, body=encode({"id": "1", "result": "3.2.3"}), status=200
    )

    connection = BlockingHttpSurrealConnection(URL)

    assert connection.version() == "3.2.3"


# ------------------------------------------------------------------ #
#  Async HTTP                                                          #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_async_http_non_2xx_raises_http_status_error() -> None:
    """A 401 with a plain-text body reports the status, not ``ClientError``."""

    async def handler(request: web.Request) -> web.StreamResponse:
        return web.Response(status=401, body=b"InvalidToken")

    async with _running_server(handler) as base_url:
        connection = AsyncHttpSurrealConnection(base_url)
        connection.token = "not-a-valid-bearer-token"

        with pytest.raises(HttpStatusError) as exc_info:
            await connection.version()

    error = exc_info.value
    assert isinstance(error, SurrealError)
    assert error.status == 401
    assert error.body == "InvalidToken"
    assert error.url == f"{base_url}/rpc"


@pytest.mark.asyncio
async def test_async_http_non_2xx_with_rpc_body_keeps_server_error() -> None:
    """A structured RPC error still maps to its ``ServerError`` subclass."""
    body = encode(
        {
            "id": "1",
            "error": {
                "kind": "NotAllowed",
                "code": -32002,
                "message": "There was a problem with authentication",
            },
        }
    )

    async def handler(request: web.Request) -> web.StreamResponse:
        return web.Response(status=403, body=body, content_type="application/cbor")

    async with _running_server(handler) as base_url:
        connection = AsyncHttpSurrealConnection(base_url)

        with pytest.raises(NotAllowedError) as exc_info:
            await connection.version()

    assert exc_info.value.kind == "NotAllowed"


@pytest.mark.asyncio
async def test_async_http_unreachable_host_raises_connection_unavailable() -> None:
    """Nothing listening on the port: the refusal maps to a transport error."""
    connection = AsyncHttpSurrealConnection(f"http://127.0.0.1:{_closed_port()}")

    with pytest.raises(ConnectionUnavailableError) as exc_info:
        await connection.version()

    assert isinstance(exc_info.value.__cause__, aiohttp.ClientError)


@pytest.mark.asyncio
async def test_async_http_timeout_raises_transport_timeout(
    short_http_timeout: None,
) -> None:
    """A server that never answers within the client timeout is a timeout."""
    release = asyncio.Event()

    async def handler(request: web.Request) -> web.StreamResponse:
        # Hold the request open past the (shortened) client timeout, then let
        # go so the server can shut down without waiting on a stuck handler.
        await release.wait()
        return web.Response(status=200, body=b"")

    async with _running_server(handler) as base_url:
        connection = AsyncHttpSurrealConnection(base_url)

        try:
            with pytest.raises(TransportTimeoutError) as exc_info:
                await connection.version()
        finally:
            release.set()

    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_async_http_undecodable_2xx_body_raises_unexpected_response() -> None:
    """A 200 the SDK cannot decode is an SDK error, not a CBOR error."""

    async def handler(request: web.Request) -> web.StreamResponse:
        return web.Response(status=200, body=b'{"not":"cbor"}')

    async with _running_server(handler) as base_url:
        connection = AsyncHttpSurrealConnection(base_url)

        with pytest.raises(UnexpectedResponseError):
            await connection.version()


# ------------------------------------------------------------------ #
#  WebSocket                                                           #
# ------------------------------------------------------------------ #


def test_blocking_ws_unreachable_host_raises_connection_unavailable() -> None:
    connection = BlockingWsSurrealConnection(f"ws://127.0.0.1:{_closed_port()}")

    with pytest.raises(ConnectionUnavailableError):
        connection.version()


def test_blocking_ws_context_manager_unreachable_host_raises() -> None:
    connection = BlockingWsSurrealConnection(f"ws://127.0.0.1:{_closed_port()}")

    with pytest.raises(ConnectionUnavailableError), connection:
        pass


@pytest.mark.asyncio
async def test_async_ws_unreachable_host_raises_connection_unavailable() -> None:
    connection = AsyncWsSurrealConnection(f"ws://127.0.0.1:{_closed_port()}")

    with pytest.raises(ConnectionUnavailableError):
        await connection.connect()
