"""Type stubs for the _surrealdb_ext Rust extension module."""

from typing import Any

class AsyncEmbeddedDB:
    """Async embedded SurrealDB database instance."""

    def __init__(self, url: str) -> None:
        """Initialize the async embedded database.

        Args:
            url: Database URL (mem:// or file://).
        """
        ...

    async def __aenter__(self) -> AsyncEmbeddedDB: ...
    async def __aexit__(
        self, exc_type: Any, exc_value: Any, traceback: Any
    ) -> None: ...
    async def connect(self) -> None:
        """Connect to the database."""
        ...

    async def close(self) -> None:
        """Close the database connection."""
        ...

    async def execute(self, cbor_request: bytes) -> bytes:
        """Execute a CBOR-encoded request and return a CBOR-encoded response.

        Args:
            cbor_request: CBOR-encoded request containing method and params.

        Returns:
            CBOR-encoded response containing id and result.
        """
        ...

class SyncEmbeddedDB:
    """Blocking embedded SurrealDB database instance."""

    def __init__(self, url: str) -> None:
        """Initialize the blocking embedded database.

        Args:
            url: Database URL (mem:// or file://).
        """
        ...

    def __enter__(self) -> SyncEmbeddedDB: ...
    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None: ...
    def connect(self) -> None:
        """Connect to the database."""
        ...

    def close(self) -> None:
        """Close the database connection."""
        ...

    def execute(self, cbor_request: bytes) -> bytes:
        """Execute a CBOR-encoded request and return a CBOR-encoded response.

        Args:
            cbor_request: CBOR-encoded request containing method and params.

        Returns:
            CBOR-encoded response containing id and result.
        """
        ...
