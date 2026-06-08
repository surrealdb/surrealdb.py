from __future__ import annotations

from surrealdb.spectron._client import AsyncSpectron, Spectron
from surrealdb.spectron._errors import (
    SpectronAPIError,
    SpectronAuthError,
    SpectronError,
    SpectronNotFoundError,
    SpectronScopeError,
)
from surrealdb.spectron._models import (
    AttributeDetail,
    AuditResponse,
    AuditRow,
    ChatResponse,
    Chunk,
    ChunkPage,
    ConsolidateOutcome,
    ConsolidateResponse,
    ContextQueryResponse,
    Document,
    DocumentKeyword,
    DocumentKeywordsResponse,
    DocumentPage,
    DocumentQueryHit,
    DocumentQueryResponse,
    EffectiveGrants,
    ElaborateOutcome,
    ElaborateResponse,
    EntityDetail,
    EntityHistoryResponse,
    EntityListResponse,
    EntityResponse,
    ExtractionResult,
    ForgetResponse,
    ForgetScopeResponse,
    FsckReport,
    KeyDetail,
    Keyword,
    KeywordDetail,
    KeywordPage,
    KeywordSearchHit,
    KeywordSearchResponse,
    LifecycleResponse,
    MintedKey,
    Principal,
    ProfileEntry,
    ProfileResponse,
    RecallHit,
    RecallResponse,
    RecomputeLinksResponse,
    ReflectResponse,
    RelationDetail,
    RememberBatchResponse,
    RememberResponse,
    ScopeNode,
    Session,
    SessionContextResponse,
    StateResponse,
    TraceListResponse,
    TraceRecord,
    TraceStatsResponse,
    Turn,
    TurnListResponse,
    UploadResponse,
    WhoamiResponse,
)
from surrealdb.spectron._namespaces.documents import (
    AsyncDocumentKeywords,
    AsyncDocuments,
    BlockingDocumentKeywords,
    BlockingDocuments,
)
from surrealdb.spectron._namespaces.entities import AsyncEntities, BlockingEntities
from surrealdb.spectron._namespaces.keys import AsyncKeys, BlockingKeys
from surrealdb.spectron._namespaces.lifecycle import (
    AsyncLifecycle,
    BlockingLifecycle,
)
from surrealdb.spectron._namespaces.principals import (
    AsyncPrincipals,
    BlockingPrincipals,
)
from surrealdb.spectron._namespaces.scopes import AsyncScopes, BlockingScopes
from surrealdb.spectron._namespaces.sessions import AsyncSessions, BlockingSessions
from surrealdb.spectron._namespaces.traces import AsyncTraces, BlockingTraces
from surrealdb.spectron._scope import ScopeArg
from surrealdb.spectron._streaming import ChatChunk
from surrealdb.spectron._transport import AsyncTransport, BlockingTransport

__all__ = [
    # clients
    "Spectron",
    "AsyncSpectron",
    "ScopeArg",
    # transports
    "BlockingTransport",
    "AsyncTransport",
    # namespaces
    "BlockingDocuments",
    "AsyncDocuments",
    "BlockingDocumentKeywords",
    "AsyncDocumentKeywords",
    "BlockingSessions",
    "AsyncSessions",
    "BlockingEntities",
    "AsyncEntities",
    "BlockingScopes",
    "AsyncScopes",
    "BlockingPrincipals",
    "AsyncPrincipals",
    "BlockingKeys",
    "AsyncKeys",
    "BlockingTraces",
    "AsyncTraces",
    "BlockingLifecycle",
    "AsyncLifecycle",
    # errors
    "SpectronError",
    "SpectronAPIError",
    "SpectronAuthError",
    "SpectronScopeError",
    "SpectronNotFoundError",
    # streaming
    "ChatChunk",
    # models — memory
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
    # models — documents
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
    # models — sessions
    "Session",
    "SessionContextResponse",
    "Turn",
    "TurnListResponse",
    # models — entities
    "EntityDetail",
    "AttributeDetail",
    "RelationDetail",
    "EntityResponse",
    "EntityListResponse",
    "EntityHistoryResponse",
    # models — scopes
    "ScopeNode",
    "ForgetScopeResponse",
    # models — principals
    "Principal",
    "EffectiveGrants",
    "WhoamiResponse",
    "ProfileEntry",
    "ProfileResponse",
    # models — keys
    "MintedKey",
    "KeyDetail",
    # models — traces
    "TraceRecord",
    "TraceListResponse",
    "TraceStatsResponse",
    "AuditRow",
    "AuditResponse",
    # models — lifecycle
    "LifecycleResponse",
    "FsckReport",
]
