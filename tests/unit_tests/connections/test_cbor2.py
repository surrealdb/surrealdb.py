"""Negotiating ``cbor.2`` and the kinds it carries, against a real server.

Every connection asks for ``cbor.2`` and falls back to ``cbor``: over WebSocket
by offering both subprotocols, over HTTP by switching once a response comes
back as ``application/cbor; v=2``. Servers before 4.0 speak only ``cbor`` and
have none of the kinds it adds, the sized numbers, date, time, timestamp,
interval, bigdecimal and regex, so the tests that need ``cbor.2`` skip there,
and the fallback tests run instead.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from surrealdb import (
    F32,
    I8,
    U8,
    U64,
    BigDecimal,
    Duration,
    Interval,
    PlainDate,
    PlainTime,
    Regex,
    Timestamp,
)
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

_SIZED = "RETURN [-128i8, 255u8, 18446744073709551615u64, 1.5f32]"
_EXPECTED: Any = [I8(-128), U8(255), U64(2**64 - 1), F32(1.5)]
_WIDENED: Any = [-128, 255, Decimal(2**64 - 1), 1.5]
_ECHO = "RETURN $v"

_CALENDAR = (
    'RETURN [date"2024-02-29", time"12:34:56.789", '
    'timestamp"2024-01-01T12:00:00.000000001", interval"P1Y2M3DT4H5M6.5S", '
    '<bigdecimal> "79228162514264337593543950336.50", <regex> "a.*"]'
)
_CALENDAR_EXPECTED: Any = [
    PlainDate(2024, 2, 29),
    PlainTime(12, 34, 56, 789_000),
    Timestamp(2024, 1, 1, 12, nanosecond=1),
    Interval(14, 3, 14_706_500_000),
    BigDecimal("79228162514264337593543950336.50"),
    Regex("a.*"),
]
_CALENDAR_KINDS = ["date", "time", "timestamp", "interval", "bigdecimal", "regex"]
_KINDS_OF = "RETURN $v.map(|$x| type::of($x))"


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


def _calendar(raw: Any) -> Any:
    """The values of ``_CALENDAR``, skipping on a 4.0 build that predates them."""
    if "error" in raw or raw["result"][0]["status"] != "OK":
        pytest.skip("the server speaks cbor.2 but has no date, time or interval kinds")
    return raw


def _check_calendar(read: Any, echoed: Any, kinds: Any) -> None:
    _check(_calendar(read), _CALENDAR_EXPECTED)
    _check(echoed, _CALENDAR_EXPECTED)
    assert _value(kinds) == _CALENDAR_KINDS


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


def test_blocking_ws_reads_and_sends_the_calendar_kinds(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    db = blocking_ws_connection
    _require_cbor2(db)
    read = db.query_raw(_CALENDAR)
    _calendar(read)
    sent = {"v": _CALENDAR_EXPECTED}
    _check_calendar(read, db.query_raw(_ECHO, sent), db.query_raw(_KINDS_OF, sent))


async def test_async_ws_reads_and_sends_the_calendar_kinds(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    db = async_ws_connection
    _require_cbor2(db)
    read = await db.query_raw(_CALENDAR)
    _calendar(read)
    sent = {"v": _CALENDAR_EXPECTED}
    echoed, kinds = await db.query_raw(_ECHO, sent), await db.query_raw(_KINDS_OF, sent)
    _check_calendar(read, echoed, kinds)


def test_blocking_http_reads_and_sends_the_calendar_kinds(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    db = blocking_http_connection
    _require_cbor2(db)
    read = db.query_raw(_CALENDAR)
    _calendar(read)
    sent = {"v": _CALENDAR_EXPECTED}
    _check_calendar(read, db.query_raw(_ECHO, sent), db.query_raw(_KINDS_OF, sent))


async def test_async_http_reads_and_sends_the_calendar_kinds(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    db = async_http_connection
    _require_cbor2(db)
    read = await db.query_raw(_CALENDAR)
    _calendar(read)
    sent = {"v": _CALENDAR_EXPECTED}
    echoed, kinds = await db.query_raw(_ECHO, sent), await db.query_raw(_KINDS_OF, sent)
    _check_calendar(read, echoed, kinds)


def test_the_calendar_kinds_are_widened_over_plain_cbor(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Over ``cbor`` each goes out as the server would widen it, as a type it has."""
    if blocking_ws_connection.wire_format != "cbor":
        pytest.skip("the server speaks cbor.2")
    sent: Any = [
        PlainDate(2024, 2, 29),
        PlainTime(12, 34, 56, 789_000),
        Timestamp(2024, 1, 1, 12),
        Interval(14, 3, 14_706_500_000),
        BigDecimal("1.50"),
    ]
    widened = [
        datetime(2024, 2, 29, tzinfo=timezone.utc),
        Duration(45_296_789_000_000),
        datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
        "P1Y2M3DT4H5M6.5S",
        Decimal("1.5"),
    ]
    assert _value(blocking_ws_connection.query_raw(_ECHO, {"v": sent})) == widened
