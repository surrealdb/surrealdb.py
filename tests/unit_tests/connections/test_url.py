from typing import Any

import pytest

from surrealdb.connections.url import Url, UrlScheme
from surrealdb.errors import SurrealError, UnsupportedEngineError


@pytest.fixture
def test_data() -> dict[str, Any]:
    return {
        "urls": [
            "http://localhost:5000",
            "https://localhost:5000",
            "http://localhost:5000/",
            "https://localhost:5000/",
            "ws://localhost:5000",
            "wss://localhost:5000",
            "ws://localhost:5000/",
            "wss://localhost:5000/",
        ],
        "schemes": ["http", "https", "http", "https", "ws", "wss", "ws", "wss"],
    }


def test_url_init(test_data: dict[str, Any]) -> None:
    for x in range(len(test_data["urls"])):
        url_string = test_data["urls"][x]
        url = Url(url_string)
        assert url_string == url.raw_url
        assert test_data["schemes"][x] == url.scheme.value
        assert "localhost" == url.hostname
        assert 5000 == url.port


def test_embedded_url_schemes() -> None:
    assert Url("mem://").scheme == UrlScheme.MEM
    assert Url("memory://test").scheme == UrlScheme.MEMORY
    assert Url("file:///tmp/db").scheme == UrlScheme.FILE
    assert Url("surrealkv:///tmp/db").scheme == UrlScheme.SURREALKV
    assert Url("surrealkv+versioned:///tmp/db").scheme == UrlScheme.SURREALKV_VERSIONED


def test_bare_memory_scheme() -> None:
    """``memory`` without ``://`` resolves, as the docs and errors advertise.

    ``urlparse`` reports an empty scheme for a bare word, so this used to raise
    ``ValueError: '' is not a valid UrlScheme`` even though ``README`` documents
    ``memory`` as equivalent to ``mem://`` and ``UnsupportedEngineError``'s own
    message lists it as a valid embedded form.
    """
    assert Url("memory").scheme == UrlScheme.MEMORY


@pytest.mark.parametrize(
    "url",
    [
        "rocksdb://tmp/db",  # a real SurrealDB engine this SDK does not support
        "localhost:8000",  # host:port with no scheme
        "not a url",
        "",
        "mem",  # bare, and not a documented alias
    ],
)
def test_unsupported_scheme_raises_surreal_error(url: str) -> None:
    """An unrecognised scheme stays inside the ``SurrealError`` hierarchy.

    ``UrlScheme(...)`` raises a bare ``ValueError``, which used to escape
    ``except SurrealError`` - the guarantee the error hierarchy is built on.
    """
    with pytest.raises(UnsupportedEngineError) as exc_info:
        Url(url)

    assert isinstance(exc_info.value, SurrealError)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert url in str(exc_info.value)
