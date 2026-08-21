from __future__ import annotations

from surrealdb_memory._models.common import Model
from surrealdb_memory._models.documents import (
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
from surrealdb_memory._models.entities import (
    AttributeDetail,
    EntityDetail,
    EntityHistoryResponse,
    EntityListResponse,
    EntityResponse,
    RelationDetail,
)
from surrealdb_memory._models.keys import KeyDetail, MintedKey
from surrealdb_memory._models.lifecycle import FsckReport, LifecycleResponse
from surrealdb_memory._models.memory import (
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
from surrealdb_memory._models.principals import (
    EffectiveGrants,
    Principal,
    ProfileEntry,
    ProfileResponse,
    WhoamiResponse,
)
from surrealdb_memory._models.scopes import ForgetScopeResponse, ScopeNode
from surrealdb_memory._models.sessions import (
    Session,
    SessionContextResponse,
    Turn,
    TurnListResponse,
)
from surrealdb_memory._models.traces import (
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
