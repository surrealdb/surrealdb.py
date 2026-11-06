from __future__ import annotations

import asyncio

import pytest
from aiohttp import web

from surrealdb_memory import AsyncMemory, Memory

from .test_async_namespaces import API_KEY, CONTEXT, ROOT, _serve


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True], ids=["blocking", "async"])
@pytest.mark.parametrize("target", [None, "", "agent-7", "principal:agent-7"])
async def test_delegation_header_reaches_http_server(
    asynchronous: bool, target: str | None
) -> None:
    seen: list[str] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        assert "X-Memory-On-Behalf-Of" not in request.headers
        assert request.headers.get("X-Spectron-On-Behalf-Of") == (target or None)
        seen.append(request.path)
        if request.path == f"{ROOT}/facts":
            assert request.method == "POST"
            assert "Idempotency-Key" in request.headers
            assert await request.json() == {"text": "delegated fact"}
            return web.json_response({"mode": "infer", "sessionId": "s"})
        if request.path == f"{ROOT}/state":
            assert request.method == "GET"
            return web.json_response({"context": {"name": "test"}})
        assert request.path == f"{ROOT}/sessions"
        assert request.method == "POST"
        assert await request.json() == {"metadata": {"source": "test"}}
        return web.json_response({"id": "s"})

    async with _serve(handler) as server:
        endpoint = str(server.make_url("/"))
        if asynchronous:
            async with AsyncMemory(
                context=CONTEXT, endpoint=endpoint, api_key=API_KEY
            ) as client:
                remembered = await client.remember(
                    "delegated fact", on_behalf_of=target
                )
                state = await client.state(on_behalf_of=target)
                session = await client.sessions.create(
                    metadata={"source": "test"}, on_behalf_of=target
                )
        else:
            with Memory(
                context=CONTEXT, endpoint=endpoint, api_key=API_KEY
            ) as blocking_client:
                remembered = await asyncio.to_thread(
                    blocking_client.remember, "delegated fact", on_behalf_of=target
                )
                state = await asyncio.to_thread(
                    blocking_client.state, on_behalf_of=target
                )
                session = await asyncio.to_thread(
                    blocking_client.sessions.create,
                    metadata={"source": "test"},
                    on_behalf_of=target,
                )

    assert remembered.session_id == "s"
    assert state.context == {"name": "test"}
    assert session.id == "s"
    assert seen == [f"{ROOT}/facts", f"{ROOT}/state", f"{ROOT}/sessions"]
