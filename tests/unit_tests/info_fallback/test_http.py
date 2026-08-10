"""Mocked regression tests for the ``info()`` record-auth ``$auth`` fallback
over the HTTP transports (finding #23, finding #8-fragile-match).

These tests do not need a running SurrealDB server. The blocking transport's
RPC endpoint is mocked with ``responses``; the async transport is pointed at a
real, throwaway ``aiohttp`` server bound to an ephemeral port on 127.0.0.1 that
answers the RPC calls itself (``aioresponses`` cannot construct aiohttp >=
3.14's ``ClientResponse``, so aiohttp's own ``TestServer`` plays the server
instead). Either way the bodies are real CBOR payloads, so the full
encode/decode + fallback path is exercised end to end.
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any

import pytest
import responses
from aiohttp import web
from aiohttp.test_utils import TestServer

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.cbor import decode, encode
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import NotAllowedError, ServerError
from surrealdb.types import Value

RPC_URL = "http://localhost:8000/rpc"

# A representative record-auth sign-in payload; the mocked server ignores it.
RECORD_SIGNIN: dict[str, Value] = {
    "namespace": "test_ns",
    "database": "test_db",
    "access": "user",
    "variables": {"email": "tobie@example.com", "password": "password123"},
}


def _auth_record() -> dict[str, Any]:
    return {
        "id": RecordID("user", "tobie"),
        "name": "Tobie",
        "email": "tobie@example.com",
    }


def _cbor(payload: dict[str, Any]) -> bytes:
    return encode(payload)


def _signin_ok() -> bytes:
    return _cbor({"id": "signin", "result": "a.jwt.token"})


def _info_error(error: dict[str, Any]) -> bytes:
    return _cbor({"id": "info", "error": error})


def _auth_query_result(records: list[dict[str, Any]]) -> bytes:
    return _cbor(
        {"id": "query", "result": [{"status": "OK", "result": records, "time": "1ms"}]}
    )


# Both the legacy ``-32000`` "no result found" code and the structured
# ``NotFound`` kind must trigger the fallback.
_NOT_FOUND_ERRORS = [
    pytest.param(
        {"code": -32000, "message": "No result found"}, id="legacy-code-32000"
    ),
    pytest.param(
        {"code": 0, "kind": "NotFound", "message": "There was no result"},
        id="structured-notfound-kind",
    ),
]


# --------------------------------------------------------------------------- #
# Blocking HTTP
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("error", _NOT_FOUND_ERRORS)
@responses.activate
def test_blocking_http_info_uses_auth_fallback(error: dict[str, Any]) -> None:
    record = _auth_record()
    responses.add(responses.POST, RPC_URL, body=_signin_ok(), status=200)
    responses.add(responses.POST, RPC_URL, body=_info_error(error), status=200)
    responses.add(
        responses.POST, RPC_URL, body=_auth_query_result([record]), status=200
    )

    db = BlockingHttpSurrealConnection("http://localhost:8000")
    db.signin(RECORD_SIGNIN)
    outcome = db.info()

    assert outcome == record
    assert outcome["id"] == RecordID("user", "tobie")
    # signin + info + $auth query
    assert len(responses.calls) == 3


@responses.activate
def test_blocking_http_info_non_not_found_error_raises() -> None:
    """A non not-found error must be raised, not silently swallowed, and must
    not trigger a second ``$auth`` query."""
    responses.add(responses.POST, RPC_URL, body=_signin_ok(), status=200)
    responses.add(
        responses.POST,
        RPC_URL,
        body=_info_error({"code": -32602, "message": "Not allowed"}),
        status=200,
    )

    db = BlockingHttpSurrealConnection("http://localhost:8000")
    db.signin(RECORD_SIGNIN)
    with pytest.raises(NotAllowedError):
        db.info()

    # Only signin + info: the fallback query must NOT have fired.
    assert len(responses.calls) == 2


@responses.activate
def test_blocking_http_info_empty_auth_reraises() -> None:
    """When ``$auth`` resolves to nothing, the original info error is raised."""
    responses.add(responses.POST, RPC_URL, body=_signin_ok(), status=200)
    responses.add(
        responses.POST,
        RPC_URL,
        body=_info_error({"code": -32000, "message": "No result found"}),
        status=200,
    )
    responses.add(responses.POST, RPC_URL, body=_auth_query_result([]), status=200)

    db = BlockingHttpSurrealConnection("http://localhost:8000")
    db.signin(RECORD_SIGNIN)
    with pytest.raises(ServerError):
        db.info()

    assert len(responses.calls) == 3


# --------------------------------------------------------------------------- #
# Async HTTP
# --------------------------------------------------------------------------- #

Responder = Callable[[dict[str, Any]], bytes]


def _make_responder(
    info_error: dict[str, Any],
    auth_records: list[dict[str, Any]],
) -> Responder:
    """Build a responder that answers signin/info/query RPCs with CBOR bodies.

    A single ``info()`` call spans several requests to the same endpoint
    (signin, then info, then the ``$auth`` fallback query), so the reply is
    keyed on the RPC ``method`` rather than on the arrival order.
    """

    def _responder(request: dict[str, Any]) -> bytes:
        method = request["method"]
        if method == "signin":
            return _signin_ok()
        if method == "info":
            return _info_error(info_error)
        if method == "query":
            return _auth_query_result(auth_records)
        raise AssertionError(f"unexpected RPC method: {method}")

    return _responder


class _RpcServer:
    """A real local ``/rpc`` endpoint that records what the SDK sent it.

    Requests are decoded from CBOR and appended to :attr:`requests`, which
    replaces the request introspection ``aioresponses`` used to provide (it
    cannot be used at all from aiohttp 3.14 onwards).
    """

    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self._server: TestServer | None = None
        self.requests: list[dict[str, Any]] = []

    async def __aenter__(self) -> _RpcServer:
        app = web.Application()
        # Pinned to ``POST /rpc``, not a catch-all: that is the only request the
        # transport should make, and matching nothing else preserves the
        # implicit assertion the previous mock enforced. A transport that
        # changed method or path now 404s here rather than being answered.
        app.router.add_route("POST", "/rpc", self._handle)
        self._server = TestServer(app)
        await self._server.start_server()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # Always shut the server down so the tests do not leak sockets.
        if self._server is not None:
            await self._server.close()
            self._server = None

    async def _handle(self, request: web.Request) -> web.Response:
        payload = decode(await request.read())
        self.requests.append(payload)
        return web.Response(
            body=self._responder(payload),
            status=200,
            content_type="application/cbor",
        )

    @property
    def url(self) -> str:
        """The base URL to point a connection at (no trailing slash)."""
        assert self._server is not None, "server not started"
        return str(self._server.make_url("/")).rstrip("/")

    @property
    def methods(self) -> list[str]:
        """The RPC method of every request the SDK made, in order."""
        return [request["method"] for request in self.requests]


@pytest.mark.parametrize("error", _NOT_FOUND_ERRORS)
async def test_async_http_info_uses_auth_fallback(error: dict[str, Any]) -> None:
    record = _auth_record()
    async with _RpcServer(_make_responder(error, [record])) as rpc:
        db = AsyncHttpSurrealConnection(rpc.url)
        await db.signin(RECORD_SIGNIN)
        outcome = await db.info()

    assert outcome == record
    assert outcome["id"] == RecordID("user", "tobie")
    # signin + info + $auth query
    assert rpc.methods == ["signin", "info", "query"]
    assert rpc.requests[2]["params"][0] == "SELECT * FROM $auth"


async def test_async_http_info_non_not_found_error_raises() -> None:
    """A non not-found error must be raised, not silently swallowed, and must
    not trigger a second ``$auth`` query."""
    async with _RpcServer(
        _make_responder({"code": -32602, "message": "Not allowed"}, [])
    ) as rpc:
        db = AsyncHttpSurrealConnection(rpc.url)
        await db.signin(RECORD_SIGNIN)
        with pytest.raises(NotAllowedError):
            await db.info()

    # Only signin + info: the fallback query must NOT have fired.
    assert rpc.methods == ["signin", "info"]
