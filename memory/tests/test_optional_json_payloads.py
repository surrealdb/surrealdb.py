from __future__ import annotations

import asyncio
from operator import attrgetter
from typing import Any

import pytest
from aiohttp import web

from surrealdb_memory import AsyncMemory, Memory

from .test_async_namespaces import API_KEY, CONTEXT, ROOT, _serve


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True], ids=["blocking", "async"])
@pytest.mark.parametrize("with_options", [False, True], ids=["defaults", "options"])
@pytest.mark.parametrize(
    ("method", "route", "options", "payload", "response"),
    [
        (
            "consolidate",
            "/consolidate",
            {"dry_run": True, "fact_limit": 0},
            {"dryRun": True, "factLimit": 0},
            {"created": 1},
        ),
        (
            "elaborate",
            "/elaborate",
            {"budget": 0, "sweep": True},
            {"budget": 0, "sweep": True},
            {"relationsEmitted": 1},
        ),
        (
            "sessions.create",
            "/sessions",
            {"metadata": {}},
            {"metadata": {}},
            {"id": "session:1"},
        ),
        (
            "keys.create",
            "/keys",
            {"name": "test", "grants": {}},
            {"name": "test", "grants": {}},
            {"id": "key:1", "key": "test-key"},
        ),
        (
            "lifecycle.fsck",
            "/fsck",
            {"check": "duplicates", "max_results": 0},
            {"check": "duplicates", "maxResults": 0},
            {"total": 0},
        ),
        (
            "scopes.forget",
            "/scopes/forget",
            {"path": "org/test"},
            {"path": "org/test"},
            {"forgotten": 0},
        ),
    ],
)
async def test_optional_payload_is_a_json_object(
    asynchronous: bool,
    with_options: bool,
    method: str,
    route: str,
    options: dict[str, Any],
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    seen: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        assert request.method == "POST"
        assert request.path == ROOT + route
        if request.content_type != "application/json":
            return web.json_response({"message": "Expected JSON"}, status=415)
        body = await request.json()
        assert body == (payload if with_options else {})
        seen.append(body)
        return web.json_response(response)

    async with _serve(handler) as server:
        endpoint = str(server.make_url("/"))
        kwargs = options if with_options else {}
        if asynchronous:
            async with AsyncMemory(
                context=CONTEXT, endpoint=endpoint, api_key=API_KEY
            ) as client:
                result = await attrgetter(method)(client)(**kwargs)
        else:
            with Memory(
                context=CONTEXT, endpoint=endpoint, api_key=API_KEY
            ) as blocking_client:
                result = await asyncio.to_thread(
                    attrgetter(method)(blocking_client), **kwargs
                )

    for key, value in response.items():
        assert result.to_dict()[key] == value
    assert seen == [payload if with_options else {}]
