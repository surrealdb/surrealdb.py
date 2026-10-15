"""Request timeouts are set per connection and can be overridden per block.

Against a real server, because the point is what happens to a reply that is
slower than the deadline: ``RETURN sleep(...)`` makes the server take a known
time to answer, so a short deadline must fail and a longer one must not.
"""

import asyncio
import re
from typing import Any

import pytest

from surrealdb import AsyncSurreal, Surreal
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import TransportTimeoutError

pytestmark = pytest.mark.slow

_SLOW = "RETURN sleep(1500ms); RETURN 1"
_SHORT = 0.3


def _skip_without_sessions(version: str) -> None:
    major = re.search(r"(\d+)\.\d+\.\d+", version)
    if major is None or int(major.group(1)) < 3:
        pytest.skip(f"sessions need SurrealDB 3.0.0 or later (server: {version})")


def _sync_connection(
    kind: str, params: dict[str, Any], timeout: float | None
) -> BlockingWsSurrealConnection | BlockingHttpSurrealConnection:
    connection: BlockingWsSurrealConnection | BlockingHttpSurrealConnection
    if kind == "ws":
        connection = BlockingWsSurrealConnection(params["ws_url"], timeout=timeout)
    else:
        connection = BlockingHttpSurrealConnection(params["url"], timeout=timeout)
    # Signing in hashes a password, which can itself outlast a deliberately
    # short deadline on a busy machine.
    with connection.timeout(30):
        connection.signin(params["vars_params"])
        connection.use(params["namespace"], params["database_name"])
    return connection


async def _async_connection(
    kind: str, params: dict[str, Any], timeout: float | None
) -> AsyncWsSurrealConnection | AsyncHttpSurrealConnection:
    connection: AsyncWsSurrealConnection | AsyncHttpSurrealConnection
    if kind == "ws":
        connection = AsyncWsSurrealConnection(params["ws_url"], timeout=timeout)
    else:
        connection = AsyncHttpSurrealConnection(params["url"], timeout=timeout)
    with connection.timeout(30):
        await connection.signin(params["vars_params"])
        await connection.use(params["namespace"], params["database_name"])
    return connection


@pytest.mark.parametrize("kind", ["ws", "http"])
def test_blocking_connection_timeout_bounds_a_slow_reply(
    kind: str, connection_params: dict[str, Any]
) -> None:
    connection = _sync_connection(kind, connection_params, _SHORT)
    try:
        with pytest.raises(TransportTimeoutError, match=r"within 0\.3s"):
            connection.query(_SLOW).execute()
        assert connection.query("RETURN 2").first() == 2
    finally:
        connection.close()


@pytest.mark.parametrize("kind", ["ws", "http"])
async def test_async_connection_timeout_bounds_a_slow_reply(
    kind: str, connection_params: dict[str, Any]
) -> None:
    connection = await _async_connection(kind, connection_params, _SHORT)
    try:
        with pytest.raises(TransportTimeoutError, match=r"within 0\.3s"):
            await connection.query(_SLOW)
        assert await connection.query("RETURN 2").first() == 2
    finally:
        await connection.close()


@pytest.mark.parametrize("kind", ["ws", "http"])
@pytest.mark.parametrize("override", [5.0, None])
def test_blocking_override_lets_a_slow_request_finish(
    kind: str, override: float | None, connection_params: dict[str, Any]
) -> None:
    connection = _sync_connection(kind, connection_params, _SHORT)
    try:
        with connection.timeout(override):
            assert connection.query(_SLOW).execute()[1] == 1
        with pytest.raises(TransportTimeoutError):
            connection.query(_SLOW).execute()
    finally:
        connection.close()


@pytest.mark.parametrize("kind", ["ws", "http"])
@pytest.mark.parametrize("override", [5.0, None])
async def test_async_override_lets_a_slow_request_finish(
    kind: str, override: float | None, connection_params: dict[str, Any]
) -> None:
    connection = await _async_connection(kind, connection_params, _SHORT)
    try:
        with connection.timeout(override):
            assert (await connection.query(_SLOW))[1] == 1
        with pytest.raises(TransportTimeoutError):
            await connection.query(_SLOW)
    finally:
        await connection.close()


@pytest.mark.parametrize("kind", ["ws", "http"])
async def test_async_override_shortens_the_default(
    kind: str, connection_params: dict[str, Any]
) -> None:
    connection = await _async_connection(kind, connection_params, 30.0)
    try:
        with connection.timeout(_SHORT), pytest.raises(TransportTimeoutError):
            await connection.query(_SLOW)
    finally:
        await connection.close()


async def test_async_override_does_not_leak_into_a_concurrent_task(
    connection_params: dict[str, Any],
) -> None:
    connection = await _async_connection("ws", connection_params, 5.0)
    try:

        async def short() -> None:
            with connection.timeout(_SHORT):
                await connection.query(_SLOW)

        async def default() -> Any:
            return await connection.query(_SLOW)

        outcomes = await asyncio.gather(short(), default(), return_exceptions=True)
        assert isinstance(outcomes[0], TransportTimeoutError)
        assert outcomes[1] == [None, 1]
    finally:
        await connection.close()


async def test_async_override_is_inherited_by_tasks_started_inside_it(
    connection_params: dict[str, Any],
) -> None:
    connection = await _async_connection("ws", connection_params, 5.0)
    try:
        with connection.timeout(_SHORT):
            task = asyncio.create_task(connection.query(_SLOW).execute())
        with pytest.raises(TransportTimeoutError):
            await task
    finally:
        await connection.close()


async def test_override_on_one_connection_leaves_another_alone(
    connection_params: dict[str, Any],
) -> None:
    first = await _async_connection("ws", connection_params, 5.0)
    second = await _async_connection("ws", connection_params, 5.0)
    try:
        with first.timeout(_SHORT):
            assert (await second.query(_SLOW))[1] == 1
    finally:
        await first.close()
        await second.close()


async def test_async_session_and_transaction_share_the_connection_override(
    connection_params: dict[str, Any],
) -> None:
    connection = await _async_connection("ws", connection_params, _SHORT)
    try:
        with connection.timeout(30):
            _skip_without_sessions(await connection.version())
            session = await connection.new_session()
        await session.use(
            connection_params["namespace"], connection_params["database_name"]
        )
        with pytest.raises(TransportTimeoutError):
            await session.query(_SLOW)
        with session.timeout(5.0):
            assert (await session.query(_SLOW))[1] == 1
            transaction = await session.begin_transaction()
            with transaction.timeout(None):
                assert (await transaction.query(_SLOW))[1] == 1
            await transaction.cancel()
        await session.close_session()
    finally:
        await connection.close()


def test_blocking_session_shares_the_connection_override(
    connection_params: dict[str, Any],
) -> None:
    connection = _sync_connection("ws", connection_params, _SHORT)
    try:
        with connection.timeout(30):
            _skip_without_sessions(connection.version())
            session = connection.new_session()
        session.use(connection_params["namespace"], connection_params["database_name"])
        with pytest.raises(TransportTimeoutError):
            session.query(_SLOW).execute()
        with session.timeout(5.0):
            assert session.query(_SLOW).execute()[1] == 1
        session.close_session()
    finally:
        connection.close()


def test_factories_pass_the_timeout_through(connection_params: dict[str, Any]) -> None:
    connection = Surreal(connection_params["url"], timeout=_SHORT)
    with connection.timeout(30):
        connection.signin(connection_params["vars_params"])
        connection.use(
            connection_params["namespace"], connection_params["database_name"]
        )
    with pytest.raises(TransportTimeoutError):
        connection.query(_SLOW).execute()
    connection.close()


async def test_async_factory_passes_the_timeout_through(
    connection_params: dict[str, Any],
) -> None:
    connection = AsyncSurreal(connection_params["ws_url"], timeout=_SHORT)
    try:
        with connection.timeout(30):
            await connection.signin(connection_params["vars_params"])
            await connection.use(
                connection_params["namespace"], connection_params["database_name"]
            )
        with pytest.raises(TransportTimeoutError):
            await connection.query(_SLOW)
    finally:
        await connection.close()


_CONNECTIONS = (
    AsyncWsSurrealConnection,
    AsyncHttpSurrealConnection,
    BlockingWsSurrealConnection,
    BlockingHttpSurrealConnection,
)


@pytest.mark.parametrize("connection", _CONNECTIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize(
    ("value", "error"),
    [
        (0, ValueError),
        (-1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        ("5", TypeError),
    ],
)
def test_an_invalid_timeout_is_rejected(
    connection: type, value: Any, error: type[Exception]
) -> None:
    # Never connects: the constructor and `timeout()` validate before any I/O.
    url = (
        "ws://localhost:8000"
        if "Ws" in connection.__name__
        else "http://localhost:8000"
    )
    instance = connection(url, timeout=None)
    with pytest.raises(error, match="timeout"):
        connection(url, timeout=value)
    with pytest.raises(error, match="timeout"), instance.timeout(value):
        pass
