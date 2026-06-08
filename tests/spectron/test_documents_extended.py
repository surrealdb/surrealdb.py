from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from surrealdb.spectron import (
    ChunkPage,
    Document,
    DocumentKeywordsResponse,
    DocumentPage,
    DocumentQueryResponse,
    KeywordDetail,
    KeywordPage,
    KeywordSearchResponse,
    RecomputeLinksResponse,
    Spectron,
    UploadResponse,
)

API_KEY = "test-key"
BASE = "https://api.spectron.test"
CONTEXT = "acme prod"
ENC = "acme%20prod"
DOCS = f"{BASE}/api/v1/{ENC}/documents"


@pytest.fixture
def client() -> Spectron:
    return Spectron(context=CONTEXT, endpoint=BASE, api_key=API_KEY)


@responses.activate
def test_get_delete_document(client: Spectron):
    responses.add(
        responses.GET,
        f"{DOCS}/doc%3A1",
        json={
            "id": "doc:1",
            "contentHash": "h",
            "createdAt": "t",
            "mimeType": "application/pdf",
            "sizeBytes": 10,
            "source": "kb",
            "status": "Ready",
            "title": "T",
            "updatedAt": "t",
            "version": 1,
        },
        status=200,
    )
    responses.add(responses.DELETE, f"{DOCS}/doc%3A1", status=204)
    doc = client.documents.get("doc:1")
    assert isinstance(doc, Document)
    assert doc.status == "Ready"
    assert client.documents.delete("doc:1") is None


@responses.activate
def test_list_documents_with_filters(client: Spectron):
    responses.add(
        responses.GET,
        DOCS,
        json={"documents": [], "page": 1, "pageSize": 20, "total": 0},
        status=200,
    )
    page = client.documents.list(status="Ready", page=1, page_size=20)
    assert isinstance(page, DocumentPage)
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert qs["status"] == ["Ready"]
    assert qs["page_size"] == ["20"]


@responses.activate
def test_query_documents(client: Spectron):
    responses.add(
        responses.POST,
        f"{DOCS}/query",
        json={
            "queryMs": 4,
            "results": [
                {"score": 0.9, "chunk": {"id": "c:1"}, "document": {"id": "doc:1"}}
            ],
        },
        status=200,
    )
    result = client.documents.query(
        "returns policy", k=5, mode="hybrid", expand_graph=True
    )
    assert isinstance(result, DocumentQueryResponse)
    assert result.results[0].chunk["id"] == "c:1"
    body = json.loads(responses.calls[0].request.body)
    assert body == {
        "query": "returns policy",
        "k": 5,
        "mode": "hybrid",
        "expandGraph": True,
    }


@responses.activate
def test_fetch_raw_returns_bytes(client: Spectron):
    responses.add(
        responses.GET,
        f"{DOCS}/doc%3A1/raw",
        body=b"%PDF-1.7 ...",
        status=200,
        content_type="application/pdf",
    )
    data = client.documents.fetch_raw("doc:1")
    assert data == b"%PDF-1.7 ..."


@responses.activate
def test_reprocess_and_recompute(client: Spectron):
    responses.add(
        responses.PUT,
        f"{DOCS}/doc%3A1",
        json={
            "contentHash": "h",
            "deduplicated": False,
            "id": "doc:1",
            "status": "Embedding",
        },
        status=202,
    )
    responses.add(
        responses.POST,
        f"{DOCS}/recompute-links",
        json={"linksEmitted": 3},
        status=200,
    )
    up = client.documents.reprocess("doc:1")
    assert isinstance(up, UploadResponse)
    assert up.status == "Embedding"
    rc = client.documents.recompute_links()
    assert isinstance(rc, RecomputeLinksResponse)
    assert rc.links_emitted == 3


@responses.activate
def test_chunks(client: Spectron):
    responses.add(
        responses.GET,
        f"{DOCS}/doc%3A1/chunks",
        json={
            "chunks": [
                {
                    "id": "c:1",
                    "document": "doc:1",
                    "charStart": 0,
                    "charEnd": 5,
                    "position": 0,
                    "text": "hello",
                }
            ],
            "page": 1,
            "pageSize": 50,
            "total": 1,
        },
        status=200,
    )
    page = client.documents.chunks("doc:1", page=1, page_size=50)
    assert isinstance(page, ChunkPage)
    assert page.chunks[0].text == "hello"


@responses.activate
def test_keyword_subnamespace(client: Spectron):
    responses.add(
        responses.GET,
        f"{DOCS}/keywords",
        json={
            "keywords": [
                {
                    "id": "kw:1",
                    "documentCount": 2,
                    "normalised": "return",
                    "text": "returns",
                }
            ],
            "page": 1,
            "pageSize": 20,
            "total": 1,
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{DOCS}/keywords/return",
        json={
            "id": "kw:1",
            "documentCount": 2,
            "normalised": "return",
            "text": "returns",
            "documents": [],
        },
        status=200,
    )
    responses.add(
        responses.POST,
        f"{DOCS}/keywords/search",
        json={
            "queryMs": 2,
            "results": [
                {
                    "id": "kw:1",
                    "documentCount": 2,
                    "normalised": "return",
                    "score": 0.8,
                    "text": "returns",
                }
            ],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{DOCS}/doc%3A1/keywords",
        json={
            "keywords": [
                {"id": "kw:1", "normalised": "return", "score": 0.8, "text": "returns"}
            ]
        },
        status=200,
    )
    page = client.documents.keywords.list(q="ret", min_document_count=1)
    assert isinstance(page, KeywordPage)
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert qs["q"] == ["ret"]
    assert qs["minDocumentCount"] == ["1"]
    detail = client.documents.keywords.get("return")
    assert isinstance(detail, KeywordDetail)
    hits = client.documents.keywords.search("returns", k=5)
    assert isinstance(hits, KeywordSearchResponse)
    assert hits.results[0].score == 0.8
    for_doc = client.documents.keywords.for_document("doc:1")
    assert isinstance(for_doc, DocumentKeywordsResponse)
    assert for_doc.keywords[0].text == "returns"
