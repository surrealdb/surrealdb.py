from typing import Any

import pytest

from surrealdb import AsyncSurreal, Surreal
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.url import UrlScheme


def test_surreal_http() -> None:
    """Test Surreal function with HTTP URL."""
    connection = Surreal("http://localhost:8000")
    assert isinstance(connection, BlockingHttpSurrealConnection)


def test_surreal_https() -> None:
    """Test Surreal function with HTTPS URL."""
    connection = Surreal("https://localhost:8000")
    assert isinstance(connection, BlockingHttpSurrealConnection)


def test_surreal_ws() -> None:
    """Test Surreal function with WebSocket URL."""
    connection = Surreal("ws://localhost:8000")
    assert isinstance(connection, BlockingWsSurrealConnection)


def test_surreal_wss() -> None:
    """Test Surreal function with secure WebSocket URL."""
    connection = Surreal("wss://localhost:8000")
    assert isinstance(connection, BlockingWsSurrealConnection)


def test_surreal_invalid_protocol() -> None:
    """Test Surreal function with invalid protocol raises ValueError."""
    with pytest.raises(ValueError, match="'ftp' is not a valid UrlScheme"):
        Surreal("ftp://localhost:8000")


def test_async_surreal_http() -> None:
    """Test AsyncSurreal function with HTTP URL."""
    connection = AsyncSurreal("http://localhost:8000")
    assert isinstance(connection, AsyncHttpSurrealConnection)


def test_async_surreal_https() -> None:
    """Test AsyncSurreal function with HTTPS URL."""
    connection = AsyncSurreal("https://localhost:8000")
    assert isinstance(connection, AsyncHttpSurrealConnection)


def test_async_surreal_ws() -> None:
    """Test AsyncSurreal function with WebSocket URL."""
    connection = AsyncSurreal("ws://localhost:8000")
    assert isinstance(connection, AsyncWsSurrealConnection)


def test_async_surreal_wss() -> None:
    """Test AsyncSurreal function with secure WebSocket URL."""
    connection = AsyncSurreal("wss://localhost:8000")
    assert isinstance(connection, AsyncWsSurrealConnection)


def test_async_surreal_invalid_protocol() -> None:
    """Test AsyncSurreal function with invalid protocol raises ValueError."""
    with pytest.raises(ValueError, match="'ftp' is not a valid UrlScheme"):
        AsyncSurreal("ftp://localhost:8000")


def test_surreal_keyword_arg() -> None:
    """Test Surreal function accepts the url as a keyword argument."""
    connection = Surreal(url="http://localhost:8000")
    assert isinstance(connection, BlockingHttpSurrealConnection)


def test_async_surreal_keyword_arg() -> None:
    """Test AsyncSurreal function accepts the url as a keyword argument."""
    connection = AsyncSurreal(url="http://localhost:8000")
    assert isinstance(connection, AsyncHttpSurrealConnection)
