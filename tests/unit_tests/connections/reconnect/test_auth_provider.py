"""`auth=`: a connection that signs itself in, again after a reconnect, and
renews its access token before it expires."""

import asyncio
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from surrealdb import AsyncSurreal, ReconnectOptions, Surreal
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.features import Features
from surrealdb.types import Tokens
from tests.unit_tests.connections.reconnect.proxy import DroppableProxy

_FAST = ReconnectOptions(retry_delay=0.05, retry_delay_max=0.2)
# Tokens this short are renewed a fifth of a second before they expire.
_SHORT_USER = "short_lived"
_SHORT_PASS = "short-lived-password"


@pytest.fixture
def short_lived_root(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Iterator[dict[str, Any]]:
    """Root credentials whose tokens last two seconds."""
    blocking_ws_connection.query(
        f"DEFINE USER OVERWRITE {_SHORT_USER} ON ROOT PASSWORD '{_SHORT_PASS}' "
        "ROLES OWNER DURATION FOR TOKEN 2s, FOR SESSION 1h;"
    ).execute()
    yield {"username": _SHORT_USER, "password": _SHORT_PASS}
    blocking_ws_connection.query(
        f"REMOVE USER IF EXISTS {_SHORT_USER} ON ROOT;"
    ).execute()


def _wait_until(condition: Any, seconds: float = 6.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.05)


async def _await_until(condition: Any, seconds: float = 6.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        await asyncio.sleep(0.05)


async def test_credentials_sign_the_connection_in_when_it_opens(
    connection_params: dict[str, Any],
) -> None:
    db = AsyncSurreal(
        connection_params["ws_url"], auth=connection_params["vars_params"]
    )
    try:
        assert isinstance(await db.query("INFO FOR ROOT;").first(), dict)
        assert db.token is not None
    finally:
        await db.close()


async def test_an_async_function_is_asked_again_after_a_reconnect(
    proxy: DroppableProxy, connection_params: dict[str, Any]
) -> None:
    calls = 0

    async def credentials() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return dict(connection_params["vars_params"])

    db = AsyncWsSurrealConnection(proxy.ws_url, reconnect=_FAST, auth=credentials)
    reconnected = asyncio.Event()
    db.subscribe("reconnecting", lambda: reconnected.clear())
    db.subscribe("connected", lambda _version: reconnected.set())
    try:
        await db.connect()
        assert calls == 1
        proxy.drop()
        await asyncio.wait_for(_await_until(lambda: calls == 2), 10)
        await asyncio.wait_for(reconnected.wait(), 10)
        assert isinstance(await db.query("INFO FOR ROOT;").first(), dict)
    finally:
        await db.close()


def test_a_token_signs_the_blocking_connection_in(
    connection_params: dict[str, Any],
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    token = blocking_ws_connection.token
    assert token is not None
    db = Surreal(connection_params["ws_url"], auth=lambda: token)
    try:
        assert isinstance(db.query("INFO FOR ROOT;").first(), dict)
    finally:
        db.close()


def test_http_signs_in_before_its_first_request(
    connection_params: dict[str, Any],
) -> None:
    db = BlockingHttpSurrealConnection(
        connection_params["url"], auth=connection_params["vars_params"]
    )
    try:
        assert isinstance(db.query("INFO FOR ROOT;").first(), dict)
    finally:
        db.close()


async def test_async_renews_with_the_provider_before_the_token_expires(
    connection_params: dict[str, Any], short_lived_root: dict[str, Any]
) -> None:
    db = AsyncWsSurrealConnection(connection_params["ws_url"], auth=short_lived_root)
    renewed: list[Tokens | None] = []
    try:
        await db.connect()
        first = db.token
        db.subscribe("auth", lambda tokens, _session: renewed.append(tokens))
        await _await_until(lambda: len(renewed) >= 2)
        assert len(renewed) >= 2
        assert db.token not in (None, first)
        assert isinstance(await db.query("INFO FOR ROOT;").first(), dict)
    finally:
        await db.close()


def test_blocking_renews_before_the_next_request_once_due(
    connection_params: dict[str, Any], short_lived_root: dict[str, Any]
) -> None:
    db = BlockingWsSurrealConnection(connection_params["ws_url"], auth=short_lived_root)
    try:
        db.connect()
        first = db.token
        time.sleep(2.1)
        assert db.token == first
        assert isinstance(db.query("INFO FOR ROOT;").first(), dict)
        assert db.token not in (None, first)
    finally:
        db.close()


def test_http_renews_before_the_next_request_once_due(
    connection_params: dict[str, Any], short_lived_root: dict[str, Any]
) -> None:
    db = BlockingHttpSurrealConnection(connection_params["url"], auth=short_lived_root)
    try:
        db.query("RETURN 1;").execute()
        first = db.token
        time.sleep(2.1)
        assert isinstance(db.query("INFO FOR ROOT;").first(), dict)
        assert db.token not in (None, first)
    finally:
        db.close()


async def test_async_renews_with_the_refresh_token(
    connection_params: dict[str, Any],
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    if not blocking_ws_connection.is_feature_supported(Features.REFRESH_TOKENS):
        pytest.skip("refresh tokens need SurrealDB 3.0 or later")
    blocking_ws_connection.query(
        """
        DEFINE TABLE IF NOT EXISTS renew_user SCHEMALESS;
        DEFINE ACCESS OVERWRITE renew_acc ON DATABASE TYPE RECORD
            SIGNUP (CREATE renew_user SET name = $name)
            SIGNIN (SELECT * FROM renew_user WHERE name = $name)
            WITH REFRESH
            DURATION FOR TOKEN 2s, FOR SESSION 1h;
        """
    ).execute()
    db = AsyncWsSurrealConnection(connection_params["ws_url"])
    renewed: list[Tokens | None] = []
    try:
        first = await db.signup(
            {
                "namespace": connection_params["namespace"],
                "database": connection_params["database_name"],
                "access": "renew_acc",
                "variables": {"name": f"renew-{uuid.uuid4().hex[:8]}"},
            }
        )
        db.subscribe("auth", lambda tokens, _session: renewed.append(tokens))
        await _await_until(lambda: bool(renewed))
        assert renewed
        assert renewed[0] is not None
        assert renewed[0].refresh not in (None, first.refresh)
        assert await db.query("RETURN $access;").first() == "renew_acc"
    finally:
        await db.close()


def test_renew_access_false_leaves_the_token_alone(
    connection_params: dict[str, Any], short_lived_root: dict[str, Any]
) -> None:
    db = BlockingWsSurrealConnection(
        connection_params["ws_url"], auth=short_lived_root, renew_access=False
    )
    try:
        db.connect()
        first = db.token
        time.sleep(2.1)
        db.query("RETURN 1;").execute()
        assert db.token == first
    finally:
        db.close()


def test_an_unusable_auth_is_refused_up_front(
    connection_params: dict[str, Any],
) -> None:
    with pytest.raises(TypeError, match="auth must be"):
        BlockingWsSurrealConnection(connection_params["ws_url"], auth=42)  # type: ignore[arg-type]

    async def credentials() -> dict[str, Any]:
        return {}

    db = BlockingWsSurrealConnection(connection_params["ws_url"], auth=credentials)
    with pytest.raises(TypeError, match="coroutine"):
        db.connect()
