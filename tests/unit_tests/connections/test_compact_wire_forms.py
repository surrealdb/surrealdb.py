"""A server accepts the datetime, UUID and duration forms the SDK now sends.

``tests/unit_tests/data_types/test_compact_wire_forms.py`` pins the bytes. This
checks what only a server can: that tag 12, tag 37 and tag 14 are read as a
datetime, a UUID and a duration, with every digit intact, on each transport.
"""

import datetime as dt
import uuid
from typing import Any

import pytest

from surrealdb import PreciseDatetime
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.datetime import Datetime
from surrealdb.data.types.duration import Duration

UTC = dt.timezone.utc
VALUES: list[Any] = [
    pytest.param(
        dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC),
        "2026-01-01T00:00:00.123456Z",
        id="datetime",
    ),
    pytest.param(
        dt.datetime(2026, 1, 1, 5, tzinfo=dt.timezone(dt.timedelta(hours=5))),
        "2026-01-01T00:00:00Z",
        id="datetime with an offset",
    ),
    pytest.param(
        dt.datetime(1969, 12, 31, 23, 59, 59, 500000, tzinfo=UTC),
        "1969-12-31T23:59:59.500Z",
        id="datetime before the epoch",
    ),
    pytest.param(
        PreciseDatetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC, nanosecond=789),
        "2026-01-01T00:00:00.123456789Z",
        id="nanoseconds",
    ),
    pytest.param(
        Datetime("2026-01-01T00:00:00.123456789Z"),
        "2026-01-01T00:00:00.123456789Z",
        id="datetime wrapper",
    ),
    pytest.param(
        uuid.UUID("12345678-1234-5678-1234-567812345678"),
        "12345678-1234-5678-1234-567812345678",
        id="uuid",
    ),
    pytest.param(Duration.parse("1h30m"), "1h30m", id="duration"),
    pytest.param(
        Duration.parse("1y999999999ns"), "1y999ms999µs999ns", id="long duration"
    ),
]


def _check(value: Any, as_text: str, returned: Any, text: Any) -> None:
    assert text == as_text
    if isinstance(value, Datetime):
        assert isinstance(returned, PreciseDatetime)
        assert returned.isoformat_with_nanoseconds() == as_text
        return
    assert returned == value
    assert isinstance(returned, type(value))
    if isinstance(value, PreciseDatetime):
        assert returned.nanosecond == value.nanosecond


@pytest.mark.parametrize(("value", "as_text"), VALUES)
def test_blocking_ws_reads_the_forms(
    blocking_ws_connection: BlockingWsSurrealConnection, value: Any, as_text: str
) -> None:
    returned = blocking_ws_connection.query("RETURN $v;", {"v": value}).first()
    text = blocking_ws_connection.query("RETURN <string>$v;", {"v": value}).first()

    _check(value, as_text, returned, text)


@pytest.mark.parametrize(("value", "as_text"), VALUES)
def test_blocking_http_reads_the_forms(
    blocking_http_connection: BlockingHttpSurrealConnection, value: Any, as_text: str
) -> None:
    returned = blocking_http_connection.query("RETURN $v;", {"v": value}).first()
    text = blocking_http_connection.query("RETURN <string>$v;", {"v": value}).first()

    _check(value, as_text, returned, text)


@pytest.mark.parametrize(("value", "as_text"), VALUES)
async def test_async_ws_reads_the_forms(
    async_ws_connection: AsyncWsSurrealConnection, value: Any, as_text: str
) -> None:
    returned = await async_ws_connection.query("RETURN $v;", {"v": value}).first()
    text = await async_ws_connection.query("RETURN <string>$v;", {"v": value}).first()

    _check(value, as_text, returned, text)


@pytest.mark.parametrize(("value", "as_text"), VALUES)
async def test_async_http_reads_the_forms(
    async_http_connection: AsyncHttpSurrealConnection, value: Any, as_text: str
) -> None:
    returned = await async_http_connection.query("RETURN $v;", {"v": value}).first()
    text = await async_http_connection.query("RETURN <string>$v;", {"v": value}).first()

    _check(value, as_text, returned, text)
