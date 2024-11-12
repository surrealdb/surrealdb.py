class SurrealDbError(Exception):
    """Base class for exceptions in this module."""


class SurrealDbConnectionError(SurrealDbError):
    """
    Exceptions from connections
    """


class SurrealDbDecodeError(SurrealDbError):
    """
    Exceptions from connections
    """


class SurrealDbEncodeError(SurrealDbError):
    """
    Exceptions from connections
    """
