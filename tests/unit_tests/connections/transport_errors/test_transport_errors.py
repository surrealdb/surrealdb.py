"""Every transport failure surfaces as a ``SurrealError`` (issue #298).

Non-2xx ``/rpc`` responses, unreachable hosts, timeouts and undecodable
bodies used to escape as ``requests``/``aiohttp``/``websockets`` exceptions,
so ``except SurrealError`` did not actually cover server failures.

These are fully mocked and need no live server.
"""

import asyncio
import socket

import aiohttp
import pytest
import requests
import responses
from aioresponses import aioresponses

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
    connection = AsyncHttpSurrealConnection(URL)
    connection.token = "not-a-valid-bearer-token"

    with aioresponses() as mocked:
        mocked.post(RPC, status=401, body=b"InvalidToken")

        with pytest.raises(HttpStatusError) as exc_info:
            await connection.version()

    error = exc_info.value
    assert isinstance(error, SurrealError)
    assert error.status == 401
    assert error.body == "InvalidToken"


@pytest.mark.asyncio
async def test_async_http_non_2xx_with_rpc_body_keeps_server_error() -> None:
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
    connection = AsyncHttpSurrealConnection(URL)

    with aioresponses() as mocked:
        mocked.post(RPC, status=403, body=body)

        with pytest.raises(NotAllowedError):
            await connection.version()


@pytest.mark.asyncio
async def test_async_http_unreachable_host_raises_connection_unavailable() -> None:
    connection = AsyncHttpSurrealConnection(URL)

    with aioresponses() as mocked:
        mocked.post(RPC, exception=aiohttp.ClientConnectionError("refused"))

        with pytest.raises(ConnectionUnavailableError):
            await connection.version()


@pytest.mark.asyncio
async def test_async_http_timeout_raises_transport_timeout() -> None:
    connection = AsyncHttpSurrealConnection(URL)

    with aioresponses() as mocked:
        mocked.post(RPC, exception=asyncio.TimeoutError())

        with pytest.raises(TransportTimeoutError):
            await connection.version()


@pytest.mark.asyncio
async def test_async_http_undecodable_2xx_body_raises_unexpected_response() -> None:
    connection = AsyncHttpSurrealConnection(URL)

    with aioresponses() as mocked:
        mocked.post(RPC, status=200, body=b'{"not":"cbor"}')

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

    with pytest.raises(ConnectionUnavailableError):
        with connection:
            pass


@pytest.mark.asyncio
async def test_async_ws_unreachable_host_raises_connection_unavailable() -> None:
    connection = AsyncWsSurrealConnection(f"ws://127.0.0.1:{_closed_port()}")

    with pytest.raises(ConnectionUnavailableError):
        await connection.connect()
