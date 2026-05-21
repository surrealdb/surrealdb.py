from __future__ import annotations

from surrealdb.spectron import (
    ChatResponse,
    ExtractionResult,
    ForgetResponse,
    RecallResponse,
    RememberBatchResponse,
    RememberResponse,
    UploadResponse,
)


def test_remember_response_decodes_camel_case():
    resp = RememberResponse.from_dict(
        {
            "mode": "infer",
            "sessionId": "sess:abc",
            "chunkId": "chunk:1",
            "preview": False,
            "turnId": "turn:1",
            "extraction": {
                "turnId": "turn:1",
                "entities": [],
                "attributes": [],
                "corrections": [],
                "instructions": [],
                "relations": [],
                "uncertainties": [],
            },
        }
    )
    assert resp.mode == "infer"
    assert resp.session_id == "sess:abc"
    assert resp.chunk_id == "chunk:1"
    assert resp.preview is False
    assert isinstance(resp.extraction, ExtractionResult)
    assert resp.extraction.turn_id == "turn:1"

    encoded = resp.to_dict()
    assert encoded["sessionId"] == "sess:abc"
    assert encoded["chunkId"] == "chunk:1"
    assert encoded["turnId"] == "turn:1"
    assert encoded["extraction"]["turnId"] == "turn:1"


def test_remember_batch_response_decodes_lists():
    resp = RememberBatchResponse.from_dict(
        {
            "sessionId": "sess:abc",
            "turnIds": ["t1", "t2"],
            "extractions": [
                {
                    "turnId": "t1",
                    "entities": [{"name": "Acme"}],
                    "attributes": [],
                    "corrections": [],
                    "instructions": [],
                    "relations": [],
                    "uncertainties": [],
                }
            ],
        }
    )
    assert resp.session_id == "sess:abc"
    assert resp.turn_ids == ["t1", "t2"]
    assert len(resp.extractions) == 1
    assert resp.extractions[0].entities == [{"name": "Acme"}]


def test_recall_response_decodes_hits():
    resp = RecallResponse.from_dict(
        {
            "classificationKind": "hybrid",
            "hits": [
                {"id": "h:1", "score": 0.92, "source": "fact", "text": "I work at Acme"}
            ],
            "queryMs": 17,
            "seedEntities": ["Acme"],
            "tier": "hot",
            "trace": {"id": "trace:1"},
        }
    )
    assert resp.classification_kind == "hybrid"
    assert resp.tier == "hot"
    assert resp.query_ms == 17
    assert resp.seed_entities == ["Acme"]
    assert resp.hits[0].id == "h:1"
    assert resp.hits[0].score == 0.92
    assert resp.hits[0].text == "I work at Acme"
    assert resp.trace == {"id": "trace:1"}


def test_chat_response_decodes_nested_extraction():
    resp = ChatResponse.from_dict(
        {
            "reply": "you're the CTO of Acme",
            "sessionId": "s",
            "traceId": "t",
            "memoryUpdates": {
                "turnId": "tu:1",
                "entities": [],
                "attributes": [],
                "corrections": [],
                "instructions": [],
                "relations": [],
                "uncertainties": [],
            },
        }
    )
    assert resp.reply == "you're the CTO of Acme"
    assert resp.session_id == "s"
    assert resp.trace_id == "t"
    assert isinstance(resp.memory_updates, ExtractionResult)


def test_forget_response_round_trips():
    resp = ForgetResponse.from_dict({"deleted": 3})
    assert resp.deleted == 3
    assert resp.to_dict() == {"deleted": 3}


def test_upload_response_round_trips():
    resp = UploadResponse.from_dict(
        {
            "contentHash": "sha:abc",
            "deduplicated": False,
            "id": "doc:1",
            "status": "queued",
        }
    )
    assert resp.id == "doc:1"
    assert resp.content_hash == "sha:abc"
    assert resp.to_dict()["contentHash"] == "sha:abc"
