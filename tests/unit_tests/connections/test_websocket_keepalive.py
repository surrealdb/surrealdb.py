"""``ping_interval`` and ``ping_timeout`` on the websocket connections.

Both are passed straight to ``websockets``, which is what actually sends the
control frames - the SDK had been taking that library's defaults of 20/20 and
never exposing a way to change them, so anyone behind a proxy with a different
idle policy had no lever short of reaching into ``connection.socket``.

The defaults here are 30/10 rather than the library's 20/20: a longer gap
between pings on an idle socket, and a shorter wait before a silent peer is
declared gone. A peer that disappears is still noticed inside roughly
``ping_interval + ping_timeout``.
"""

import pytest
from websockets.exceptions import WebSocketException

from surrealdb import AsyncSurreal, Surreal
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.utils_mixin import check_keepalive

WS_CLASSES = (BlockingWsSurrealConnection, AsyncWsSurrealConnection)
URL = "ws://localhost:8000/rpc"


@pytest.mark.parametrize("cls", WS_CLASSES, ids=lambda c: c.__name__)
def test_the_defaults_are_thirty_and_ten(cls: type) -> None:
    connection = cls(URL)

    assert connection._ping_interval == 30.0
    assert connection._ping_timeout == 10.0


@pytest.mark.parametrize("cls", WS_CLASSES, ids=lambda c: c.__name__)
def test_both_can_be_overridden(cls: type) -> None:
    connection = cls(URL, ping_interval=5, ping_timeout=2.5)

    assert connection._ping_interval == 5.0
    assert connection._ping_timeout == 2.5


@pytest.mark.parametrize("cls", WS_CLASSES, ids=lambda c: c.__name__)
def test_none_is_passed_through_to_disable_them(cls: type) -> None:
    """``websockets`` reads ``None`` as "no keepalive" / "wait forever"."""
    connection = cls(URL, ping_interval=None, ping_timeout=None)

    assert connection._ping_interval is None
    assert connection._ping_timeout is None


@pytest.mark.parametrize(
    "factory", (Surreal, AsyncSurreal), ids=("Surreal", "AsyncSurreal")
)
def test_the_factories_forward_them(factory: object) -> None:
    """Reachable from ``Surreal(url)``, or the option exists for nobody."""
    default = factory(URL)  # type: ignore[operator]
    custom = factory(URL, ping_interval=7, ping_timeout=3)  # type: ignore[operator]

    assert (default._ping_interval, default._ping_timeout) == (30.0, 10.0)
    assert (custom._ping_interval, custom._ping_timeout) == (7.0, 3.0)


def test_the_factory_accepts_and_ignores_them_for_http() -> None:
    """Matches ``streaming``, which the factory documents as ignored where it
    cannot apply.

    The factory picks the transport from the URL at runtime, so code that does
    not know the scheme statically would otherwise have to branch before passing
    an option. The connection classes themselves are strict - see below - so the
    leniency is confined to the one place that has to be lenient.
    """
    connection = Surreal("http://localhost:8000", ping_interval=5, ping_timeout=1)

    assert isinstance(connection, BlockingHttpSurrealConnection)
    assert not hasattr(connection, "_ping_interval")


def test_the_http_connection_class_itself_refuses_them() -> None:
    """It has no websocket, so accepting the argument there would be a lie."""
    with pytest.raises(TypeError, match="ping_interval"):
        BlockingHttpSurrealConnection(
            url="http://localhost:8000",
            ping_interval=5,  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]
        )


# ------------------------------------------------- they reach the library


def test_the_blocking_transport_passes_them_to_websockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storing the values is not the same as using them.

    Without this, deleting both keyword arguments from the ``connect()`` call
    leaves every other test in this file passing: the attributes are still set,
    they just never reach the library that sends the frames.
    """
    import websockets.sync.client as ws_sync

    captured: dict[str, object] = {}

    def fake_connect(url: str, **kwargs: object) -> object:
        captured.update(kwargs)
        raise WebSocketException("stop here - the kwargs are what matters")

    monkeypatch.setattr(ws_sync, "connect", fake_connect)
    connection = BlockingWsSurrealConnection(URL, ping_interval=7, ping_timeout=3)

    with pytest.raises(Exception):  # noqa: B017
        connection.connect()

    assert captured["ping_interval"] == 7.0
    assert captured["ping_timeout"] == 3.0


async def test_the_async_transport_passes_them_to_websockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import websockets

    captured: dict[str, object] = {}

    async def fake_connect(url: str, **kwargs: object) -> object:
        captured.update(kwargs)
        raise WebSocketException("stop here - the kwargs are what matters")

    monkeypatch.setattr(websockets, "connect", fake_connect)
    connection = AsyncWsSurrealConnection(URL, ping_interval=7, ping_timeout=3)

    with pytest.raises(Exception):  # noqa: B017
        await connection.connect()

    assert captured["ping_interval"] == 7.0
    assert captured["ping_timeout"] == 3.0


def test_the_defaults_reach_a_real_socket(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """And the library actually applies them, against a live server."""
    socket = blocking_ws_connection.socket
    assert socket is not None

    assert socket.ping_interval == 30.0
    assert socket.ping_timeout == 10.0


# --------------------------------------------------------------- validation


@pytest.mark.parametrize("name", ("ping_interval", "ping_timeout"))
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(0, ValueError, id="zero"),
        pytest.param(-1, ValueError, id="negative"),
        pytest.param(-0.5, ValueError, id="negative-float"),
        pytest.param("30", TypeError, id="string"),
        pytest.param(True, TypeError, id="bool"),
        pytest.param([30], TypeError, id="list"),
    ],
)
def test_unusable_values_are_refused(
    name: str, value: object, expected: type[Exception]
) -> None:
    """Zero is the one worth catching: ``websockets`` accepts it and then spins.

    It is rejected here rather than passed on, so the mistake surfaces at the
    constructor instead of as a connection that pings in a tight loop.
    """
    with pytest.raises(expected):
        check_keepalive(name, value)  # type: ignore[arg-type]


@pytest.mark.parametrize("cls", WS_CLASSES, ids=lambda c: c.__name__)
def test_the_constructor_refuses_them_too(cls: type) -> None:
    """The validation has to be wired in, not merely available."""
    with pytest.raises(ValueError):
        cls(URL, ping_interval=0)

    with pytest.raises(TypeError):
        cls(URL, ping_timeout="10")


def test_the_message_names_the_argument_that_was_wrong() -> None:
    """With two numeric arguments of the same shape, "invalid value" is useless."""
    with pytest.raises(ValueError) as caught:
        BlockingWsSurrealConnection(URL, ping_timeout=-1)

    assert "ping_timeout" in str(caught.value)


@pytest.mark.parametrize("value", (30, 30.0))
def test_ints_and_floats_are_both_accepted(value: float) -> None:
    assert check_keepalive("ping_interval", value) == 30.0
