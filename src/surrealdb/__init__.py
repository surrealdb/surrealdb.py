from __future__ import annotations

from typing import TYPE_CHECKING, Union

_EMBEDDED_AVAILABLE = False
try:
    from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
    from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
    _EMBEDDED_AVAILABLE = True  # pyright: ignore[reportConstantRedefinition]
except ImportError:
    pass

if TYPE_CHECKING:
    from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection as AsyncEmbeddedSurrealConnection
    from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection as BlockingEmbeddedSurrealConnection

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import (
    AsyncSurrealSession,
    AsyncSurrealTransaction,
    AsyncWsSurrealConnection,
)
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingSurrealTransaction,
    BlockingWsSurrealConnection,
)
from surrealdb.connections.builders import (
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryBuilder,
    AsyncQueryIntoBuilder,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
)
from surrealdb.connections.url import Url, UrlScheme
from surrealdb.data.types.datetime import Datetime
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.geometry import Geometry
from surrealdb.data.types.range import Range
from surrealdb.data.types.record_id import RecordID, escape_identifier
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    AlreadyExistsDetailKind,
    AlreadyExistsError,
    AuthDetailKind,
    ConfigurationDetailKind,
    ConfigurationError,
    ConnectionDetailKind,
    ConnectionUnavailableError,
    ErrorKind,
    InternalError,
    InvalidDurationError,
    InvalidGeometryError,
    InvalidRecordIdError,
    InvalidTableError,
    NotAllowedDetailKind,
    NotAllowedError,
    NotFoundDetailKind,
    NotFoundError,
    QueryDetailKind,
    QueryError,
    SerializationDetailKind,
    SerializationError,
    ServerError,
    SurrealDBMethodError,
    SurrealError,
    ThrownError,
    UnexpectedResponseError,
    UnsupportedEngineError,
    UnsupportedFeatureError,
    ValidationDetailKind,
    ValidationError,
)
from surrealdb.types import Tokens, Value

__all__ = [
    "AsyncSurreal",
    "Surreal",
    # Connections
    "AsyncEmbeddedSurrealConnection",
    "AsyncHttpSurrealConnection",
    "AsyncSurrealSession",
    "AsyncSurrealTransaction",
    "AsyncWsSurrealConnection",
    "BlockingEmbeddedSurrealConnection",
    "BlockingHttpSurrealConnection",
    "BlockingSurrealSession",
    "BlockingSurrealTransaction",
    "BlockingWsSurrealConnection",
    # Connection type aliases (for annotating the objects the factories return)
    "AsyncSurrealConnection",
    "BlockingSurrealConnection",
    # Builders (returned by create/update/upsert/delete/insert/query)
    "AsyncCrudBuilder",
    "AsyncInsertBuilder",
    "AsyncQueryBuilder",
    "AsyncQueryIntoBuilder",
    "SyncCrudBuilder",
    "SyncInsertBuilder",
    "SyncQueryBuilder",
    # Data types
    "Table",
    "Duration",
    "Geometry",
    "Range",
    "RecordID",
    "Datetime",
    "Tokens",
    "Value",
    "escape_identifier",
    # Errors – base
    "SurrealError",
    # Errors – server
    "ServerError",
    "ValidationError",
    "ConfigurationError",
    "ThrownError",
    "QueryError",
    "SerializationError",
    "NotAllowedError",
    "NotFoundError",
    "AlreadyExistsError",
    "InternalError",
    "ErrorKind",
    # Error detail kind constants
    "AuthDetailKind",
    "ValidationDetailKind",
    "ConfigurationDetailKind",
    "QueryDetailKind",
    "SerializationDetailKind",
    "NotAllowedDetailKind",
    "NotFoundDetailKind",
    "AlreadyExistsDetailKind",
    "ConnectionDetailKind",
    # Errors – SDK-side
    "ConnectionUnavailableError",
    "UnsupportedEngineError",
    "UnsupportedFeatureError",
    "UnexpectedResponseError",
    "InvalidRecordIdError",
    "InvalidDurationError",
    "InvalidGeometryError",
    "InvalidTableError",
    # Errors – backward compat
    "SurrealDBMethodError",
]

_EMBEDDED_SCHEMES = (UrlScheme.MEM, UrlScheme.MEMORY, UrlScheme.FILE, UrlScheme.SURREALKV, UrlScheme.SURREALKV_VERSIONED)

# Type aliases for the connection objects the factory functions return. The
# ``Surreal``/``AsyncSurreal`` names are factory *functions*, so they cannot be
# used to annotate a connection instance (e.g. ``db: AsyncSurreal``). Use these
# unions instead: ``db: AsyncSurrealConnection`` / ``db: BlockingSurrealConnection``.
AsyncSurrealConnection = Union[
    AsyncWsSurrealConnection,
    AsyncHttpSurrealConnection,
    "AsyncEmbeddedSurrealConnection",
]
BlockingSurrealConnection = Union[
    BlockingWsSurrealConnection,
    BlockingHttpSurrealConnection,
    "BlockingEmbeddedSurrealConnection",
]


def Surreal(
    url: str,
) -> Union["BlockingEmbeddedSurrealConnection", BlockingWsSurrealConnection, BlockingHttpSurrealConnection]:
    constructed_url = Url(url)
    if constructed_url.scheme in _EMBEDDED_SCHEMES:
        if not _EMBEDDED_AVAILABLE:
            raise UnsupportedEngineError(url)
        return BlockingEmbeddedSurrealConnection(url=url)
    elif (
        constructed_url.scheme == UrlScheme.HTTP
        or constructed_url.scheme == UrlScheme.HTTPS
    ):
        return BlockingHttpSurrealConnection(url=url)
    elif (
        constructed_url.scheme == UrlScheme.WS
        or constructed_url.scheme == UrlScheme.WSS
    ):
        return BlockingWsSurrealConnection(url=url)
    else:
        raise UnsupportedEngineError(url)


def AsyncSurreal(
    url: str,
) -> Union["AsyncEmbeddedSurrealConnection", AsyncWsSurrealConnection, AsyncHttpSurrealConnection]:
    constructed_url = Url(url)
    if constructed_url.scheme in _EMBEDDED_SCHEMES:
        if not _EMBEDDED_AVAILABLE:
            raise UnsupportedEngineError(url)
        return AsyncEmbeddedSurrealConnection(url=url)
    elif (
        constructed_url.scheme == UrlScheme.HTTP
        or constructed_url.scheme == UrlScheme.HTTPS
    ):
        return AsyncHttpSurrealConnection(url=url)
    elif (
        constructed_url.scheme == UrlScheme.WS
        or constructed_url.scheme == UrlScheme.WSS
    ):
        return AsyncWsSurrealConnection(url=url)
    else:
        raise UnsupportedEngineError(url)
