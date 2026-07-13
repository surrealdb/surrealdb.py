from __future__ import annotations

import re

import pytest
from aioresponses import aioresponses

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
BASE = "https://api.spectron.test"
CONTEXT = "acme-prod"
ROOT = f"{BASE}/api/v1/{CONTEXT}"


@pytest.mark.asyncio
async def test_async_consolidate_and_audit():
    with aioresponses() as m:
        m.post(
            f"{ROOT}/consolidate",
            payload={
                "created": 1,
                "dryRun": True,
                "outcomes": [],
                "superseded": 0,
                "traceId": "t",
                "updated": 0,
            },
            status=200,
        )
        m.get(
            re.compile(rf"{re.escape(ROOT)}/audit.*"),
            payload={"rows": []},
            status=200,
        )
        async with AsyncSpectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY) as c:
            res = await c.consolidate(dry_run=True)
            assert isinstance(res, ConsolidateResponse)
            assert res.dry_run is True
            audit = await c.audit(kind="decision")
            assert isinstance(audit, AuditResponse)


@pytest.mark.asyncio
async def test_async_namespaces_and_bare_array():
    with aioresponses() as m:
        m.post(
            f"{ROOT}/sessions",
            payload={"id": "sess:1", "createdAt": "t", "scopes": []},
            status=201,
        )
        m.get(
            re.compile(rf"{re.escape(ROOT)}/traces.*"),
            payload={"traces": []},
            status=200,
        )
        m.get(f"{ROOT}/documents/doc%3A1", payload={"id": "doc:1"}, status=200)
        m.get(
            f"{ROOT}/keys",
            payload=[{"id": "k1", "name": "ci", "createdAt": "t"}],
            status=200,
        )
        async with AsyncSpectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY) as c:
            sess = await c.sessions.create()
            assert isinstance(sess, Session)
            traces = await c.traces.list()
            assert isinstance(traces, TraceListResponse)
            doc = await c.documents.get("doc:1")
            assert isinstance(doc, Document)
            keys = await c.keys.list()
            assert isinstance(keys, list)
            assert isinstance(keys[0], KeyDetail)


@pytest.mark.asyncio
async def test_async_fetch_raw_bytes():
    with aioresponses() as m:
        m.get(f"{ROOT}/documents/doc%3A1/raw", body=b"%PDF data", status=200)
        async with AsyncSpectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY) as c:
            data = await c.documents.fetch_raw("doc:1")
            assert data == b"%PDF data"
