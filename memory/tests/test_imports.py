"""The public surface of ``surrealdb_memory``.

Two tests that used to live here asserted things about the *core* SDK's
namespace - that ``surrealdb`` does not re-export these names, and that its own
exports still work. Those moved to ``tests/unit_tests/test_memory_shim.py`` in
the SDK when this package was split out: the boundary belongs to whichever side
owns the shim, and an addon test suite that imports ``surrealdb`` to make
assertions about it would couple the two back together.
"""

from __future__ import annotations


def test_clients_importable() -> None:
    from surrealdb_memory import AsyncMemory, Memory

    assert Memory.__name__ == "Memory"
    assert AsyncMemory.__name__ == "AsyncMemory"


def test_exception_hierarchy() -> None:
    from surrealdb_memory import (
        MemoryAPIError,
        MemoryAuthError,
        MemoryNotFoundError,
        MemoryScopeError,
        MemoryServiceError,
    )

    assert issubclass(MemoryAPIError, MemoryServiceError)
    for cls in (MemoryAuthError, MemoryNotFoundError, MemoryScopeError):
        assert issubclass(cls, MemoryAPIError)


def test_the_base_error_does_not_shadow_the_builtin() -> None:
    """``MemoryError`` is a Python builtin, so the base error must not take it.

    Naming it ``MemoryError`` would mean a caller's ``except MemoryError:`` no
    longer catches an interpreter out-of-memory, and a real service failure
    would not be caught by code expecting the builtin - the two classes are
    unrelated, so both directions fail silently.
    """
    import builtins

    import surrealdb_memory

    assert not hasattr(surrealdb_memory, "MemoryError")
    assert not issubclass(surrealdb_memory.MemoryServiceError, builtins.MemoryError)


def test_package_exports() -> None:
    import surrealdb_memory as mem

    for name in (
        "Memory",
        "AsyncMemory",
        "BlockingTransport",
        "AsyncTransport",
        "BlockingDocuments",
        "AsyncDocuments",
        "MemoryServiceError",
        "MemoryAPIError",
        "MemoryAuthError",
        "MemoryScopeError",
        "MemoryNotFoundError",
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
        assert hasattr(mem, name), f"surrealdb_memory missing {name}"


def test_old_namespaces_are_gone() -> None:
    import surrealdb_memory as mem

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
        assert not hasattr(mem, name), f"surrealdb_memory still exposes {name}"
