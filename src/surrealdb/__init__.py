from typing import Any, Union

from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.url import Url, UrlScheme

from surrealdb.data.types.table import Table
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
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.geometry import Geometry
from surrealdb.data.types.range import Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.datetime import Datetime

from surrealdb.types import Value

__all__ = [
    "AsyncSurreal",
    "Surreal",
    "AsyncEmbeddedSurrealConnection",
    "AsyncHttpSurrealConnection",
    "AsyncWsSurrealConnection",
    "BlockingEmbeddedSurrealConnection",
    "BlockingHttpSurrealConnection",
    "BlockingWsSurrealConnection",
    "Table",
    "Duration",
    "Geometry",
    "Range",
    "RecordID",
    "Datetime",
    "Value",
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
        # Ensure `url` is provided as either an arg or kwarg
        if len(args) > 0:
            url = args[0]  # Assume the first positional argument is `url`
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
            raise ValueError(
                f"Unsupported protocol in URL: {url}. Use 'memory', 'mem://', 'file://', 'surrealkv://', 'ws://', or 'http://'."
            )


class BlockingSurrealDBMeta(type):

    def __call__(cls, *args: Any, **kwargs: Any) -> Union[BlockingEmbeddedSurrealConnection, BlockingHttpSurrealConnection, BlockingWsSurrealConnection]:
        # Ensure `url` is provided as either an arg or kwarg
        if len(args) > 0:
            url = args[0]  # Assume the first positional argument is `url`
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
            raise ValueError(
                f"Unsupported protocol in URL: {url}. Use 'memory', 'mem://', 'file://', 'surrealkv://', 'ws://', or 'http://'."
            )


def Surreal(
    url: str,
) -> Union[BlockingEmbeddedSurrealConnection, BlockingWsSurrealConnection, BlockingHttpSurrealConnection]:
    constructed_url = Url(url)
    if constructed_url.scheme in (UrlScheme.MEM, UrlScheme.MEMORY,UrlScheme.FILE, UrlScheme.SURREALKV):
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
        raise ValueError(
            f"Unsupported protocol in URL: {url}. Use 'memory', 'mem://', 'file://', 'surrealkv://', 'ws://', or 'http://'."
        )


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
        raise ValueError(
            f"Unsupported protocol in URL: {url}. Use 'memory', 'mem://', 'file://', 'surrealkv://', 'ws://', or 'http://'."
        )
