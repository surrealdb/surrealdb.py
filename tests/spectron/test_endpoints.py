from __future__ import annotations

import json
import re

import pytest
import responses

from surrealdb import Spectron
from surrealdb.spectron import KnowledgeNodeUpsertRow, QueryMode

BASE = "https://api.spectron.test"
API_KEY = "test-key"
CTX = "acme-prod"


@pytest.fixture
def client() -> Spectron:
    return Spectron(context=CTX, base_url=BASE, api_key=API_KEY)


@responses.activate
def test_knowledge_query(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/knowledge/query",
        json={
            "queryMs": 10,
            "results": [
                {
                    "score": 0.5,
                    "chunk": {
                        "id": "c", "document": "d", "charStart": 0, "charEnd": 1,
                        "position": 0, "text": "t",
                    },
                    "document": {"id": "d", "title": "T", "source": "s"},
                }
            ],
        },
        status=200,
    )
    out = client.knowledge.query("question", mode=QueryMode.HYBRID, k=5)
    assert out.query_ms == 10
    assert out.results[0].score == 0.5

    body = json.loads(responses.calls[0].request.body)
    assert body["query"] == "question"
    assert body["mode"] == "hybrid"
    assert body["k"] == 5


@responses.activate
def test_knowledge_list_with_query_params(client: Spectron):
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{CTX}/knowledge",
        json={"documents": [], "page": 0, "pageSize": 10, "total": 0},
        status=200,
    )
    client.knowledge.list(status="ready", mime_type="application/pdf", page=1, page_size=10)
    sent = responses.calls[0].request
    assert "status=ready" in sent.url
    assert "mime_type=application%2Fpdf" in sent.url
    assert "page=1" in sent.url
    assert "page_size=10" in sent.url


@responses.activate
def test_knowledge_nodes_upsert(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/knowledge/nodes/batch",
        body="",
        status=204,
    )
    client.knowledge.nodes.upsert(
        nodes=[KnowledgeNodeUpsertRow(kind="product", slug="airpods", title="AirPods")],
        scope={"org": "apple"},
    )
    body = json.loads(responses.calls[0].request.body)
    assert body["nodes"] == [
        {"kind": "product", "slug": "airpods", "title": "AirPods"}
    ]
    assert body["scope"] == [{"key": "org", "value": "apple"}]


@responses.activate
def test_knowledge_traverse(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/knowledge/traverse",
        json={"edges": [], "nodes": []},
        status=200,
    )
    client.knowledge.traverse(
        start=[{"type": "document", "id": "doc:1"}],
        edges=["knowledge_has_keyword"],
        max_depth=2,
    )
    body = json.loads(responses.calls[0].request.body)
    assert body["start"] == [{"type": "document", "id": "doc:1"}]
    assert body["edges"] == ["knowledge_has_keyword"]
    assert body["maxDepth"] == 2


@responses.activate
def test_knowledge_keywords_search(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/knowledge/keywords/search",
        json={"queryMs": 1, "results": []},
        status=200,
    )
    client.knowledge.keywords.search("refund", k=10, threshold=0.6)
    body = json.loads(responses.calls[0].request.body)
    assert body == {"query": "refund", "k": 10, "threshold": 0.6}


@responses.activate
def test_knowledge_keyword_path_encoded(client: Spectron):
    responses.add(
        responses.GET,
        re.compile(rf"{re.escape(BASE)}/api/v1/{CTX}/knowledge/keywords/[^/]+"),
        json={
            "id": "k:1",
            "normalised": "RETURN POLICY",
            "text": "return policy",
            "documentCount": 2,
            "documents": [],
        },
        status=200,
    )
    client.knowledge.keywords.get("RETURN POLICY")
    assert "%20" in responses.calls[0].request.url


@responses.activate
def test_sessions_create_and_turn(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/sessions",
        json={
            "id": "session:abc",
            "scope": [{"key": "user", "value": "tobie"}],
        },
        status=201,
    )
    session = client.sessions.create(scope={"user": "tobie"})
    assert session.id == "session:abc"

    body = json.loads(responses.calls[0].request.body)
    assert body["scope"] == [{"key": "user", "value": "tobie"}]

    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/sessions/session%3Aabc/turns",
        json={"entities": [], "attributes": [], "relations": []},
        status=200,
    )
    diff = session.turn("user", "I just got promoted to CTO")
    assert diff.entities == []


@responses.activate
def test_memory_query_one_shot(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/query",
        json={"hits": [], "tier": "hybrid", "queryMs": 7},
        status=200,
    )
    out = client.query("what role does Christian have?", k=10)
    assert out.tier == "hybrid"
    assert out.query_ms == 7


@responses.activate
def test_memory_state(client: Spectron):
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{CTX}/state",
        json={"identity": {"name": "tobie"}, "instructions": []},
        status=200,
    )
    state = client.state()
    assert state.identity == {"name": "tobie"}


@responses.activate
def test_entities_get(client: Spectron):
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{CTX}/entities/Person/christian_battaglia",
        json={"type": "Person", "name": "christian_battaglia", "attributes": {"role": "CTO"}},
        status=200,
    )
    e = client.entities.get("Person", "christian_battaglia")
    assert e.attributes == {"role": "CTO"}


@responses.activate
def test_lifecycle_decay(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{CTX}/lifecycle/decay",
        body="",
        status=204,
    )
    client.lifecycle.decay()
    assert len(responses.calls) == 1


@responses.activate
def test_traces_stats(client: Spectron):
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/{CTX}/traces/stats",
        json={"totalQueries": 42, "cacheHits": 30, "avgLatencyMs": 4.5},
        status=200,
    )
    stats = client.traces.stats()
    assert stats.total_queries == 42
    assert stats.cache_hits == 30
