"""Negotiating ``cbor.2`` and the sized numbers it carries, against a real server.

Every connection asks for ``cbor.2`` and falls back to ``cbor``: over WebSocket
by offering both subprotocols, over HTTP by switching once a response comes
back as ``application/cbor; v=2``. Servers before 4.0 speak only ``cbor`` and
have no sized numbers, so the tests that need ``cbor.2`` skip there, and the
fallback test runs instead.
"""

from decimal import Decimal
from typing import Any

import pytest

from surrealdb import F32, I8, U8, U64
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

_SIZED = "RETURN [-128i8, 255u8, 18446744073709551615u64, 1.5f32]"
_EXPECTED: Any = [I8(-128), U8(255), U64(2**64 - 1), F32(1.5)]
_WIDENED: Any = [-128, 255, Decimal(2**64 - 1), 1.5]
_ECHO = "RETURN $v"


def _kinds(values: Any) -> list[type]:
    return [type(v) for v in values]


def _require_cbor2(db: Any) -> None:
    if db.wire_format != "cbor.2":
        pytest.skip(f"the server speaks {db.wire_format}, not cbor.2")


def _value(raw: Any) -> Any:
    """The one statement's result from a ``query_raw`` response."""
    return raw["result"][0]["result"]


def _check(raw: Any, expected: Any) -> None:
    result = _value(raw)
    assert result == expected
    assert _kinds(result) == _kinds(expected)


def test_blocking_ws_reads_sized_numbers(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    _require_cbor2(blocking_ws_connection)
    _check(blocking_ws_connection.query_raw(_SIZED), _EXPECTED)


async def test_async_ws_reads_sized_numbers(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    _require_cbor2(async_ws_connection)
    _check(await async_ws_connection.query_raw(_SIZED), _EXPECTED)


def test_blocking_http_reads_sized_numbers(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    _require_cbor2(blocking_http_connection)
    _check(blocking_http_connection.query_raw(_SIZED), _EXPECTED)


async def test_async_http_reads_sized_numbers(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    _require_cbor2(async_http_connection)
    _check(await async_http_connection.query_raw(_SIZED), _EXPECTED)


def test_blocking_ws_sends_sized_numbers_at_their_width(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    _require_cbor2(blocking_ws_connection)
    result = blocking_ws_connection.query_raw(_ECHO, {"v": _EXPECTED})
    _check(result, _EXPECTED)


async def test_async_ws_sends_sized_numbers_at_their_width(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    _require_cbor2(async_ws_connection)
    _check(await async_ws_connection.query_raw(_ECHO, {"v": _EXPECTED}), _EXPECTED)


def test_blocking_http_sends_sized_numbers_once_it_speaks_cbor2(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    _require_cbor2(blocking_http_connection)
    result = blocking_http_connection.query_raw(_ECHO, {"v": _EXPECTED})
    _check(result, _EXPECTED)


async def test_async_http_sends_sized_numbers_once_it_speaks_cbor2(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    _require_cbor2(async_http_connection)
    _check(await async_http_connection.query_raw(_ECHO, {"v": _EXPECTED}), _EXPECTED)


def test_http_speaks_plain_cbor_until_a_response_says_otherwise(
    connection_params: dict[str, Any],
) -> None:
    db = BlockingHttpSurrealConnection(connection_params["url"])
    assert db.wire_format == "cbor"
    db.version()
    assert db.wire_format in ("cbor", "cbor.2")


def test_sized_numbers_are_widened_over_plain_cbor(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Over ``cbor`` a sized number goes out as the server would widen it."""
    if blocking_ws_connection.wire_format != "cbor":
        pytest.skip("the server speaks cbor.2")
    result = blocking_ws_connection.query_raw(_ECHO, {"v": _EXPECTED})
    _check(result, _WIDENED)
