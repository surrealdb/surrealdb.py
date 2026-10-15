"""Every remote connection learns the server version when it connects.

Against a real server: the handshake is a request on the wire, and what is
being checked is that it happens once, before anything else, on every
transport - and that an unsupported answer stops the connection.
"""

from typing import Any

import pytest
import requests

from surrealdb import AsyncSurreal, Features, Surreal
from surrealdb.connections import server_version
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import UnavailableFeatureError, UnsupportedVersionError
from surrealdb.features import parse_version


def _reported(version: str) -> tuple[int, int, int]:
    parsed = parse_version(version)
    assert parsed is not None
    return parsed


@pytest.fixture
def refuse_every_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server_version, "is_version_supported", lambda *_args, **_kw: False
    )


@pytest.mark.parametrize("kind", ["ws", "http"])
def test_blocking_connect_learns_the_server_version(
    kind: str, connection_params: dict[str, Any]
) -> None:
    url = connection_params["ws_url" if kind == "ws" else "url"]
    connection = Surreal(url)
    try:
        connection.connect()
        assert connection.server_version is not None
        assert _reported(connection.server_version) == _reported(connection.version())
        assert connection.is_feature_supported(Features.LIVE_QUERIES)
    finally:
        connection.close()


@pytest.mark.parametrize("kind", ["ws", "http"])
async def test_async_connect_learns_the_server_version(
    kind: str, connection_params: dict[str, Any]
) -> None:
    url = connection_params["ws_url" if kind == "ws" else "url"]
    connection = AsyncSurreal(url)
    try:
        await connection.connect()
        assert connection.server_version is not None
        assert _reported(connection.server_version) == _reported(
            await connection.version()
        )
    finally:
        await connection.close()


async def test_http_learns_the_version_on_its_first_request(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    assert connection.server_version is None
    await connection.signin(connection_params["vars_params"])
    assert connection.server_version is not None


@pytest.mark.usefixtures("refuse_every_version")
def test_blocking_ws_refuses_an_unsupported_server(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    with pytest.raises(UnsupportedVersionError):
        connection.connect()
    assert connection.socket is None
    with pytest.raises(UnsupportedVersionError):
        connection.query("RETURN 1").execute()
    assert connection.socket is None


@pytest.mark.usefixtures("refuse_every_version")
async def test_async_ws_refuses_an_unsupported_server(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    with pytest.raises(UnsupportedVersionError):
        await connection.connect()
    assert connection.socket is None
    with pytest.raises(UnsupportedVersionError):
        await connection.signin(connection_params["vars_params"])
    assert connection.socket is None


@pytest.mark.usefixtures("refuse_every_version")
def test_blocking_http_refuses_an_unsupported_server(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    with pytest.raises(UnsupportedVersionError):
        connection.signin(connection_params["vars_params"])


@pytest.mark.usefixtures("refuse_every_version")
async def test_async_http_refuses_an_unsupported_server(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    with pytest.raises(UnsupportedVersionError):
        await connection.connect()


@pytest.mark.usefixtures("refuse_every_version")
@pytest.mark.parametrize("kind", ["ws", "http"])
async def test_version_check_false_connects_anyway(
    kind: str, connection_params: dict[str, Any]
) -> None:
    url = connection_params["ws_url" if kind == "ws" else "url"]
    connection = AsyncSurreal(url, version_check=False)
    try:
        await connection.signin(connection_params["vars_params"])
        assert await connection.query("RETURN 1").first() == 1
        assert connection.server_version is not None
    finally:
        await connection.close()


def _is_v2(version: str | None) -> bool:
    return version is not None and _reported(version) < (3, 0, 0)


async def test_v2_refuses_sessions_and_transactions_before_sending(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    if not _is_v2(async_ws_connection.server_version):
        pytest.skip("needs a SurrealDB 2.x server")
    assert not async_ws_connection.is_feature_supported(Features.SESSIONS)
    with pytest.raises(UnavailableFeatureError, match="sessions"):
        await async_ws_connection.new_session()
    with pytest.raises(UnavailableFeatureError, match="transactions"):
        await async_ws_connection.begin()
    assert await async_ws_connection.query("RETURN 1").first() == 1


def test_blocking_v2_refuses_sessions_and_transactions_before_sending(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    if not _is_v2(blocking_ws_connection.server_version):
        pytest.skip("needs a SurrealDB 2.x server")
    with pytest.raises(UnavailableFeatureError):
        blocking_ws_connection.new_session()
    with pytest.raises(UnavailableFeatureError):
        blocking_ws_connection.begin()


async def test_streaming_is_not_attempted_on_a_server_that_predates_it(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    version = async_ws_connection.server_version
    assert version is not None
    if Features.QUERY_STREAMING.supports(version):
        assert async_ws_connection._streaming_supported is not False
    else:
        assert async_ws_connection._streaming_supported is False
        assert "v3.3.0" in (async_ws_connection._streaming_refusal or "")


async def test_async_http_version_as_the_first_call_learns_the_version(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    reported = await connection.version()
    assert connection.server_version is not None
    assert _reported(connection.server_version) == _reported(reported)
    assert connection.is_feature_supported(Features.LIVE_QUERIES)


def test_blocking_http_version_as_the_first_call_learns_the_version(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    reported = connection.version()
    assert connection.server_version is not None
    assert _reported(connection.server_version) == _reported(reported)


@pytest.mark.usefixtures("refuse_every_version")
async def test_async_http_version_refuses_an_unsupported_server(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    with pytest.raises(UnsupportedVersionError):
        await connection.version()


@pytest.mark.usefixtures("refuse_every_version")
def test_blocking_http_version_refuses_an_unsupported_server(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    with pytest.raises(UnsupportedVersionError):
        connection.version()


async def test_async_http_repoint_handshake_sends_no_old_token(
    connection_params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = AsyncHttpSurrealConnection(connection_params["url"])
    await connection.signin(connection_params["vars_params"])
    assert connection.token
    sent: list[dict[str, str]] = []
    original = connection._request

    async def record(
        session: Any, url: str, headers: dict[str, str], *rest: Any
    ) -> Any:
        sent.append(dict(headers))
        return await original(session, url, headers, *rest)

    monkeypatch.setattr(connection, "_request", record)
    await connection.connect(connection_params["url"])
    assert sent and all("Authorization" not in headers for headers in sent)


def test_blocking_http_repoint_handshake_sends_no_old_token(
    connection_params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = BlockingHttpSurrealConnection(connection_params["url"])
    connection.signin(connection_params["vars_params"])
    assert connection.token
    sent: list[dict[str, str]] = []
    original = requests.post

    def record(url: str, headers: dict[str, str], **kwargs: Any) -> Any:
        sent.append(dict(headers))
        return original(url, headers=headers, **kwargs)

    monkeypatch.setattr(requests, "post", record)
    connection.connect(connection_params["url"])
    assert sent and all("Authorization" not in headers for headers in sent)


async def test_async_ws_streaming_state_is_reset_by_a_new_socket(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncWsSurrealConnection(connection_params["ws_url"])
    try:
        await connection.connect()
        connection._streaming_supported = False
        connection._streaming_refusal = "stale"
        await connection.close()
        await connection.connect()
        version = connection.server_version
        assert version is not None
        assert connection._streaming_refusal != "stale"
        if Features.QUERY_STREAMING.supports(version):
            assert connection._streaming_supported is None
    finally:
        await connection.close()


def test_blocking_ws_streaming_state_is_reset_by_a_new_socket(
    connection_params: dict[str, Any],
) -> None:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    try:
        connection.connect()
        connection._streaming_supported = False
        connection._streaming_refusal = "stale"
        connection.close()
        connection.connect()
        version = connection.server_version
        assert version is not None
        assert connection._streaming_refusal != "stale"
        if Features.QUERY_STREAMING.supports(version):
            assert connection._streaming_supported is None
    finally:
        connection.close()
