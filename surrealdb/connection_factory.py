import logging

from urllib.parse import urlparse

from surrealdb.connection import Connection
from surrealdb.constants import (
    ALLOWED_CONNECTION_SCHEMES,
    WS_CONNECTION_SCHEMES,
    HTTP_CONNECTION_SCHEMES,
    CLIB_CONNECTION_SCHEMES,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_CONNECTION_URL,
)
from surrealdb.connection_clib import CLibConnection
from surrealdb.connection_http import HTTPConnection
from surrealdb.connection_ws import WebsocketConnection
from surrealdb.data.cbor import encode, decode
from surrealdb.errors import SurrealDbConnectionError


def create_connection_factory(
    connection_url: str | None,
    logger: logging.Logger,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
) -> Connection:
    if logger is None:
        logger = logging.getLogger(__name__)

    if connection_url is None:
        connection_url = DEFAULT_CONNECTION_URL

    if timeout <= 0:
        timeout = DEFAULT_REQUEST_TIMEOUT

    parsed_url = urlparse(connection_url)
    if parsed_url.scheme not in ALLOWED_CONNECTION_SCHEMES:
        raise SurrealDbConnectionError(
            "invalid scheme. allowed schemes are", "".join(ALLOWED_CONNECTION_SCHEMES)
        )

    if parsed_url.scheme in WS_CONNECTION_SCHEMES:
        logger.debug("websocket url detected, creating a websocket connection")
        return WebsocketConnection(
            connection_url, logger, encoder=encode, decoder=decode, timeout=timeout
        )

    if parsed_url.scheme in HTTP_CONNECTION_SCHEMES:
        logger.debug("http url detected, creating a http connection")
        return HTTPConnection(
            connection_url, logger, encoder=encode, decoder=decode, timeout=timeout
        )

    if parsed_url.scheme in CLIB_CONNECTION_SCHEMES:
        logger.debug("embedded url detected, creating a clib connection")
        clib_url = connection_url
        if parsed_url.scheme == "mem":
            clib_url = urlparse(connection_url, "memory").geturl()

        return CLibConnection(
            clib_url, logger, encoder=encode, decoder=decode, timeout=timeout
        )

    raise Exception("no connection type available")
