class SurrealException(Exception):
    """Base exception for SurrealDB client library."""


class SurrealAuthenticationException(SurrealException):
    """Exception raised for errors with SurrealDB authentication."""


class SurrealPermissionException(SurrealException):
    """Exception raised for errors with SurrealDB permissions."""
