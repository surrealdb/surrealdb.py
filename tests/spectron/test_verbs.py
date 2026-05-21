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
    assert body == {"text": "I work at Acme as CTO", "sessionId": "sess:1"}
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
    assert body == {"messages": [{"role": "user", "content": "hello"}], "sessionId": "s"}
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
        json={"contentHash": "h", "deduplicated": False, "id": "doc:1", "status": "queued"},
        status=200,
    )
    result = client.documents.upload(f, content_type="text/plain")
    assert isinstance(result, UploadResponse)
    assert result.id == "doc:1"
    sent = responses.calls[0].request
    assert sent.headers["Authorization"] == f"Bearer {API_KEY}"
    assert sent.headers["Content-Type"].startswith("multipart/form-data")


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
