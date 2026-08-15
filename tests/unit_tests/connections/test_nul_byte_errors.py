"""A rejected value fails as a ``SurrealError``, on every server version.

SurrealDB 2.x refuses a NUL byte in a record's data, and answers with a bare
string where the protocol calls for an error object. Reading ``kind`` off that
string raised ``AttributeError: 'str' object has no attribute 'get'`` from
inside the SDK - no server message, and nothing an ``except SurrealError``
would catch. 3.x stores the byte happily.

Written as a property rather than a fixed expectation, so it runs on every leg
of the server matrix: whether the value is accepted is the server's business,
but *how a refusal is reported* is the SDK's, and it must never be an exception
from outside the documented tree.
"""

from typing import Any

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import SurrealError

NUL_DATA: dict[str, Any] = {"note": "before\x00after"}


def _assert_typed(error: BaseException) -> None:
    assert isinstance(error, SurrealError), (
        f"a rejected value raised {type(error).__name__}, which callers cannot "
        f"catch with `except SurrealError`: {error}"
    )
    assert str(error), "the server's explanation was lost"


def test_blocking_ws_nul_byte(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    try:
        blocking_ws_connection.create("nul_probe", NUL_DATA)
    except Exception as error:
        _assert_typed(error)


def test_blocking_http_nul_byte(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    try:
        blocking_http_connection.create("nul_probe", NUL_DATA)
    except Exception as error:
        _assert_typed(error)


async def test_async_ws_nul_byte(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    try:
        await async_ws_connection.create("nul_probe", NUL_DATA)
    except Exception as error:
        _assert_typed(error)


async def test_async_http_nul_byte(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    try:
        await async_http_connection.create("nul_probe", NUL_DATA)
    except Exception as error:
        _assert_typed(error)


def test_the_probe_itself_is_a_valid_create(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Guards against the tests above passing because nothing reached the server.

    A ``create`` that failed locally - a rejected table name, say - would still
    raise a ``SurrealError`` and tell us nothing about how a *server* refusal
    is reported. The same call with an ordinary value has to succeed.
    """
    assert blocking_ws_connection.create("nul_probe", {"note": "plain"}) is not None
