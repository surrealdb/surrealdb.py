"""Datetimes go to SurrealDB as tag 12 ``[seconds, nanoseconds]``.

SurrealDB 4 refuses tag 0 (a datetime as text), and every 2.x and 3.x server
reads tag 12, so it is the one form that works everywhere.
"""

import datetime as dt

import pytest

from surrealdb import Datetime, PreciseDatetime
from surrealdb.cbor import CBORTag, loads
from surrealdb.data.cbor import decode, encode
from surrealdb.data.types import constants
from surrealdb.data.types.datetime import parse_instant

UTC = dt.timezone.utc


def _frame(value: object) -> CBORTag:
    tag = loads(encode(value))
    assert isinstance(tag, CBORTag)
    return tag


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (dt.datetime(2026, 1, 1, tzinfo=UTC), [1767225600, 0]),
        (dt.datetime(2026, 1, 1), [1767225600, 0]),
        (
            dt.datetime(2026, 1, 1, 12, tzinfo=dt.timezone(dt.timedelta(hours=12))),
            [1767225600, 0],
        ),
        (dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC), [1767225600, 123456000]),
        (
            PreciseDatetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC, nanosecond=789),
            [1767225600, 123456789],
        ),
        (dt.datetime(1969, 12, 31, 23, 59, 59, 500000, tzinfo=UTC), [-1, 500000000]),
        (Datetime("2026-01-01T00:00:00Z"), [1767225600, 0]),
        (Datetime("2026-01-01T00:00:00.000000007Z"), [1767225600, 7]),
        (Datetime("2026-01-01T02:00:00.5+02:00"), [1767225600, 500000000]),
        (Datetime("2026-01-01T00:00:00"), [1767225600, 0]),
        (Datetime("2026-01-01"), [1767225600, 0]),
    ],
)
def test_a_datetime_is_sent_as_seconds_and_nanoseconds(
    value: object, expected: list[int]
) -> None:
    frame = _frame(value)

    assert frame.tag == constants.TAG_DATETIME_COMPACT
    assert frame.value == expected


def test_a_nested_datetime_is_sent_as_tag_12() -> None:
    params = loads(encode({"at": [dt.datetime(2026, 1, 1, tzinfo=UTC)]}))

    assert params["at"][0] == CBORTag(constants.TAG_DATETIME_COMPACT, [1767225600, 0])


@pytest.mark.parametrize(
    "value",
    [
        dt.datetime(2026, 1, 1, 12, 30, 45, 123456, tzinfo=UTC),
        PreciseDatetime(2026, 1, 1, 12, 30, 45, 123456, tzinfo=UTC, nanosecond=789),
        PreciseDatetime(1900, 6, 1, 0, 0, 0, 1, tzinfo=UTC, nanosecond=1),
    ],
)
def test_a_datetime_round_trips_to_the_nanosecond(value: dt.datetime) -> None:
    decoded = decode(encode(value))

    assert decoded == value
    assert getattr(decoded, "nanosecond", 0) == getattr(value, "nanosecond", 0)


def test_parse_instant_keeps_nanoseconds_and_zone() -> None:
    value = parse_instant("2026-01-01T12:00:00.123456789-05:30")

    assert value.microsecond == 123456
    assert value.nanosecond == 789
    assert value.utcoffset() == -dt.timedelta(hours=5, minutes=30)


@pytest.mark.parametrize(
    "text", ["", "yesterday", "2026-13-01T00:00:00Z", "2026-01-01T00:00:00.1234567890Z"]
)
def test_a_datetime_that_is_not_one_is_refused_before_it_is_sent(text: str) -> None:
    with pytest.raises(ValueError, match="not an ISO 8601 datetime"):
        encode(Datetime(text))
