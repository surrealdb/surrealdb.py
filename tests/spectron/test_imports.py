from __future__ import annotations


def test_top_level_clients_importable():
    from surrealdb import AsyncSpectron, Spectron

    assert Spectron.__name__ == "Spectron"
    assert AsyncSpectron.__name__ == "AsyncSpectron"


def test_top_level_exception_aliases_importable():
    from surrealdb import (
        SpectronAPIError,
        SpectronAuthError,
        SpectronError,
        SpectronNotFoundError,
        SpectronScopeError,
    )

    assert issubclass(SpectronAPIError, SpectronError)
    for cls in (SpectronAuthError, SpectronNotFoundError, SpectronScopeError):
        assert issubclass(cls, SpectronAPIError)


def test_removed_aliases_no_longer_exposed():
    import surrealdb

    for name in (
        "SpectronValidationError",
        "SpectronRateLimitError",
        "SpectronServerError",
        "SpectronQueryMode",
        "SpectronDocumentStatus",
        "SpectronIngestProfile",
        "SpectronTurnRole",
        "SpectronMemoryCategory",
    ):
        assert not hasattr(surrealdb, name), f"surrealdb still exposes {name}"


def test_subpackage_exports():
    import surrealdb.spectron as spx

    for name in (
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
    ):
        assert hasattr(spx, name), f"surrealdb.spectron missing {name}"


def test_old_namespaces_are_gone():
    import surrealdb.spectron as spx

    for name in (
        "knowledge",
        "memory",
        "AuthError",
        "NotFoundError",
        "ScopeError",
        "ValidationError",
        "RateLimitError",
        "ServerError",
        "QueryMode",
        "DocumentStatus",
        "serialise_scope",
        "deserialise_scope",
    ):
        assert not hasattr(spx, name), f"surrealdb.spectron still exposes {name}"


def test_existing_surrealdb_exports_still_work():
    from surrealdb import (
        AsyncSurreal,
        RecordID,
        Surreal,
        SurrealError,
        Table,
    )

    assert callable(Surreal)
    assert callable(AsyncSurreal)
    assert RecordID.__name__ == "RecordID"
    assert Table.__name__ == "Table"
    assert issubclass(SurrealError, Exception)
