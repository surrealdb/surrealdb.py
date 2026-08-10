from enum import Enum
from urllib.parse import urlparse

from surrealdb.errors import UnsupportedEngineError


class UrlScheme(Enum):
    HTTP = "http"
    HTTPS = "https"
    WS = "ws"
    WSS = "wss"
    MEM = "mem"
    FILE = "file"
    MEMORY = "memory"
    SURREALKV = "surrealkv"
    SURREALKV_VERSIONED = "surrealkv+versioned"


# Embedded forms that are documented without a `://` separator. `urlparse`
# reports an empty scheme for these, so they are matched against the whole
# string instead. Kept to the documented spellings rather than falling back to
# the raw URL for any scheme-less input, which would quietly accept nonsense
# like `Surreal("http")` as an HTTP connection to nowhere.
_BARE_SCHEMES = {"memory"}


class Url:
    def __init__(self, url: str) -> None:
        self.raw_url = url.replace("/rpc", "")
        parsed_url = urlparse(url)
        scheme = url if url in _BARE_SCHEMES else parsed_url.scheme
        try:
            self.scheme = UrlScheme(scheme)
        except ValueError as error:
            # `UrlScheme(...)` raises a bare `ValueError` for anything it does
            # not recognise, which escaped the `SurrealError` hierarchy and so
            # was not caught by `except SurrealError`. Every failure this SDK
            # raises is meant to be a `SurrealError`.
            raise UnsupportedEngineError(url) from error
        self.hostname = parsed_url.hostname
        self.port = parsed_url.port
