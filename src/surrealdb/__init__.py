from typing import Any, Union

from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import (
    AsyncSurrealSession,
    AsyncSurrealTransaction,
    AsyncWsSurrealConnection,
)
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingSurrealTransaction,
    BlockingWsSurrealConnection,
)
from surrealdb.connections.url import Url, UrlScheme
from surrealdb.data.types.constants import (
    TAG_BOUND_EXCLUDED,
    TAG_BOUND_INCLUDED,
    TAG_DATETIME,
    TAG_DATETIME_COMPACT,
    TAG_DECIMAL_STRING,
    TAG_DURATION,
    TAG_DURATION_COMPACT,
    TAG_GEOMETRY_COLLECTION,
    TAG_GEOMETRY_LINE,
    TAG_GEOMETRY_MULTI_LINE,
    TAG_GEOMETRY_MULTI_POINT,
    TAG_GEOMETRY_MULTI_POLYGON,
    TAG_GEOMETRY_POINT,
    TAG_GEOMETRY_POLYGON,
    TAG_NONE,
    TAG_RANGE,
    TAG_RECORD_ID,
    TAG_TABLE_NAME,
    TAG_UUID_STRING,
)
from surrealdb.data.types.datetime import Datetime
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.geometry import Geometry
from surrealdb.data.types.range import Range
from surrealdb.data.types.record_id import RecordID
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
    # Data types
    "Table",
    "Duration",
    "Geometry",
    "Range",
    "RecordID",
    "Datetime",
    "Tokens",
    "Value",
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
    # Constants
    "TAG_BOUND_EXCLUDED",
    "TAG_BOUND_INCLUDED",
    "TAG_DATETIME",
    "TAG_DATETIME_COMPACT",
    "TAG_DECIMAL_STRING",
    "TAG_DURATION",
    "TAG_DURATION_COMPACT",
    "TAG_GEOMETRY_COLLECTION",
    "TAG_GEOMETRY_LINE",
    "TAG_GEOMETRY_MULTI_LINE",
    "TAG_GEOMETRY_MULTI_POINT",
    "TAG_GEOMETRY_MULTI_POLYGON",
    "TAG_GEOMETRY_POINT",
    "TAG_GEOMETRY_POLYGON",
    "TAG_NONE",
    "TAG_RANGE",
    "TAG_RECORD_ID",
    "TAG_TABLE_NAME",
    "TAG_UUID_STRING",
]


class AsyncSurrealDBMeta(type):

    def __call__(cls, *args: Any, **kwargs: Any) -> Union[AsyncEmbeddedSurrealConnection, AsyncHttpSurrealConnection, AsyncWsSurrealConnection]:
        if len(args) > 0:
            url = args[0]
        else:
            url = kwargs.get("url")

        if url is None:
            raise ValueError("The 'url' parameter is required to initialise SurrealDB.")

        constructed_url = Url(url)

        if constructed_url.scheme in (UrlScheme.MEM, UrlScheme.MEMORY, UrlScheme.FILE, UrlScheme.SURREALKV):
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


class BlockingSurrealDBMeta(type):

    def __call__(cls, *args: Any, **kwargs: Any) -> Union[BlockingEmbeddedSurrealConnection, BlockingHttpSurrealConnection, BlockingWsSurrealConnection]:
        if len(args) > 0:
            url = args[0]
        else:
            url = kwargs.get("url")

        if url is None:
            raise ValueError("The 'url' parameter is required to initialise SurrealDB.")

        constructed_url = Url(url)

        if constructed_url.scheme in (UrlScheme.MEM, UrlScheme.MEMORY, UrlScheme.FILE, UrlScheme.SURREALKV):
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


def Surreal(
    url: str,
) -> Union[BlockingEmbeddedSurrealConnection, BlockingWsSurrealConnection, BlockingHttpSurrealConnection]:
    constructed_url = Url(url)
    if constructed_url.scheme in (UrlScheme.MEM, UrlScheme.MEMORY, UrlScheme.FILE, UrlScheme.SURREALKV):
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
) -> Union[AsyncEmbeddedSurrealConnection, AsyncWsSurrealConnection, AsyncHttpSurrealConnection]:
    constructed_url = Url(url)
    if constructed_url.scheme in (UrlScheme.MEM, UrlScheme.MEMORY, UrlScheme.FILE, UrlScheme.SURREALKV):
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
