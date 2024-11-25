import logging

from urllib.parse import urlparse

from surrealdb.connection import Connection
from surrealdb.constants import (
    ALLOWED_CONNECTION_SCHEMES,
    WS_CONNECTION_SCHEMES,
    HTTP_CONNECTION_SCHEMES,
    CLIB_CONNECTION_SCHEMES,
)
from surrealdb.connection_clib import CLibConnection
from surrealdb.connection_http import HTTPConnection
from surrealdb.connection_ws import WebsocketConnection
from surrealdb.data.cbor import encode, decode
from surrealdb.errors import SurrealDbConnectionError


def create_connection_factory(url: str) -> Connection:
    logger: logging.Logger = logging.getLogger(__name__)

    parsed_url = urlparse(url)
    if parsed_url.scheme not in ALLOWED_CONNECTION_SCHEMES:
        raise SurrealDbConnectionError(
            "invalid scheme. allowed schemes are", "".join(ALLOWED_CONNECTION_SCHEMES)
        )

    if parsed_url.scheme in WS_CONNECTION_SCHEMES:
        logger.debug("websocket url detected, creating a websocket connection")
        return WebsocketConnection(url, logger, encoder=encode, decoder=decode)

    if parsed_url.scheme in HTTP_CONNECTION_SCHEMES:
        logger.debug("http url detected, creating a http connection")
        return HTTPConnection(url, logger, encoder=encode, decoder=decode)

    if parsed_url.scheme in CLIB_CONNECTION_SCHEMES:
        logger.debug("embedded url detected, creating a clib connection")
        return CLibConnection(url, logger, encoder=encode, decoder=decode)

    raise Exception("no connection type available")
