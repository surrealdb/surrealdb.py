import pytest

from surrealdb import AsyncSurreal, Surreal
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import SurrealError, UnsupportedEngineError


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
    """An unsupported protocol raises a ``SurrealError``, not a bare ``ValueError``.

    This previously escaped as ``ValueError: 'ftp' is not a valid UrlScheme``
    straight from enum construction, so ``except SurrealError`` did not cover
    it. The original ``ValueError`` is kept as ``__cause__``.
    """
    with pytest.raises(UnsupportedEngineError) as exc_info:
        Surreal("ftp://localhost:8000")

    assert isinstance(exc_info.value, SurrealError)
    assert isinstance(exc_info.value.__cause__, ValueError)


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
    """The async factory rejects an unsupported protocol the same way."""
    with pytest.raises(UnsupportedEngineError) as exc_info:
        AsyncSurreal("ftp://localhost:8000")

    assert isinstance(exc_info.value, SurrealError)
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_surreal_keyword_arg() -> None:
    """Test Surreal function accepts the url as a keyword argument."""
    connection = Surreal(url="http://localhost:8000")
    assert isinstance(connection, BlockingHttpSurrealConnection)


def test_async_surreal_keyword_arg() -> None:
    """Test AsyncSurreal function accepts the url as a keyword argument."""
    connection = AsyncSurreal(url="http://localhost:8000")
    assert isinstance(connection, AsyncHttpSurrealConnection)


def test_all_names_are_importable() -> None:
    """Every name in ``surrealdb.__all__`` actually exists.

    ``__all__`` used to advertise ``AsyncEmbeddedSurrealConnection`` and
    ``BlockingEmbeddedSurrealConnection`` unconditionally, even though both are
    imported under a ``try``/``except ImportError`` and are absent unless the
    optional native engine is installed. On a plain ``pip install surrealdb``
    that made ``from surrealdb import *`` raise ``AttributeError``.

    This runs in both configurations: the core CI test job installs no embedded
    engine, while the embedded job builds one, so the guard covers each path.
    """
    import surrealdb

    missing = [name for name in surrealdb.__all__ if not hasattr(surrealdb, name)]
    assert missing == [], f"__all__ advertises names that do not exist: {missing}"


def test_star_import_succeeds() -> None:
    """``from surrealdb import *`` works whatever is installed."""
    namespace: dict[str, object] = {}
    exec("from surrealdb import *", namespace)

    assert "Surreal" in namespace
    assert "AsyncSurreal" in namespace


def test_unsupported_scheme_raises_surreal_error() -> None:
    """``Surreal`` rejects an unknown scheme inside the error hierarchy."""
    with pytest.raises(SurrealError):
        Surreal("rocksdb://tmp/db")

    with pytest.raises(SurrealError):
        AsyncSurreal("rocksdb://tmp/db")


def test_http_connections_implement_connect() -> None:
    """``connect()`` works on HTTP, not just the websocket transports.

    HTTP opens no persistent connection, but the inherited default raised
    ``NotImplementedError``, so transport-agnostic code calling ``connect()``
    broke on HTTP alone.
    """
    connection = Surreal("http://localhost:8000")
    connection.connect()

    assert connection.raw_url == "http://localhost:8000"


def test_http_connect_repoints_the_url() -> None:
    """Passing a url to ``connect()`` re-points it, as websockets do."""
    connection = Surreal("http://localhost:8000")
    connection.connect("http://localhost:9000/")

    assert connection.host == "localhost"
    assert connection.port == 9000
    assert connection.raw_url == "http://localhost:9000"
