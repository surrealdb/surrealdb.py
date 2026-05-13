from __future__ import annotations


def test_top_level_clients_importable():
    from surrealdb import AsyncSpectron, Spectron

    assert Spectron.__name__ == "Spectron"
    assert AsyncSpectron.__name__ == "AsyncSpectron"


def test_top_level_exception_aliases_importable():
    from surrealdb import (
        SpectronAuthError,
        SpectronError,
        SpectronNotFoundError,
        SpectronRateLimitError,
        SpectronScopeError,
        SpectronServerError,
        SpectronValidationError,
    )

    for cls in (
        SpectronAuthError,
        SpectronNotFoundError,
        SpectronRateLimitError,
        SpectronScopeError,
        SpectronServerError,
        SpectronValidationError,
    ):
        assert issubclass(cls, SpectronError)


def test_top_level_enums_importable():
    from surrealdb import (
        SpectronDocumentStatus,
        SpectronIngestProfile,
        SpectronMemoryCategory,
        SpectronQueryMode,
        SpectronTurnRole,
    )

    assert SpectronQueryMode("hybrid").value == "hybrid"
    assert SpectronDocumentStatus("ready").value == "ready"
    assert SpectronIngestProfile("text_only").value == "text_only"
    assert SpectronTurnRole("user").value == "user"
    assert SpectronMemoryCategory("identity").value == "identity"


def test_management_surface_is_gone():
    import surrealdb
    import surrealdb.spectron as spx

    for name in (
        "SpectronManagement",
        "AsyncSpectronManagement",
        "SpectronPrincipalType",
    ):
        assert not hasattr(surrealdb, name), f"surrealdb still exposes {name}"
    for name in (
        "SpectronManagement",
        "AsyncSpectronManagement",
        "PrincipalType",
        "ContextConfig",
        "ContextResponse",
        "CreatedApiKey",
    ):
        assert not hasattr(spx, name), f"surrealdb.spectron still exposes {name}"


def test_subpackage_exports():
    import surrealdb.spectron as spx

    for name in (
        "Spectron",
        "AsyncSpectron",
        "SpectronError",
        "AuthError",
        "ScopeError",
        "NotFoundError",
        "ValidationError",
        "RateLimitError",
        "ServerError",
        "QueryMode",
        "DocumentStatus",
        "IngestProfile",
        "TurnRole",
        "MemoryCategory",
        "serialise_scope",
        "deserialise_scope",
    ):
        assert hasattr(spx, name), f"surrealdb.spectron missing {name}"


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
