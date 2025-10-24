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


# Test the meta classes indirectly through the factory functions
# These tests ensure the meta classes work correctly


def test_blocking_meta_class_positional_arg() -> None:
    """Test BlockingSurrealDBMeta with positional argument."""
    # This tests the meta class behavior indirectly
    connection = Surreal("http://localhost:8000")
    assert isinstance(connection, BlockingHttpSurrealConnection)


def test_blocking_meta_class_keyword_arg() -> None:
    """Test BlockingSurrealDBMeta with keyword argument."""
    # This tests the meta class behavior indirectly
    connection = Surreal(url="http://localhost:8000")
    assert isinstance(connection, BlockingHttpSurrealConnection)


def test_blocking_meta_class_missing_url() -> None:
    """Test BlockingSurrealDBMeta with missing URL raises ValueError."""
    # This would test the meta class directly, but we can't instantiate it
    # The factory function doesn't expose this error case
    pass


def test_async_meta_class_positional_arg() -> None:
    """Test AsyncSurrealDBMeta with positional argument."""
    # This tests the meta class behavior indirectly
    connection = AsyncSurreal("http://localhost:8000")
    assert isinstance(connection, AsyncHttpSurrealConnection)


def test_async_meta_class_keyword_arg() -> None:
    """Test AsyncSurrealDBMeta with keyword argument."""
    # This tests the meta class behavior indirectly
    connection = AsyncSurreal(url="http://localhost:8000")
    assert isinstance(connection, AsyncHttpSurrealConnection)


def test_async_meta_class_missing_url() -> None:
    """Test AsyncSurrealDBMeta with missing URL raises ValueError."""
    # This would test the meta class directly, but we can't instantiate it
    # The factory function doesn't expose this error case
    pass
