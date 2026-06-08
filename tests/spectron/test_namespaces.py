from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from surrealdb.spectron import (
    EffectiveGrants,
    EntityListResponse,
    EntityResponse,
    ForgetScopeResponse,
    FsckReport,
    KeyDetail,
    LifecycleResponse,
    MintedKey,
    Principal,
    ScopeNode,
    Session,
    Spectron,
    TraceListResponse,
    TraceRecord,
    TraceStatsResponse,
    TurnListResponse,
)

API_KEY = "test-key"
BASE = "https://api.spectron.test"
CONTEXT = "acme prod"
ENC = "acme%20prod"
ROOT = f"{BASE}/api/v1/{ENC}"


@pytest.fixture
def client() -> Spectron:
    return Spectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY)


# ---- traces ---------------------------------------------------------------


@responses.activate
def test_traces_list_get_stats(client: Spectron):
    responses.add(
        responses.GET,
        f"{ROOT}/traces",
        json={
            "traces": [
                {
                    "id": "tr:1",
                    "cached": False,
                    "createdAt": "t",
                    "latencyMs": 9,
                    "queryText": "q",
                    "resolutionTier": "t2",
                    "tierReason": "r",
                }
            ]
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{ROOT}/traces/stats",
        json={
            "totalQueries": 10,
            "avgLatencyMs": 5.5,
            "cacheHitRate": 0.5,
            "cacheHits": 5,
            "responseTracesCached": 2,
            "responseTracesTotal": 4,
            "windowHours": 24,
            "contradiction": {},
            "retrieval": {},
            "supersession": {},
            "tierCounts": {},
            "sourceKindDistribution": [],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{ROOT}/traces/tr%3A1",
        json={
            "id": "tr:1",
            "cached": True,
            "createdAt": "t",
            "latencyMs": 3,
            "queryText": "q",
            "resolutionTier": "t1",
            "tierReason": "r",
        },
        status=200,
    )
    listed = client.traces.list(limit=5)
    assert isinstance(listed, TraceListResponse)
    assert listed.traces[0].id == "tr:1"
    stats = client.traces.stats()
    assert isinstance(stats, TraceStatsResponse)
    assert stats.total_queries == 10
    one = client.traces.get("tr:1")
    assert isinstance(one, TraceRecord)
    assert one.cached is True


# ---- lifecycle ------------------------------------------------------------


@responses.activate
def test_lifecycle_decay_expire_fsck(client: Spectron):
    responses.add(
        responses.POST, f"{ROOT}/lifecycle/decay", json={"affected": 7}, status=200
    )
    responses.add(
        responses.POST, f"{ROOT}/lifecycle/expire", json={"affected": 0}, status=200
    )
    responses.add(
        responses.POST,
        f"{ROOT}/fsck",
        json={
            "total": 1,
            "contradictions": [{"a": 1}],
            "duplicates": [],
            "injection": [],
        },
        status=200,
    )
    assert client.lifecycle.decay().affected == 7
    assert isinstance(client.lifecycle.expire(), LifecycleResponse)
    report = client.lifecycle.fsck(check="duplicates", duplicate_threshold=0.9)
    assert isinstance(report, FsckReport)
    assert report.total == 1
    body = json.loads(responses.calls[2].request.body)
    assert body == {"check": "duplicates", "duplicateThreshold": 0.9}


# ---- sessions -------------------------------------------------------------


@responses.activate
def test_sessions_lifecycle(client: Spectron):
    responses.add(
        responses.POST,
        f"{ROOT}/sessions",
        json={"id": "sess:1", "createdAt": "t", "scope": ["org=acme"]},
        status=201,
    )
    responses.add(responses.DELETE, f"{ROOT}/sessions/sess%3A1", status=204)
    responses.add(
        responses.POST,
        f"{ROOT}/sessions/sess%3A1/context",
        json={"context": "summary"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{ROOT}/sessions/sess%3A1/turns",
        json={
            "turns": [
                {
                    "id": "t:1",
                    "content": "hi",
                    "createdAt": "t",
                    "role": "user",
                    "seq": 1,
                    "session": "sess:1",
                }
            ]
        },
        status=200,
    )
    created = client.sessions.create(scope={"org": "acme"})
    assert isinstance(created, Session)
    assert created.scope == ["org=acme"]
    assert json.loads(responses.calls[0].request.body) == {"scope": ["org=acme"]}
    assert client.sessions.delete("sess:1") is None
    assert client.sessions.context("sess:1", "recap").context == "summary"
    turns = client.sessions.turns("sess:1", limit=10)
    assert isinstance(turns, TurnListResponse)
    assert turns.turns[0].role == "user"


# ---- entities -------------------------------------------------------------


@responses.activate
def test_entities(client: Spectron):
    responses.add(
        responses.GET,
        f"{ROOT}/entities",
        json={
            "entities": [
                {
                    "id": "e:1",
                    "entityType": "person",
                    "name": "Stu",
                    "createdAt": "t",
                    "updatedAt": "t",
                    "importance": 0.5,
                    "memoryCategory": "identity",
                }
            ]
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{ROOT}/entities/person/Stu",
        json={
            "entity": {
                "id": "e:1",
                "entityType": "person",
                "name": "Stu",
                "createdAt": "t",
                "updatedAt": "t",
                "importance": 0.5,
                "memoryCategory": "identity",
            },
            "attributes": [],
            "relations": [],
        },
        status=200,
    )
    responses.add(responses.DELETE, f"{ROOT}/entities/person/Stu", status=204)
    listed = client.entities.list(entity_type="person")
    assert isinstance(listed, EntityListResponse)
    assert listed.entities[0].name == "Stu"
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert qs["type"] == ["person"]
    got = client.entities.get("person", "Stu")
    assert isinstance(got, EntityResponse)
    assert got.entity.id == "e:1"
    assert client.entities.delete("person", "Stu") is None


# ---- keys -----------------------------------------------------------------


@responses.activate
def test_keys(client: Spectron):
    responses.add(
        responses.POST,
        f"{ROOT}/keys",
        json={"id": "k1", "key": "sp-k1-secret", "validUntil": None},
        status=201,
    )
    responses.add(
        responses.GET,
        f"{ROOT}/keys",
        json=[{"id": "k1", "name": "ci", "createdAt": "t"}],
        status=200,
    )
    responses.add(responses.DELETE, f"{ROOT}/keys/ci", status=204)
    minted = client.keys.create(name="ci", ttl_seconds=3600)
    assert isinstance(minted, MintedKey)
    assert minted.key == "sp-k1-secret"
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert qs["ttlSeconds"] == ["3600"]
    assert json.loads(responses.calls[0].request.body) == {"name": "ci"}
    keys = client.keys.list()
    assert isinstance(keys, list)
    assert isinstance(keys[0], KeyDetail)
    assert client.keys.delete("ci") is None


# ---- principals -----------------------------------------------------------


@responses.activate
def test_principals(client: Spectron):
    responses.add(
        responses.GET,
        f"{ROOT}/principals",
        json=[{"id": "p1", "displayName": "Stu", "kind": "human", "grants": {}}],
        status=200,
    )
    responses.add(
        responses.POST,
        f"{ROOT}/principals/p1/grants",
        json={
            "id": "p1",
            "displayName": "Stu",
            "kind": "human",
            "grants": {"memory:read": ["/*"]},
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{ROOT}/principals/p1/effective",
        json={"path": "/", "verbs": ["memory:read"]},
        status=200,
    )
    listed = client.principals.list()
    assert isinstance(listed[0], Principal)
    granted = client.principals.grant("p1", "/*", ["memory:read"])
    assert granted.grants == {"memory:read": ["/*"]}
    assert json.loads(responses.calls[1].request.body) == {
        "path": "/*",
        "verbs": ["memory:read"],
    }
    eff = client.principals.effective("p1", "/")
    assert isinstance(eff, EffectiveGrants)
    assert eff.verbs == ["memory:read"]
    qs = parse_qs(urlparse(responses.calls[2].request.url).query)
    assert qs["path"] == ["/"]


# ---- scopes ---------------------------------------------------------------


@responses.activate
def test_scopes(client: Spectron):
    responses.add(
        responses.POST,
        f"{ROOT}/scopes",
        json={"path": "org/acme/", "createdAt": "t", "tombstonedAt": None},
        status=201,
    )
    responses.add(
        responses.GET,
        f"{ROOT}/scopes",
        json=[{"path": "org/acme/", "createdAt": "t"}],
        status=200,
    )
    responses.add(responses.DELETE, f"{ROOT}/scopes", status=204)
    responses.add(
        responses.POST,
        f"{ROOT}/scopes/forget",
        json={"forgotten": 12},
        status=200,
    )
    node = client.scopes.register("org/acme/", display_name="Acme")
    assert isinstance(node, ScopeNode)
    assert json.loads(responses.calls[0].request.body) == {
        "path": "org/acme/",
        "displayName": "Acme",
    }
    assert isinstance(client.scopes.list()[0], ScopeNode)
    assert client.scopes.delete("org/acme/") is None
    forgotten = client.scopes.forget("user/stu/")
    assert isinstance(forgotten, ForgetScopeResponse)
    assert forgotten.forgotten == 12
