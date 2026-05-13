from __future__ import annotations

from surrealdb.spectron import (
    ChunkPageJson,
    DocumentJson,
    KnowledgeNodeUpsertRow,
    QueryMode,
    QueryResponseJson,
    TraverseApiResponse,
)


def test_document_decodes_camel_case_optional_fields():
    payload = {
        "id": "doc:returns",
        "title": "Returns",
        "source": "returns.pdf",
        "status": "ready",
        "mimeType": "application/pdf",
        "sizeBytes": 4096,
        "contentHash": "abc",
        "version": 2,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
        "chunkCount": 12,
        "keywordCount": 7,
        "language": "en",
        "processingStartedAt": None,
        "processingCompletedAt": None,
        "error": None,
    }
    doc = DocumentJson.from_dict(payload)
    assert doc.id == "doc:returns"
    assert doc.mime_type == "application/pdf"
    assert doc.size_bytes == 4096
    assert doc.chunk_count == 12
    assert doc.language == "en"

    encoded = doc.to_dict()
    assert encoded["mimeType"] == "application/pdf"
    assert encoded["sizeBytes"] == 4096
    assert encoded["chunkCount"] == 12
    assert "error" not in encoded


def test_chunk_page_decodes_nested_list():
    page = ChunkPageJson.from_dict(
        {
            "chunks": [
                {
                    "id": "chunk:1",
                    "document": "doc:1",
                    "charStart": 0,
                    "charEnd": 100,
                    "position": 0,
                    "text": "hello",
                    "section": None,
                    "tokenCount": 20,
                }
            ],
            "page": 0,
            "pageSize": 50,
            "total": 1,
        }
    )
    assert page.total == 1
    assert page.chunks[0].id == "chunk:1"
    assert page.chunks[0].char_end == 100
    assert page.chunks[0].token_count == 20


def test_query_response_decodes_graph_evidence():
    response = QueryResponseJson.from_dict(
        {
            "queryMs": 12,
            "results": [
                {
                    "score": 0.91,
                    "chunk": {
                        "id": "c:1",
                        "document": "d:1",
                        "charStart": 0,
                        "charEnd": 10,
                        "position": 0,
                        "text": "foo",
                    },
                    "document": {"id": "d:1", "title": "Doc", "source": "doc.pdf"},
                    "graphEvidence": [
                        {"edgeKind": "knowledge_has_keyword", "neighbourLabel": "k", "weight": 0.7}
                    ],
                }
            ],
        }
    )
    assert response.query_ms == 12
    assert response.results[0].score == 0.91
    assert response.results[0].graph_evidence is not None
    assert response.results[0].graph_evidence[0].edge_kind == "knowledge_has_keyword"


def test_traverse_response_decodes_from_alias():

    payload = {
        "edges": [{"kind": "edge", "from": "node:a", "to": "node:b"}],
        "nodes": [{"id": "node:a", "type": "document", "depth": 0}],
    }
    resp = TraverseApiResponse.from_dict(payload)
    assert resp.edges[0].from_ == "node:a"
    assert resp.edges[0].to == "node:b"
    assert resp.nodes[0].depth == 0
    assert resp.edges[0].to_dict()["from"] == "node:a"


def test_enums_round_trip_through_to_dict():
    row = KnowledgeNodeUpsertRow(
        kind="product",
        slug="airpods",
        title="AirPods",
        content={"price": 249},
    )
    encoded = row.to_dict()
    assert encoded == {
        "kind": "product",
        "slug": "airpods",
        "title": "AirPods",
        "content": {"price": 249},
    }


def test_query_mode_enum_values():
    assert QueryMode.HYBRID.value == "hybrid"
    assert QueryMode.HYBRID_GRAPH.value == "hybrid_graph"
