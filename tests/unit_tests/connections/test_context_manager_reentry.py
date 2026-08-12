"""Entering a context manager on an open connection keeps what is already open.

``with db:`` on a connection that had already been signed in threw away the
socket it was managing and opened a replacement. A websocket *is* the
server-side session, so the sign-in went with it and the first statement inside
the block came back ``NotAllowedError: Anonymous access not allowed`` - from a
connection the caller had authenticated moments earlier. The discarded socket
was never closed either, so it leaked with its two worker threads.

The HTTP transports had the same shape without the auth consequence, since
their identity is a token on the connection rather than the pooled session:
entering replaced the session object and only the replacement was ever closed,
so every re-entry leaked a connection pool.

Signing in and *then* using the connection with ``with`` is the obvious reading
of "``with`` manages the connection I already have", so this is the shape that
mattered.
"""

from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_entering_keeps_the_open_socket_and_its_session(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    connection.signin(connection_params["vars_params"])
    connection.use(connection_params["namespace"], connection_params["database_name"])
    opened = connection.socket

    with connection as entered:
        assert entered is connection
        assert connection.socket is opened, "the open socket was replaced"
        # The consequence, asked of the server rather than of an attribute.
        assert connection.query("RETURN 1").first() == 1


def test_entering_an_unconnected_connection_still_connects(
    connection_params: dict[str, Any],
) -> None:
    """The behaviour that was already right, and had to stay."""
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    assert connection.socket is None

    with connection:
        assert connection.socket is not None

    assert connection.socket is None


def test_exiting_still_closes(connection_params: dict[str, Any]) -> None:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    connection.signin(connection_params["vars_params"])

    with connection:
        pass

    assert connection.socket is None


def test_reentering_repeatedly_opens_one_socket(
    connection_params: dict[str, Any],
) -> None:
    """Nested/sequential ``with`` on a live connection must not stack sockets."""
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    connection.signin(connection_params["vars_params"])
    connection.use(connection_params["namespace"], connection_params["database_name"])
    opened = connection.socket

    with connection:
        with connection:
            assert connection.socket is opened
        # The inner block closed it, which is what a context manager does.
        assert connection.socket is None


def test_http_reuses_the_pooled_session(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    with connection:
        first = connection.session
        assert first is not None
        with connection:
            assert connection.session is first, "the pooled session was replaced"


async def test_async_http_reuses_the_pooled_session(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    async with connection:
        first = connection._session  # pyright: ignore[reportPrivateUsage]
        assert first is not None
        async with connection:
            assert connection._session is first, (  # pyright: ignore[reportPrivateUsage]
                "the pooled session was replaced"
            )


async def test_async_http_replaces_a_closed_session(
    connection_params: dict[str, Any],
) -> None:
    """Reuse is of an *open* session; a closed one is no use to anybody."""
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    async with connection:
        pass
    async with connection:
        session = connection._session  # pyright: ignore[reportPrivateUsage]
        assert session is not None and not session.closed


@pytest.mark.parametrize("attempts", [3])
def test_the_websocket_session_survives_every_reentry(
    connection_params: dict[str, Any], attempts: int
) -> None:
    """The regression as reported: sign in once, use ``with`` afterwards."""
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    connection.signin(connection_params["vars_params"])
    connection.use(connection_params["namespace"], connection_params["database_name"])

    for _ in range(attempts):
        with connection:
            assert connection.query("RETURN 1").first() == 1
        connection.signin(connection_params["vars_params"])
        connection.use(
            connection_params["namespace"], connection_params["database_name"]
        )
