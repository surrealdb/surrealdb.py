from urllib.parse import urlparse

from surrealdb.connection import Connection
from surrealdb.constants import ALLOWED_CONNECTION_SCHEMES, WS_CONNECTION_SCHEMES, HTTP_CONNECTION_SCHEMES
from surrealdb.connection_http import HTTPConnection
from surrealdb.connection_ws import WebsocketConnection
from surrealdb.errors import SurrealDbConnectionError


def create_connection_factory(url: str) -> Connection:
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ALLOWED_CONNECTION_SCHEMES:
        raise SurrealDbConnectionError("invalid scheme. allowed schemes are", "".join(ALLOWED_CONNECTION_SCHEMES))

    if parsed_url.scheme in WS_CONNECTION_SCHEMES:
        return WebsocketConnection(url)

    if parsed_url.scheme in HTTP_CONNECTION_SCHEMES:
        return HTTPConnection(url)

    raise Exception('no connection type available')
