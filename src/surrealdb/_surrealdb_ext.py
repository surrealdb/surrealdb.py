"""
Compatibility shim for the embedded engine.

The `surrealdb` default distribution is pure-Python (fast install, no Rust build).
If users opt-in to embedded support via `surrealdb[embedded]`, the companion
package `surrealdb-embedded` provides the compiled extension as
`surrealdb_embedded._surrealdb_ext`.
"""

from __future__ import annotations

try:
    from surrealdb_embedded._surrealdb_ext import AsyncEmbeddedDB, SyncEmbeddedDB  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError(
        "Embedded SurrealDB engine is not installed. Install it with "
        '`pip install "surrealdb[embedded]"` (or `uv add "surrealdb[embedded]"`).'
    ) from e

__all__ = ["AsyncEmbeddedDB", "SyncEmbeddedDB"]


