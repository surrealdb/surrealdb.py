from enum import Enum
from urllib.parse import urlparse


class UrlScheme(Enum):
    HTTP = "http"
    HTTPS = "https"
    WS = "ws"
    WSS = "wss"
    MEM = "mem"


class Url:
    def __init__(self, url: str) -> None:
        self.raw_url = url.replace("/rpc", "")
        parsed_url = urlparse(url)
        self.scheme = UrlScheme(parsed_url.scheme)
        self.hostname = parsed_url.hostname
        self.port = parsed_url.port
