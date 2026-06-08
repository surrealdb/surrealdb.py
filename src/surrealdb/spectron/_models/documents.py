from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class UploadResponse(Model):
    content_hash: str
    deduplicated: bool
    id: str
    status: str


@dataclass(slots=True)
class Document(Model):
    """A document row. Timestamps ride the wire as ISO-8601 strings and are
    surfaced verbatim (no datetime parsing) to keep the model dependency-free.
    """

    id: str
    content_hash: str = ""
    created_at: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    source: str = ""
    status: str = ""
    title: str = ""
    updated_at: str = ""
    version: int = 0
    chunk_count: int | None = None
    error: str | None = None
    keyword_count: int | None = None
    language: str | None = None
    processing_completed_at: str | None = None
    processing_started_at: str | None = None


@dataclass(slots=True)
class DocumentPage(Model):
    documents: list[Document] = field(default_factory=list)
    page: int = 0
    page_size: int = 0
    total: int = 0


@dataclass(slots=True)
class Chunk(Model):
    id: str
    document: str = ""
    char_start: int = 0
    char_end: int = 0
    position: int = 0
    text: str = ""
    section: str | None = None
    token_count: int | None = None


@dataclass(slots=True)
class ChunkPage(Model):
    chunks: list[Chunk] = field(default_factory=list)
    page: int = 0
    page_size: int = 0
    total: int = 0


@dataclass(slots=True)
class DocumentQueryHit(Model):
    """One chunk-level hit from ``documents.query``. The chunk/document rows
    and any graph evidence stay loose dicts per the slim-model convention.
    """

    score: float = 0.0
    chunk: dict[str, Any] = field(default_factory=dict)
    document: dict[str, Any] = field(default_factory=dict)
    graph_evidence: list[dict[str, Any]] | None = None


@dataclass(slots=True)
class DocumentQueryResponse(Model):
    query_ms: int = 0
    results: list[DocumentQueryHit] = field(default_factory=list)


@dataclass(slots=True)
class RecomputeLinksResponse(Model):
    links_emitted: int = 0


@dataclass(slots=True)
class DocumentKeyword(Model):
    id: str
    normalised: str = ""
    score: float = 0.0
    text: str = ""


@dataclass(slots=True)
class DocumentKeywordsResponse(Model):
    keywords: list[DocumentKeyword] = field(default_factory=list)


@dataclass(slots=True)
class Keyword(Model):
    id: str
    document_count: int = 0
    normalised: str = ""
    text: str = ""


@dataclass(slots=True)
class KeywordPage(Model):
    keywords: list[Keyword] = field(default_factory=list)
    page: int = 0
    page_size: int = 0
    total: int = 0


@dataclass(slots=True)
class KeywordDetail(Model):
    id: str
    document_count: int = 0
    normalised: str = ""
    text: str = ""
    documents: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class KeywordSearchHit(Model):
    id: str
    document_count: int = 0
    normalised: str = ""
    score: float = 0.0
    text: str = ""


@dataclass(slots=True)
class KeywordSearchResponse(Model):
    query_ms: int = 0
    results: list[KeywordSearchHit] = field(default_factory=list)
