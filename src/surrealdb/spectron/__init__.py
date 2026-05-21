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
    ChatResponse,
    ExtractionResult,
    ForgetResponse,
    RecallHit,
    RecallResponse,
    RememberBatchResponse,
    RememberResponse,
    UploadResponse,
)
from surrealdb.spectron._namespaces.documents import (
    AsyncDocuments,
    BlockingDocuments,
)
from surrealdb.spectron._streaming import ChatChunk
from surrealdb.spectron._transport import AsyncTransport, BlockingTransport

__all__ = [
    "Spectron",
    "AsyncSpectron",
    "BlockingTransport",
    "AsyncTransport",
    "BlockingDocuments",
    "AsyncDocuments",
    "SpectronError",
    "SpectronAPIError",
    "SpectronAuthError",
    "SpectronScopeError",
    "SpectronNotFoundError",
    "ChatChunk",
    "ChatResponse",
    "ExtractionResult",
    "ForgetResponse",
    "RecallHit",
    "RecallResponse",
    "RememberBatchResponse",
    "RememberResponse",
    "UploadResponse",
]
