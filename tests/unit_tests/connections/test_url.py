from typing import Any

import pytest

from surrealdb.connections.url import Url, UrlScheme


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
