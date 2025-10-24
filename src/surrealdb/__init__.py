from typing import Any, Union

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.url import Url, UrlScheme

from surrealdb.data.types.table import Table
from surrealdb.data.types.constants import *
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.geometry import Geometry
from surrealdb.data.types.range import Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.datetime import Datetime

from surrealdb.types import Value

__all__ = [
    "AsyncSurreal",
    "Surreal",
    "AsyncHttpSurrealConnection",
    "AsyncWsSurrealConnection",
    "BlockingHttpSurrealConnection",
    "BlockingWsSurrealConnection",
    "Table",
    "Duration",
    "Geometry",
    "Range",
    "RecordID",
    "Datetime",
    "Value",
]


class AsyncSurrealDBMeta(type):

    def __call__(cls, *args: Any, **kwargs: Any) -> Union[AsyncHttpSurrealConnection, AsyncWsSurrealConnection]:
        # Ensure `url` is provided as either an arg or kwarg
        if len(args) > 0:
            url = args[0]  # Assume the first positional argument is `url`
        else:
            url = kwargs.get("url")

        if url is None:
            raise ValueError("The 'url' parameter is required to initialise SurrealDB.")

        constructed_url = Url(url)

        if (
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
                f"Unsupported protocol in URL: {url}. Use 'ws://' or 'http://'."
            )


class BlockingSurrealDBMeta(type):

    def __call__(cls, *args: Any, **kwargs: Any) -> Union[BlockingHttpSurrealConnection, BlockingWsSurrealConnection]:
        # Ensure `url` is provided as either an arg or kwarg
        if len(args) > 0:
            url = args[0]  # Assume the first positional argument is `url`
        else:
            url = kwargs.get("url")

        if url is None:
            raise ValueError("The 'url' parameter is required to initialise SurrealDB.")

        constructed_url = Url(url)

        if (
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
                f"Unsupported protocol in URL: {url}. Use 'ws://' or 'http://'."
            )


def Surreal(
    url: str,
) -> Union[BlockingWsSurrealConnection, BlockingHttpSurrealConnection]:
    constructed_url = Url(url)
    if (
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
            f"Unsupported protocol in URL: {url}. Use 'ws://' or 'http://'."
        )


def AsyncSurreal(
    url: str,
) -> Union[AsyncWsSurrealConnection, AsyncHttpSurrealConnection]:
    constructed_url = Url(url)
    if (
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
            f"Unsupported protocol in URL: {url}. Use 'ws://' or 'http://'."
        )
