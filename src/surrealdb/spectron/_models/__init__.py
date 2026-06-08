from __future__ import annotations

from surrealdb.spectron._models.common import Model
from surrealdb.spectron._models.documents import (
    Chunk,
    ChunkPage,
    Document,
    DocumentKeyword,
    DocumentKeywordsResponse,
    DocumentPage,
    DocumentQueryHit,
    DocumentQueryResponse,
    Keyword,
    KeywordDetail,
    KeywordPage,
    KeywordSearchHit,
    KeywordSearchResponse,
    RecomputeLinksResponse,
    UploadResponse,
)
from surrealdb.spectron._models.entities import (
    AttributeDetail,
    EntityDetail,
    EntityHistoryResponse,
    EntityListResponse,
    EntityResponse,
    RelationDetail,
)
from surrealdb.spectron._models.keys import KeyDetail, MintedKey
from surrealdb.spectron._models.lifecycle import FsckReport, LifecycleResponse
from surrealdb.spectron._models.memory import (
    ChatResponse,
    ConsolidateOutcome,
    ConsolidateResponse,
    ContextQueryResponse,
    ElaborateOutcome,
    ElaborateResponse,
    ExtractionResult,
    ForgetResponse,
    RecallHit,
    RecallResponse,
    ReflectResponse,
    RememberBatchResponse,
    RememberResponse,
    StateResponse,
)
from surrealdb.spectron._models.principals import (
    EffectiveGrants,
    Principal,
    ProfileEntry,
    ProfileResponse,
    WhoamiResponse,
)
from surrealdb.spectron._models.scopes import ForgetScopeResponse, ScopeNode
from surrealdb.spectron._models.sessions import (
    Session,
    SessionContextResponse,
    Turn,
    TurnListResponse,
)
from surrealdb.spectron._models.traces import (
    AuditResponse,
    AuditRow,
    TraceListResponse,
    TraceRecord,
    TraceStatsResponse,
)

__all__ = [
    "Model",
    # memory
    "ExtractionResult",
    "RememberResponse",
    "RememberBatchResponse",
    "RecallHit",
    "RecallResponse",
    "ChatResponse",
    "ForgetResponse",
    "ConsolidateOutcome",
    "ConsolidateResponse",
    "ReflectResponse",
    "ElaborateOutcome",
    "ElaborateResponse",
    "ContextQueryResponse",
    "StateResponse",
    # documents
    "UploadResponse",
    "Document",
    "DocumentPage",
    "Chunk",
    "ChunkPage",
    "DocumentQueryHit",
    "DocumentQueryResponse",
    "RecomputeLinksResponse",
    "DocumentKeyword",
    "DocumentKeywordsResponse",
    "Keyword",
    "KeywordPage",
    "KeywordDetail",
    "KeywordSearchHit",
    "KeywordSearchResponse",
    # sessions
    "Session",
    "SessionContextResponse",
    "Turn",
    "TurnListResponse",
    # entities
    "EntityDetail",
    "AttributeDetail",
    "RelationDetail",
    "EntityResponse",
    "EntityListResponse",
    "EntityHistoryResponse",
    # scopes
    "ScopeNode",
    "ForgetScopeResponse",
    # principals
    "Principal",
    "EffectiveGrants",
    "WhoamiResponse",
    "ProfileEntry",
    "ProfileResponse",
    # keys
    "MintedKey",
    "KeyDetail",
    # traces
    "TraceRecord",
    "TraceListResponse",
    "TraceStatsResponse",
    "AuditRow",
    "AuditResponse",
    # lifecycle
    "LifecycleResponse",
    "FsckReport",
]
