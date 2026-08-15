from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from surrealdb.spectron import (
    AsyncSpectron,
    AuditResponse,
    ConsolidateResponse,
    Document,
    KeyDetail,
    Session,
    TraceListResponse,
)

API_KEY = "test-key"
CONTEXT = "acme-prod"
# Every context-scoped route hangs off this path prefix. These tests used to
# match absolute URLs against an imaginary host; a real loopback server picks
# its host and port at bind time, so routes are matched on the path alone.
ROOT = f"/api/v1/{CONTEXT}"

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


@asynccontextmanager
async def _serve(handler: Handler) -> AsyncIterator[TestServer]:
    """Run ``handler`` on a real loopback HTTP server for the duration of a test.

    Every method and path is routed to ``handler`` so that a request the SDK
    should not have made still reaches it and can be answered with a 404, which
    is what an unregistered URL used to produce.
    """
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    try:
        yield server
    finally:
        await server.close()


def _unexpected(request: web.Request) -> web.StreamResponse:
    """Answer a route the SDK was not supposed to call.

    404 maps to ``SpectronNotFoundError``, so a wrong URL fails the test loudly
    instead of silently falling through to a catch-all response.
    """
    return web.json_response(
        {"message": f"unexpected route {request.method} {request.path}"},
        status=404,
    )


@pytest.mark.asyncio
async def test_async_consolidate_and_audit() -> None:
    seen: list[tuple[str, str, dict[str, str]]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        seen.append((request.method, request.path, dict(request.query)))
        if request.method == "POST" and request.path == f"{ROOT}/consolidate":
            return web.json_response(
                {
                    "created": 1,
                    "dryRun": True,
                    "outcomes": [],
                    "superseded": 0,
                    "traceId": "t",
                    "updated": 0,
                },
                status=200,
            )
        if request.method == "GET" and request.path == f"{ROOT}/audit":
            return web.json_response({"rows": []}, status=200)
        return _unexpected(request)

    async with (
        _serve(handler) as server,
        AsyncSpectron(
            context=CONTEXT,
            endpoint=str(server.make_url("/")),
            api_key=API_KEY,
        ) as c,
    ):
        res = await c.consolidate(dry_run=True)
        assert isinstance(res, ConsolidateResponse)
        assert res.dry_run is True
        audit = await c.audit(kind="decision")
        assert isinstance(audit, AuditResponse)

    assert seen == [
        ("POST", f"{ROOT}/consolidate", {}),
        ("GET", f"{ROOT}/audit", {"kind": "decision"}),
    ]


@pytest.mark.asyncio
async def test_async_namespaces_and_bare_array() -> None:
    seen: list[tuple[str, str]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        seen.append((request.method, request.path))
        if request.method == "POST" and request.path == f"{ROOT}/sessions":
            return web.json_response(
                {"id": "sess:1", "createdAt": "t", "scopes": []},
                status=201,
            )
        if request.method == "GET" and request.path == f"{ROOT}/traces":
            return web.json_response({"traces": []}, status=200)
        # The SDK percent-encodes the record id, but `:` is legal inside a path
        # segment so it is normalised back to `doc:1` on the wire.
        if request.method == "GET" and request.path == f"{ROOT}/documents/doc:1":
            return web.json_response({"id": "doc:1"}, status=200)
        # `keys.list` answers with a bare JSON array rather than an envelope
        # object; this case exists to pin that response shape.
        if request.method == "GET" and request.path == f"{ROOT}/keys":
            return web.json_response(
                [{"id": "k1", "name": "ci", "createdAt": "t"}],
                status=200,
            )
        return _unexpected(request)

    async with (
        _serve(handler) as server,
        AsyncSpectron(
            context=CONTEXT,
            endpoint=str(server.make_url("/")),
            api_key=API_KEY,
        ) as c,
    ):
        sess = await c.sessions.create()
        assert isinstance(sess, Session)
        traces = await c.traces.list()
        assert isinstance(traces, TraceListResponse)
        doc = await c.documents.get("doc:1")
        assert isinstance(doc, Document)
        keys = await c.keys.list()
        assert isinstance(keys, list)
        assert isinstance(keys[0], KeyDetail)

    assert seen == [
        ("POST", f"{ROOT}/sessions"),
        ("GET", f"{ROOT}/traces"),
        ("GET", f"{ROOT}/documents/doc:1"),
        ("GET", f"{ROOT}/keys"),
    ]


@pytest.mark.asyncio
async def test_async_fetch_raw_bytes() -> None:
    async def handler(request: web.Request) -> web.StreamResponse:
        if request.method == "GET" and request.path == f"{ROOT}/documents/doc:1/raw":
            # Served as opaque octets: the assertion below proves the SDK hands
            # the body back byte-for-byte, with no decoding or re-encoding.
            return web.Response(
                body=b"%PDF data",
                content_type="application/octet-stream",
            )
        return _unexpected(request)

    async with (
        _serve(handler) as server,
        AsyncSpectron(
            context=CONTEXT,
            endpoint=str(server.make_url("/")),
            api_key=API_KEY,
        ) as c,
    ):
        data = await c.documents.fetch_raw("doc:1")
        assert data == b"%PDF data"
