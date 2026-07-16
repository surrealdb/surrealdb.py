from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from surrealdb.spectron import (
    AuditResponse,
    ConsolidateResponse,
    ContextQueryResponse,
    ElaborateResponse,
    ProfileResponse,
    ReflectResponse,
    Spectron,
    StateResponse,
    WhoamiResponse,
)

API_KEY = "test-key"
BASE = "https://api.spectron.test"
CONTEXT = "acme prod"
ENC = "acme%20prod"


@pytest.fixture
def client() -> Spectron:
    return Spectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY)


@responses.activate
def test_consolidate_posts_dry_run(client: Spectron) -> None:
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC}/consolidate",
        json={
            "created": 2,
            "dryRun": True,
            "outcomes": [
                {
                    "entityName": "Acme",
                    "key": "role",
                    "kind": "create",
                    "proofCount": 3,
                    "value": "CTO",
                }
            ],
            "superseded": 0,
            "traceId": "tr:1",
            "updated": 1,
        },
        status=200,
    )
    result = client.consolidate(dry_run=True, fact_limit=50)
    assert isinstance(result, ConsolidateResponse)
    assert result.dry_run is True
    assert result.created == 2
    assert result.outcomes[0].kind == "create"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"dryRun": True, "factLimit": 50}


@responses.activate
def test_audit_gets_with_filters(client: Spectron) -> None:
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{ENC}/audit",
        json={
            "rows": [
                {
                    "traceId": "tr:1",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "kind": "decision",
                    "cost": 0.01,
                    "latencyMs": 12,
                    "rowsTouched": 3,
                    "principal": "principal:agent-7",
                }
            ]
        },
        status=200,
    )
    result = client.audit(kind="decision", limit=10)
    assert isinstance(result, AuditResponse)
    assert result.rows[0].principal == "principal:agent-7"
    assert result.rows[0].model is None
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert qs["kind"] == ["decision"]
    assert qs["limit"] == ["10"]
    assert "principal" not in qs  # None params dropped


@responses.activate
def test_reflect_posts_query(client: Spectron) -> None:
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC}/reflect",
        json={
            "reflection": "You favour async APIs.",
            "evidence": ["fact:1"],
            "persistedAttributes": [],
            "traceId": "tr:2",
        },
        status=200,
    )
    result = client.reflect("what are my preferences", persist=True)
    assert isinstance(result, ReflectResponse)
    assert result.reflection.startswith("You favour")
    body = json.loads(responses.calls[0].request.body)
    assert body == {"query": "what are my preferences", "persist": True}


@responses.activate
def test_elaborate_posts_optional_body(client: Spectron) -> None:
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC}/elaborate",
        json={"outcomes": [], "relationsEmitted": 4},
        status=200,
    )
    result = client.elaborate(entity_ref="entity:person/stu", dry_run=True)
    assert isinstance(result, ElaborateResponse)
    assert result.relations_emitted == 4
    body = json.loads(responses.calls[0].request.body)
    assert body == {"entityRef": "entity:person/stu", "dryRun": True}


@responses.activate
def test_inspect_returns_raw_payload(client: Spectron) -> None:
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{ENC}/inspect",
        json={
            "kind": "entity",
            "entity": {"id": "e:1"},
            "attributes": [],
            "relations": [],
        },
        status=200,
    )
    result = client.inspect("entity:person/stu", as_of="2026-01-01T00:00:00Z")
    assert isinstance(result, dict)
    assert result["kind"] == "entity"
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert qs["ref"] == ["entity:person/stu"]
    assert qs["asOf"] == ["2026-01-01T00:00:00Z"]


@responses.activate
def test_query_context_posts(client: Spectron) -> None:
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC}/context",
        json={"context": "Stu is CTO of Acme.", "queryMs": 5, "tier": "tier2"},
        status=200,
    )
    result = client.query_context("who is stu", k=5, scope_view="merged")
    assert isinstance(result, ContextQueryResponse)
    assert result.tier == "tier2"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"query": "who is stu", "k": 5, "scopeView": "merged"}


@responses.activate
def test_state_whoami_profile(client: Spectron) -> None:
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{ENC}/state",
        json={
            "context": {"entities": [], "attributes": [], "relations": []},
            "identity": {"entities": [], "attributes": [], "relations": []},
            "knowledge": {"entities": [], "attributes": [], "relations": []},
            "instructions": [],
            "unknowns": [],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{ENC}/me",
        json={
            "principalId": "p:1",
            "displayName": "Stu",
            "kind": "human",
            "enforce": True,
            "grants": {"memory:read": ["/*"]},
            "effectiveGrants": {},
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{ENC}/profile",
        json={
            "dynamic": [],
            "preferences": [{"key": "tone", "value": "brief"}],
            "static": [],
            "instructions": [],
        },
        status=200,
    )
    assert isinstance(client.state(), StateResponse)
    who = client.whoami()
    assert isinstance(who, WhoamiResponse)
    assert who.principal_id == "p:1"
    assert who.enforce is True
    prof = client.profile()
    assert isinstance(prof, ProfileResponse)
    assert prof.preferences[0].value == "brief"


@responses.activate
def test_health_is_not_context_scoped(client: Spectron) -> None:
    responses.add(responses.GET, f"{BASE}/api/v1/health", json={"ok": True}, status=200)
    assert client.health() == {"ok": True}
