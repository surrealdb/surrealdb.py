"""A rejected ``authenticate()`` must leave the connection as it found it.

Both HTTP transports adopted the token *before* sending it, so a rejected one
stayed attached to every later request - including the ``signin()`` that would
have recovered the connection, which the server then answered ``401``. There
was no way back short of building a new connection, and nothing in the SDK said
so. The websocket transports already assigned the token after a successful
reply; they are covered here so the four stay in step.

Two rejection paths, because they fail at different places:

* a token that is not JWT-shaped never leaves the process - the request schema
  refuses it - so nothing but the SDK's own bookkeeping can undo the damage;
* a well-formed token with a bad signature is refused by the server.
"""

from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import SurrealError

# Rejected by the request schema, before any socket is touched.
MALFORMED_TOKEN = "not-a-real-token"

# JWT-shaped, so it reaches the server, which refuses the signature. Every
# server version in the support matrix rejects it; only the error type differs.
FORGED_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9"
    ".eyJpc3MiOiJTdXJyZWFsREIiLCJJRCI6InJvb3QifQ"
    ".ZmFrZS1zaWduYXR1cmUtdGhhdC13aWxsLW5ldmVyLXZlcmlmeQ"
)

BAD_TOKENS = [
    pytest.param(MALFORMED_TOKEN, id="malformed"),
    pytest.param(FORGED_TOKEN, id="forged"),
]


# The happy path, which had no HTTP cover at all before the token stopped
# being assigned up front - so nothing would have noticed if the change had
# broken authenticating successfully rather than only failing to.


def test_blocking_http_authenticate_succeeds(
    connection_params: dict[str, Any],
) -> None:
    signer = BlockingHttpSurrealConnection(connection_params["url"])
    tokens = signer.signin(connection_params["vars_params"])

    connection = BlockingHttpSurrealConnection(connection_params["url"])
    assert connection.token is None
    connection.authenticate(tokens.access)

    assert connection.token == tokens.access
    connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    assert connection.query("RETURN 1").first() == 1

    # Authenticating again on a connection that already holds a token.
    connection.authenticate(tokens.access)
    assert connection.query("RETURN 1").first() == 1


async def test_async_http_authenticate_succeeds(
    connection_params: dict[str, Any],
) -> None:
    signer = AsyncHttpSurrealConnection(connection_params["url"])
    tokens = await signer.signin(connection_params["vars_params"])

    connection = AsyncHttpSurrealConnection(connection_params["url"])
    assert connection.token is None
    await connection.authenticate(tokens.access)

    assert connection.token == tokens.access
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    assert await connection.query("RETURN 1").first() == 1


# --------------------------------------------------------------------- HTTP


@pytest.mark.parametrize("bad_token", BAD_TOKENS)
def test_blocking_http_survives_a_rejected_token(
    connection_params: dict[str, Any], bad_token: str
) -> None:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    connection.signin(connection_params["vars_params"])
    connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    good_token = connection.token

    with pytest.raises((ValueError, SurrealError)):
        connection.authenticate(bad_token)

    assert connection.token == good_token, "the rejected token was adopted anyway"
    assert connection.query("RETURN 1").first() == 1
    # Signing in again is the documented way out of a bad auth state, and has
    # to work even when the connection was already unauthenticated.
    connection.signin(connection_params["vars_params"])
    assert connection.query("RETURN 1").first() == 1


@pytest.mark.parametrize("bad_token", BAD_TOKENS)
async def test_async_http_survives_a_rejected_token(
    connection_params: dict[str, Any], bad_token: str
) -> None:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    await connection.signin(connection_params["vars_params"])
    await connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    good_token = connection.token

    with pytest.raises((ValueError, SurrealError)):
        await connection.authenticate(bad_token)

    assert connection.token == good_token, "the rejected token was adopted anyway"
    assert await connection.query("RETURN 1").first() == 1
    await connection.signin(connection_params["vars_params"])
    assert await connection.query("RETURN 1").first() == 1


def test_blocking_http_recovers_from_an_unauthenticated_start(
    connection_params: dict[str, Any],
) -> None:
    """A brand-new connection whose first act fails is still usable."""
    connection = BlockingHttpSurrealConnection(connection_params["url"])

    with pytest.raises((ValueError, SurrealError)):
        connection.authenticate(FORGED_TOKEN)

    assert connection.token is None
    connection.signin(connection_params["vars_params"])
    connection.use(
        namespace=connection_params["namespace"],
        database=connection_params["database_name"],
    )
    assert connection.query("RETURN 1").first() == 1


# ----------------------------------------------------------------- WebSocket


@pytest.mark.parametrize("bad_token", BAD_TOKENS)
def test_blocking_ws_survives_a_rejected_token(
    connection_params: dict[str, Any], bad_token: str
) -> None:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    try:
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        good_token = connection.token

        with pytest.raises((ValueError, SurrealError)):
            connection.authenticate(bad_token)

        assert connection.token == good_token
        assert connection.query("RETURN 1").first() == 1
    finally:
        connection.close()


@pytest.mark.parametrize("bad_token", BAD_TOKENS)
async def test_async_ws_survives_a_rejected_token(
    connection_params: dict[str, Any], bad_token: str
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    try:
        await connection.signin(connection_params["vars_params"])
        await connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        good_token = connection.token

        with pytest.raises((ValueError, SurrealError)):
            await connection.authenticate(bad_token)

        assert connection.token == good_token
        assert await connection.query("RETURN 1").first() == 1
    finally:
        await connection.close()
