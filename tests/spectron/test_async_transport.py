from __future__ import annotations

import asyncio
import re

import pytest
from aioresponses import aioresponses

from surrealdb.spectron import NotFoundError, ServerError
from surrealdb.spectron._transport import AsyncTransport

API_KEY = "test-key"
BASE = "https://api.spectron.test"


def _async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.asyncio
async def test_async_get_sends_bearer_header():
    with aioresponses() as m:
        m.get(f"{BASE}/api/v1/x/health", payload={"ok": True}, status=200)
        async with AsyncTransport(base_url=BASE, api_key=API_KEY) as t:
            body = await t.get("/api/v1/x/health")
            assert body == {"ok": True}
            request = list(m.requests.values())[0][0]
            assert request.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"


@pytest.mark.asyncio
async def test_async_get_retries_on_5xx(monkeypatch):
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    url_re = re.compile(rf"{re.escape(BASE)}/api/v1/x/y")
    with aioresponses() as m:
        m.get(url_re, status=503, payload={"e": 1})
        m.get(url_re, status=502, payload={"e": 2})
        m.get(url_re, status=200, payload={"ok": True})
        async with AsyncTransport(base_url=BASE, api_key=API_KEY) as t:
            body = await t.get("/api/v1/x/y")
            assert body == {"ok": True}


@pytest.mark.asyncio
async def test_async_post_does_not_retry(monkeypatch):
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    with aioresponses() as m:
        m.post(f"{BASE}/api/v1/x/z", status=503, payload={"title": "down"})
        async with AsyncTransport(base_url=BASE, api_key=API_KEY) as t:
            with pytest.raises(ServerError):
                await t.post("/api/v1/x/z", json={})
        assert len(m.requests) == 1


@pytest.mark.asyncio
async def test_async_404_maps_to_not_found():
    with aioresponses() as m:
        m.get(f"{BASE}/api/v1/x/missing", status=404, payload={"title": "gone"})
        async with AsyncTransport(base_url=BASE, api_key=API_KEY) as t:
            with pytest.raises(NotFoundError):
                await t.get("/api/v1/x/missing")
