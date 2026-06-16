from __future__ import annotations

import json

import pytest
import responses

from surrealdb.spectron import (
    AsyncSpectron,
    ChatResponse,
    ForgetResponse,
    RecallResponse,
    RememberBatchResponse,
    RememberResponse,
    Spectron,
    UploadResponse,
)

API_KEY = "test-key"
BASE = "https://api.spectron.test"
CONTEXT = "acme prod"
ENC_CONTEXT = "acme%20prod"


@pytest.fixture
def client() -> Spectron:
    return Spectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY)


@responses.activate
def test_remember_posts_to_facts_with_idempotency_key(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/facts",
        json={
            "mode": "infer",
            "sessionId": "sess:1",
            "chunkId": "chunk:1",
            "extraction": {
                "turnId": "t:1",
                "entities": [],
                "attributes": [],
                "corrections": [],
                "instructions": [],
                "relations": [],
                "uncertainties": [],
            },
        },
        status=200,
    )
    result = client.remember("I work at Acme as CTO", session_id="sess:1")
    assert isinstance(result, RememberResponse)
    assert result.session_id == "sess:1"
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body == {"text": "I work at Acme as CTO", "session_id": "sess:1"}
    assert sent.headers["Authorization"] == f"Bearer {API_KEY}"
    assert "Idempotency-Key" in sent.headers
    assert len(sent.headers["Idempotency-Key"]) == 64


@responses.activate
def test_remember_many_posts_to_facts_batch(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/facts/batch",
        json={"sessionId": "s", "turnIds": ["t1"], "extractions": []},
        status=200,
    )
    result = client.remember_many(
        [{"role": "user", "content": "hello"}],
        session_id="s",
    )
    assert isinstance(result, RememberBatchResponse)
    assert result.turn_ids == ["t1"]
    sent = responses.calls[0].request
    body = json.loads(sent.body)
    assert body == {
        "messages": [{"role": "user", "content": "hello"}],
        "session_id": "s",
    }
    assert "Idempotency-Key" in sent.headers


@responses.activate
def test_recall_posts_to_query(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/query",
        json={
            "classificationKind": "hybrid",
            "hits": [{"id": "h:1", "score": 0.9, "source": "fact", "text": "hi"}],
            "queryMs": 3,
            "seedEntities": [],
            "tier": "hot",
            "trace": {},
        },
        status=200,
    )
    result = client.recall("hi", k=5, mode="hybrid")
    assert isinstance(result, RecallResponse)
    assert result.hits[0].id == "h:1"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"query": "hi", "k": 5, "mode": "hybrid"}
    assert "Idempotency-Key" not in responses.calls[0].request.headers


@responses.activate
def test_forget_posts_to_forget(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/forget",
        json={"deleted": 2},
        status=200,
    )
    result = client.forget("old fact", purge=True)
    assert isinstance(result, ForgetResponse)
    assert result.deleted == 2
    body = json.loads(responses.calls[0].request.body)
    assert body == {"query": "old fact", "purge": True}


@responses.activate
def test_chat_non_stream_posts_to_chat(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/chat",
        json={
            "reply": "you're the CTO",
            "sessionId": "s",
            "traceId": "tr",
            "memoryUpdates": {
                "turnId": "t",
                "entities": [],
                "attributes": [],
                "corrections": [],
                "instructions": [],
                "relations": [],
                "uncertainties": [],
            },
        },
        status=200,
    )
    result = client.chat("what's my role?")
    assert isinstance(result, ChatResponse)
    assert result.reply == "you're the CTO"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"message": "what's my role?"}


@responses.activate
def test_documents_upload_posts_multipart(client: Spectron, tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("contents")
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/documents",
        json={
            "contentHash": "h",
            "deduplicated": False,
            "id": "doc:1",
            "status": "queued",
        },
        status=200,
    )
    result = client.documents.upload(
        f,
        content_type="text/plain",
        title="Returns policy",
        source="kb",
        scopes=["org/acme"],
    )
    assert isinstance(result, UploadResponse)
    assert result.id == "doc:1"
    sent = responses.calls[0].request
    assert sent.headers["Authorization"] == f"Bearer {API_KEY}"
    assert sent.headers["Content-Type"].startswith("multipart/form-data")
    raw = sent.body
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    # The `metadata` JSON part precedes the `file` part.
    assert raw.index('name="metadata"') < raw.index('name="file"')
    assert '"title": "Returns policy"' in raw
    assert '"source": "kb"' in raw
    # The write scopes ride in the metadata part as DNF clauses.
    metadata_part = raw[raw.index('name="metadata"') : raw.index('name="file"')]
    assert '[["org/acme"]]' in metadata_part


@responses.activate
def test_scopes_serialise_to_dnf_clauses(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/facts",
        json={"mode": "infer", "sessionId": "s"},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/chat",
        json={"reply": "ok", "sessionId": "s", "traceId": "tr"},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/facts",
        json={"mode": "infer", "sessionId": "s"},
        status=200,
    )

    # A bare string is one singleton clause.
    client.remember("x", scopes="org/acme")
    assert json.loads(responses.calls[0].request.body)["scopes"] == [["org/acme"]]

    # A flat list of paths is an OR of singleton clauses.
    client.chat("y", scopes=["team/acme", "project/x"])
    assert json.loads(responses.calls[1].request.body)["scopes"] == [
        ["team/acme"],
        ["project/x"],
    ]

    # A nested clause is an AND of its paths.
    client.remember("z", scopes=[["team/acme", "project/x"]])
    assert json.loads(responses.calls[2].request.body)["scopes"] == [
        ["team/acme", "project/x"],
    ]


@responses.activate
def test_on_behalf_of_sends_delegation_header(client: Spectron):
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/facts",
        json={"mode": "infer", "sessionId": "s"},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{BASE}/api/v1/{ENC_CONTEXT}/query",
        json={
            "classificationKind": "hybrid",
            "hits": [],
            "queryMs": 1,
            "seedEntities": [],
            "tier": "hot",
            "trace": {},
        },
        status=200,
    )

    # A write merges delegation with the idempotency header.
    client.remember("x", on_behalf_of="principal:agent-7")
    write = responses.calls[0].request
    assert write.headers["X-Spectron-On-Behalf-Of"] == "principal:agent-7"
    assert "Idempotency-Key" in write.headers

    # A read sends it too, and omits it when not set.
    client.recall("q", on_behalf_of="principal:agent-7")
    assert (
        responses.calls[1].request.headers["X-Spectron-On-Behalf-Of"]
        == "principal:agent-7"
    )
    client.recall("q")
    assert "X-Spectron-On-Behalf-Of" not in responses.calls[2].request.headers


def test_context_quotes_special_chars(client: Spectron):
    assert client.context_id == CONTEXT
    assert client._base.endswith(f"/api/v1/{ENC_CONTEXT}")


@pytest.mark.asyncio
async def test_async_client_constructs():
    # Lightweight construction test — covers transport not strictly required.
    client = AsyncSpectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY)
    try:
        assert client.context_id == CONTEXT
        assert client.endpoint == BASE
        assert client.api_key == API_KEY
    finally:
        await client.close()
