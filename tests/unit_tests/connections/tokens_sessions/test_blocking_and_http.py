"""The same token and session methods on the blocking websocket and on HTTP."""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import requests

from surrealdb import Null
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import (
    ServerError,
    UnavailableFeatureError,
    UnsupportedFeatureError,
)
from surrealdb.features import Features


@pytest.fixture
def ws(connection_params: dict[str, Any]) -> Iterator[BlockingWsSurrealConnection]:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def http(connection_params: dict[str, Any]) -> Iterator[BlockingHttpSurrealConnection]:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
async def ahttp(
    connection_params: dict[str, Any],
) -> AsyncIterator[AsyncHttpSurrealConnection]:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    try:
        yield connection
    finally:
        await connection.close()


def test_blocking_ws_refresh_and_revoke(
    ws: BlockingWsSurrealConnection, record_user: dict[str, Any]
) -> None:
    first = ws.signup(record_user)
    renewed = ws.refresh()
    assert renewed.refresh not in (None, first.refresh)
    assert ws.token == renewed.access
    assert ws.query("RETURN $access;").first() == record_user["access"]
    ws.revoke()
    with pytest.raises(ServerError):
        ws.refresh(renewed)


def test_blocking_ws_reset_sessions_and_fork(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    ws.use(connection_params["namespace"], connection_params["database_name"])
    ws.let("where", "root")

    fork = ws.fork_session()
    assert fork.id in ws.sessions()
    assert fork.query("RETURN [$where, session::db()];").first() == [
        "root",
        connection_params["database_name"],
    ]
    fork.reset()
    fork.use(connection_params["namespace"], connection_params["database_name"])
    assert fork.query("RETURN $where;").first() is None
    fork.close_session()

    ws.reset()
    assert ws.token is None
    assert ws.namespace is None


def test_blocking_ws_partial_use(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    ws.use(connection_params["namespace"], connection_params["database_name"])
    ws.use(database="other_db")
    assert ws.query("RETURN [session::ns(), session::db()];").first() == [
        connection_params["namespace"],
        "other_db",
    ]
    ws.use(Null, Null)
    assert ws.namespace is None


def test_blocking_ws_health(ws: BlockingWsSurrealConnection) -> None:
    ws.health()


def test_http_refresh_and_revoke(
    http: BlockingHttpSurrealConnection, record_user: dict[str, Any]
) -> None:
    first = http.signup(record_user)
    renewed = http.refresh()
    assert renewed.refresh not in (None, first.refresh)
    assert http.token == renewed.access
    http.use(record_user["namespace"], record_user["database"])
    assert http.query("RETURN $access;").first() == record_user["access"]
    http.revoke()
    with pytest.raises(ValueError, match="refresh token"):
        http.refresh()


async def test_async_http_refresh(
    ahttp: AsyncHttpSurrealConnection, record_user: dict[str, Any]
) -> None:
    await ahttp.signup(record_user)
    renewed = await ahttp.refresh()
    assert ahttp.token == renewed.access
    await ahttp.revoke()
    with pytest.raises(ServerError):
        await ahttp.refresh(renewed)


def test_http_reset_and_partial_use(
    http: BlockingHttpSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    http.signin(connection_params["vars_params"])
    http.use(connection_params["namespace"], connection_params["database_name"])
    http.use(database="other_db")
    assert http.namespace == connection_params["namespace"]
    assert http.database == "other_db"
    http.let("answer", 42)
    http.reset()
    assert (http.namespace, http.database, http.token, http.vars) == (
        None,
        None,
        None,
        {},
    )
    with pytest.raises(UnsupportedFeatureError):
        http.sessions()


async def test_http_health(
    http: BlockingHttpSurrealConnection, ahttp: AsyncHttpSurrealConnection
) -> None:
    http.health()
    await ahttp.health()


def test_http_refresh_sends_no_bearer(
    http: BlockingHttpSurrealConnection,
    record_user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The held access token may have expired, which is why it is refreshed."""
    http.signup(record_user)
    sent: list[dict[str, str]] = []
    original = requests.post

    def record(url: str, headers: dict[str, str], **kwargs: Any) -> Any:
        sent.append(dict(headers))
        return original(url, headers=headers, **kwargs)

    monkeypatch.setattr(requests, "post", record)
    http.refresh()
    assert sent and "Authorization" not in sent[-1]


async def test_async_http_refresh_sends_no_bearer(
    ahttp: AsyncHttpSurrealConnection,
    record_user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await ahttp.signup(record_user)
    sent: list[dict[str, str]] = []
    original = ahttp._request

    async def record(
        session: Any, url: str, headers: dict[str, str], *rest: Any
    ) -> Any:
        sent.append(dict(headers))
        return await original(session, url, headers, *rest)

    monkeypatch.setattr(ahttp, "_request", record)
    await ahttp.refresh()
    assert sent and "Authorization" not in sent[-1]


def test_http_invalidate_forgets_the_refresh_token(
    http: BlockingHttpSurrealConnection, record_user: dict[str, Any]
) -> None:
    http.signup(record_user)
    http.invalidate()
    with pytest.raises(ValueError, match="refresh token"):
        http.refresh()


async def test_async_http_invalidate_forgets_the_refresh_token(
    ahttp: AsyncHttpSurrealConnection, record_user: dict[str, Any]
) -> None:
    await ahttp.signup(record_user)
    await ahttp.invalidate()
    with pytest.raises(ValueError, match="refresh token"):
        await ahttp.refresh()


def test_http_v2_refuses_before_checking_tokens(
    http: BlockingHttpSurrealConnection,
) -> None:
    http.connect()
    if http.is_feature_supported(Features.REFRESH_TOKENS):
        pytest.skip("needs a SurrealDB 2.x server")
    with pytest.raises(UnavailableFeatureError):
        http.refresh()
    with pytest.raises(UnavailableFeatureError):
        http.revoke()
    with pytest.raises(UnavailableFeatureError):
        http.reset()


async def test_async_http_v2_refuses_before_checking_tokens(
    ahttp: AsyncHttpSurrealConnection,
) -> None:
    await ahttp.connect()
    if ahttp.is_feature_supported(Features.REFRESH_TOKENS):
        pytest.skip("needs a SurrealDB 2.x server")
    with pytest.raises(UnavailableFeatureError):
        await ahttp.refresh()
    with pytest.raises(UnavailableFeatureError):
        await ahttp.revoke()
    with pytest.raises(UnavailableFeatureError):
        await ahttp.reset()


def test_blocking_ws_reset_ends_the_session_live_queries(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    ws.use(connection_params["namespace"], connection_params["database_name"])
    ws.query("DEFINE TABLE IF NOT EXISTS reset_live;").execute()
    live_id = ws.live("reset_live")
    notifications = ws.subscribe_live(live_id)
    ws.reset()
    assert str(live_id) not in ws._registry.live
    assert list(notifications) == []


def test_blocking_ws_fork_keeps_no_rejected_credentials(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    ws._registry.root.access = "not.a.token"
    fork = ws.fork_session()
    assert ws._registry.state(fork.id).access is None
    fork.close_session()


def test_http_revoke_sends_no_stale_bearer(
    http: BlockingHttpSurrealConnection, record_user: dict[str, Any]
) -> None:
    tokens = http.signup(record_user)
    http.token = "stale.access.token"
    http.revoke(tokens)


def test_http_authenticate_drops_a_refresh_token_from_another_identity(
    http: BlockingHttpSurrealConnection,
    record_user: dict[str, Any],
    connection_params: dict[str, Any],
) -> None:
    root = BlockingHttpSurrealConnection(connection_params["url"])
    root_token = root.signin(connection_params["vars_params"]).access
    assert root_token is not None
    http.signup(record_user)
    http.authenticate(root_token)
    with pytest.raises(ValueError, match="refresh token"):
        http.refresh()


def test_blocking_ws_authenticate_drops_a_refresh_token_from_another_identity(
    ws: BlockingWsSurrealConnection,
    record_user: dict[str, Any],
    connection_params: dict[str, Any],
) -> None:
    root = BlockingHttpSurrealConnection(connection_params["url"])
    root_token = root.signin(connection_params["vars_params"]).access
    assert root_token is not None
    ws.signup(record_user)
    ws.authenticate(root_token)
    with pytest.raises(ValueError, match="refresh token"):
        ws.refresh()


def test_blocking_ws_cannot_fork_a_closed_session(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    session = ws.new_session()
    session.close_session()
    with pytest.raises(ValueError, match="not attached"):
        ws.fork_session(session.id)
    assert session.id not in ws._registry.sessions


def test_blocking_ws_token_methods_on_a_closed_session_do_not_reopen_it(
    ws: BlockingWsSurrealConnection,
    connection_params: dict[str, Any],
    needs_v3: None,
) -> None:
    ws.signin(connection_params["vars_params"])
    session = ws.new_session()
    session.close_session()
    with pytest.raises(ValueError, match="does not hold"):
        session.refresh()
    with pytest.raises(ValueError, match="does not hold"):
        session.revoke()
    assert session.id not in ws._registry.sessions
