from __future__ import annotations

import dataclasses
import enum
import types
import typing
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeVar, get_args, get_origin

_UNION_ORIGINS: tuple[Any, ...] = (typing.Union, types.UnionType)

T = TypeVar("T", bound="Model")


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)


def _wire_name(f: dataclasses.Field[Any]) -> str:
    override = f.metadata.get("json") if f.metadata else None
    if isinstance(override, str) and override:
        return override
    return _to_camel(f.name)


class Model:
    __resolved_hints__: ClassVar[dict[str, Any]] = {}

    @classmethod
    def _hints(cls) -> dict[str, Any]:
        cached = cls.__dict__.get("__resolved_hints__")
        if cached is None:
            cached = typing.get_type_hints(cls)
            cls.__resolved_hints__ = cached
        return cached

    @classmethod
    def from_dict(cls: type[T], data: Any) -> T:
        if data is None or not isinstance(data, dict):
            raise TypeError(f"Cannot decode {cls.__name__} from {type(data).__name__}")
        hints = cls._hints()
        kwargs: dict[str, Any] = {}
        seen_required = 0
        required_fields = 0
        for f in dataclasses.fields(cls):  # type: ignore[arg-type]
            wire_key = _wire_name(f)
            field_type = hints.get(f.name, f.type)
            has_default = (
                f.default is not dataclasses.MISSING
                or f.default_factory is not dataclasses.MISSING
            )
            if not has_default:
                required_fields += 1
            if wire_key in data:
                raw = data[wire_key]
            elif f.name in data:
                raw = data[f.name]
            elif not has_default:
                raise ValueError(
                    f"Missing required field '{wire_key}' for {cls.__name__}"
                )
            else:
                continue
            kwargs[f.name] = _decode(field_type, raw)
            if not has_default:
                seen_required += 1
        if seen_required < required_fields:
            missing = [
                f.name
                for f in dataclasses.fields(cls)  # type: ignore[arg-type]
                if f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING
                and f.name not in kwargs
            ]
            if missing:
                raise ValueError(
                    f"Missing required fields {missing!r} for {cls.__name__}"
                )
        return cls(**kwargs)

    def to_dict(self, *, omit_none: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in dataclasses.fields(self):  # type: ignore[arg-type]
            value = getattr(self, f.name)
            if value is None and omit_none:
                continue
            out[_wire_name(f)] = _encode(value)
        return out


def _decode(type_hint: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(type_hint)
    if origin in _UNION_ORIGINS:
        args = [a for a in get_args(type_hint) if a is not type(None)]
        if not args:
            return value
        for candidate in args:
            try:
                return _decode(candidate, value)
            except (TypeError, ValueError):
                continue
        return value
    if origin in (list, tuple):
        if not isinstance(value, (list, tuple)):
            return value
        inner_args = get_args(type_hint)
        inner = inner_args[0] if inner_args else Any
        return [_decode(inner, v) for v in value]
    if origin is dict:
        if not isinstance(value, dict):
            return value
        dict_args = get_args(type_hint)
        v_type = dict_args[1] if len(dict_args) == 2 else Any
        return {k: _decode(v_type, v) for k, v in value.items()}
    if isinstance(type_hint, type):
        if issubclass(type_hint, Model) and isinstance(value, dict):
            return type_hint.from_dict(value)
        if issubclass(type_hint, enum.Enum):
            try:
                return type_hint(value)
            except ValueError:
                return value
    return value


def _encode(value: Any) -> Any:
    if isinstance(value, Model):
        return value.to_dict()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    return value


class QueryMode(str, enum.Enum):
    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"
    HYBRID_GRAPH = "hybrid_graph"


class DocumentStatus(str, enum.Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    RENDERING = "rendering"
    TRANSCRIBING = "transcribing"
    CAPTIONING = "captioning"
    KEYWORDING = "keywording"
    READY = "ready"
    FAILED = "failed"


class IngestProfile(str, enum.Enum):
    TEXT_ONLY = "text_only"
    TEXT_PLUS_OCR = "text_plus_ocr"
    MULTIMODAL_BALANCED = "multimodal_balanced"
    MULTIMODAL_FULL = "multimodal_full"


class TurnRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MemoryCategory(str, enum.Enum):
    IDENTITY = "identity"
    KNOWLEDGE = "knowledge"
    CONTEXT = "context"
    INSTRUCTION = "instruction"
    UNCERTAINTY = "uncertainty"


@dataclass(slots=True)
class ChunkJson(Model):
    char_end: int
    char_start: int
    document: str
    id: str
    position: int
    text: str
    section: str | None = None
    token_count: int | None = None


@dataclass(slots=True)
class ChunkPageJson(Model):
    chunks: list[ChunkJson]
    page: int
    page_size: int
    total: int


@dataclass(slots=True)
class DocumentJson(Model):
    content_hash: str
    created_at: str
    id: str
    mime_type: str
    size_bytes: int
    source: str
    status: str
    title: str
    updated_at: str
    version: int
    chunk_count: int | None = None
    error: str | None = None
    keyword_count: int | None = None
    language: str | None = None
    processing_completed_at: str | None = None
    processing_started_at: str | None = None


@dataclass(slots=True)
class DocumentPageJson(Model):
    documents: list[DocumentJson]
    page: int
    page_size: int
    total: int


@dataclass(slots=True)
class DocumentKeywordJson(Model):
    id: str
    normalised: str
    score: float
    text: str


@dataclass(slots=True)
class DocumentKeywordsResponse(Model):
    keywords: list[DocumentKeywordJson]


@dataclass(slots=True)
class KeywordJson(Model):
    document_count: int
    id: str
    normalised: str
    text: str


@dataclass(slots=True)
class KeywordPageJson(Model):
    keywords: list[KeywordJson]
    page: int
    page_size: int
    total: int


@dataclass(slots=True)
class KeywordDocumentJson(Model):
    id: str
    score: float
    title: str


@dataclass(slots=True)
class KeywordDetailJson(Model):
    document_count: int
    documents: list[KeywordDocumentJson]
    id: str
    normalised: str
    text: str


@dataclass(slots=True)
class KeywordSearchHitJson(Model):
    document_count: int
    id: str
    normalised: str
    score: float
    text: str


@dataclass(slots=True)
class KeywordSearchResponseJson(Model):
    query_ms: int
    results: list[KeywordSearchHitJson]


@dataclass(slots=True)
class KnowledgeLinkTarget(Model):
    kind: str
    slug: str


@dataclass(slots=True)
class KnowledgeLinkUpsert(Model):
    label: str
    to: KnowledgeLinkTarget


@dataclass(slots=True)
class KnowledgeNodeUpsertRow(Model):
    kind: str
    slug: str
    title: str
    content: dict[str, Any] | None = None
    links: list[KnowledgeLinkUpsert] | None = None
    source_document: str | None = None


@dataclass(slots=True)
class KnowledgeSummaryJson(Model):
    id: str
    kind: str
    title: str


@dataclass(slots=True)
class KnowledgeNodeListedJson(Model):
    content: dict[str, Any]
    created_at: str
    id: str
    kind: str
    scope: list[str]
    title: str
    updated_at: str
    source_document: str | None = None


@dataclass(slots=True)
class KnowledgeNodeFullJson(Model):
    content: dict[str, Any]
    created_at: str
    embedding: list[float]
    id: str
    kind: str
    scope: list[str]
    title: str
    updated_at: str
    source_document: str | None = None


@dataclass(slots=True)
class KnowledgeNodePageJson(Model):
    nodes: list[KnowledgeNodeListedJson]
    page: int
    page_size: int
    total: int


@dataclass(slots=True)
class KnowledgeNodeSearchHitJson(Model):
    node: KnowledgeSummaryJson
    score: float


@dataclass(slots=True)
class KnowledgeNodeSearchResponseJson(Model):
    query_ms: int
    results: list[KnowledgeNodeSearchHitJson]


@dataclass(slots=True)
class QueryFilter(Model):
    document_ids: list[str] | None = None
    mime_type: list[str] | None = None


@dataclass(slots=True)
class QueryHitChunkJson(Model):
    char_end: int
    char_start: int
    document: str
    id: str
    position: int
    text: str
    section: str | None = None


@dataclass(slots=True)
class QueryHitDocumentJson(Model):
    id: str
    source: str
    title: str


@dataclass(slots=True)
class GraphEvidenceJson(Model):
    edge_kind: str
    neighbour_label: str
    weight: float


@dataclass(slots=True)
class QueryHitJson(Model):
    chunk: QueryHitChunkJson
    document: QueryHitDocumentJson
    score: float
    graph_evidence: list[GraphEvidenceJson] | None = None
    graph_expansion: dict[str, Any] | None = None


@dataclass(slots=True)
class QueryResponseJson(Model):
    query_ms: int
    results: list[QueryHitJson]


@dataclass(slots=True)
class TraverseStartJson(Model):
    type: str
    id: str | None = None
    normalised: str | None = None
    kind: str | None = None
    slug: str | None = None


@dataclass(slots=True)
class TraverseNodeJson(Model):
    depth: int
    id: str
    type: str
    kind: str | None = None
    normalised: str | None = None
    title: str | None = None


@dataclass(slots=True)
class TraverseEdgeJson(Model):
    kind: str
    label: str | None = None
    score: float | None = None
    from_: str = field(metadata={"json": "from"}, default="")
    to: str = ""


@dataclass(slots=True)
class TraverseApiResponse(Model):
    edges: list[TraverseEdgeJson]
    nodes: list[TraverseNodeJson]


@dataclass(slots=True)
class UploadResponse(Model):
    content_hash: str
    deduplicated: bool
    id: str
    status: str


@dataclass(slots=True)
class SessionInfo(Model):
    id: str
    scope: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None
    created_at: str | None = None


@dataclass(slots=True)
class Turn(Model):
    role: TurnRole
    content: str
    id: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class EntityRef(Model):
    type: str
    name: str


@dataclass(slots=True)
class AttributeUpdate(Model):
    entity: EntityRef
    key: str
    value: Any
    category: MemoryCategory | None = None
    confidence: float | None = None


@dataclass(slots=True)
class RelationUpdate(Model):
    label: str
    source: EntityRef
    target: EntityRef
    confidence: float | None = None


@dataclass(slots=True)
class ExtractionResult(Model):
    entities: list[EntityRef] | None = None
    attributes: list[AttributeUpdate] | None = None
    relations: list[RelationUpdate] | None = None
    instructions: list[str] | None = None
    uncertainties: list[str] | None = None
    corrections: list[dict[str, Any]] | None = None
    turn_id: str | None = None


@dataclass(slots=True)
class ChatReply(Model):
    reply: str
    memory_updates: ExtractionResult | None = None
    turn_id: str | None = None


@dataclass(slots=True)
class ContextResult(Model):
    context: str
    tier: str | None = None
    query_ms: int | None = None


@dataclass(slots=True)
class MemoryHit(Model):
    source: str
    score: float
    text: str | None = None
    id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class MemoryQueryResponse(Model):
    hits: list[MemoryHit]
    tier: str | None = None
    query_ms: int | None = None
    trace: dict[str, Any] | None = None


@dataclass(slots=True)
class StructuredState(Model):
    identity: dict[str, Any] | None = None
    knowledge: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    instructions: list[str] | None = None
    unknowns: list[str] | None = None


@dataclass(slots=True)
class ProfileResponse(Model):
    static: dict[str, Any] | None = None
    dynamic: dict[str, Any] | None = None
    preferences: dict[str, Any] | None = None
    instructions: list[str] | None = None


@dataclass(slots=True)
class Entity(Model):
    type: str
    name: str
    attributes: dict[str, Any] | None = None
    scope: dict[str, str] | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class EntityHistoryEntry(Model):
    value: Any
    valid_from: str | None = None
    valid_until: str | None = None
    source_turn: str | None = None


@dataclass(slots=True)
class ReflectionResult(Model):
    reflection: str
    evidence: list[dict[str, Any]] | None = None
    persisted_attributes: list[AttributeUpdate] | None = None


@dataclass(slots=True)
class ForgetResult(Model):
    deleted: int


@dataclass(slots=True)
class TraceRecord(Model):
    id: str
    resolution_tier: str | None = None
    latency_ms: int | None = None
    cached: bool | None = None
    retrieved_count: int | None = None
    top_scores: list[float] | None = None
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class TraceListResponse(Model):
    traces: list[TraceRecord]


@dataclass(slots=True)
class TraceStats(Model):
    total_queries: int | None = None
    cache_hits: int | None = None
    avg_latency_ms: float | None = None
    tier_counts: dict[str, int] | None = None


__all__ = [
    "QueryMode",
    "DocumentStatus",
    "IngestProfile",
    "TurnRole",
    "MemoryCategory",
    "Model",
    "ChunkJson",
    "ChunkPageJson",
    "DocumentJson",
    "DocumentPageJson",
    "DocumentKeywordJson",
    "DocumentKeywordsResponse",
    "KeywordJson",
    "KeywordPageJson",
    "KeywordDocumentJson",
    "KeywordDetailJson",
    "KeywordSearchHitJson",
    "KeywordSearchResponseJson",
    "KnowledgeLinkTarget",
    "KnowledgeLinkUpsert",
    "KnowledgeNodeUpsertRow",
    "KnowledgeSummaryJson",
    "KnowledgeNodeListedJson",
    "KnowledgeNodeFullJson",
    "KnowledgeNodePageJson",
    "KnowledgeNodeSearchHitJson",
    "KnowledgeNodeSearchResponseJson",
    "QueryFilter",
    "QueryHitChunkJson",
    "QueryHitDocumentJson",
    "GraphEvidenceJson",
    "QueryHitJson",
    "QueryResponseJson",
    "TraverseStartJson",
    "TraverseNodeJson",
    "TraverseEdgeJson",
    "TraverseApiResponse",
    "UploadResponse",
    "SessionInfo",
    "Turn",
    "EntityRef",
    "AttributeUpdate",
    "RelationUpdate",
    "ExtractionResult",
    "ChatReply",
    "ContextResult",
    "MemoryHit",
    "MemoryQueryResponse",
    "StructuredState",
    "ProfileResponse",
    "Entity",
    "EntityHistoryEntry",
    "ReflectionResult",
    "ForgetResult",
    "TraceRecord",
    "TraceListResponse",
    "TraceStats",
]
