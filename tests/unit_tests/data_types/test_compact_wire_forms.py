"""The SDK sends datetimes, UUIDs and durations in the forms every server reads.

SurrealDB 4.0 refuses CBOR tag 0 (a datetime as text), tag 9 (a UUID as text)
and tag 13 (a duration as text) in a request. The forms it does read - tag 12
``[seconds, nanoseconds]``, tag 37 (16 bytes) and tag 14 ``[seconds,
nanoseconds]`` - have been read by every server since 1.5.0, so sending them is
safe against older servers too. The tests here pin the exact bytes, because a
decode of what was encoded cannot tell the two forms apart: the decoder reads
both.
"""

import datetime as dt
import uuid
from typing import Any

import pytest

from surrealdb import PreciseDatetime
from surrealdb.cbor import CBORTag, dumps
from surrealdb.data.cbor import decode, encode
from surrealdb.data.types.datetime import Datetime
from surrealdb.data.types.duration import Duration

UTC = dt.timezone.utc


def _tags(data: bytes) -> set[int]:
    """Every semantic tag in a CBOR item, found without decoding any of them."""
    seen: set[int] = set()

    def argument(info: int, at: int) -> tuple[int, int]:
        if info < 24:
            return info, at
        width = {24: 1, 25: 2, 26: 4, 27: 8}[info]
        return int.from_bytes(data[at : at + width], "big"), at + width

    def item(at: int) -> int:
        major, info = data[at] >> 5, data[at] & 0x1F
        value, at = argument(info, at + 1)
        if major in (2, 3):
            return at + value
        if major == 4:
            for _ in range(value):
                at = item(at)
        elif major == 5:
            for _ in range(value * 2):
                at = item(at)
        elif major == 6:
            seen.add(value)
            at = item(at)
        return at

    assert item(0) == len(data)
    return seen


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(dt.datetime(2026, 1, 1, tzinfo=UTC), "cc821a6955b90000", id="utc"),
        pytest.param(
            dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC),
            "cc821a6955b9001a075bca00",
            id="microseconds",
        ),
        pytest.param(dt.datetime(1970, 1, 1, tzinfo=UTC), "cc820000", id="epoch"),
        pytest.param(
            dt.datetime(1969, 12, 31, 23, 59, 59, 500000, tzinfo=UTC),
            "cc82201a1dcd6500",
            id="before the epoch: negative seconds, positive nanoseconds",
        ),
        pytest.param(
            dt.datetime(1, 1, 1, tzinfo=UTC), "cc823b0000000e7791f6ff00", id="year 1"
        ),
        pytest.param(
            dt.datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
            "cc821b0000003afff4417f1a3b9ac618",
            id="year 9999",
        ),
        pytest.param(
            dt.datetime(2026, 1, 1, 5, tzinfo=dt.timezone(dt.timedelta(hours=5))),
            "cc821a6955b90000",
            id="a positive offset is the same instant",
        ),
        pytest.param(
            dt.datetime(2025, 12, 31, 19, tzinfo=dt.timezone(-dt.timedelta(hours=5))),
            "cc821a6955b90000",
            id="a negative offset is the same instant",
        ),
        pytest.param(
            dt.datetime(2026, 1, 1),
            "cc821a6955b90000",
            id="a naive datetime is read as UTC",
        ),
        pytest.param(
            PreciseDatetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC, nanosecond=789),
            "cc821a6955b9001a075bcd15",
            id="nanoseconds beyond the microsecond are kept",
        ),
        pytest.param(
            PreciseDatetime(2026, 1, 1, nanosecond=1),
            "cc821a6955b90001",
            id="a naive precise datetime is read as UTC",
        ),
        pytest.param(
            PreciseDatetime(
                2026,
                1,
                1,
                5,
                tzinfo=dt.timezone(dt.timedelta(hours=5)),
                nanosecond=999,
            ),
            "cc821a6955b9001903e7",
            id="a precise datetime with an offset",
        ),
    ],
)
def test_a_datetime_is_sent_as_tag_12(value: dt.datetime, expected: str) -> None:
    assert encode(value).hex() == expected


@pytest.mark.parametrize(
    ("text", "seconds", "nanoseconds"),
    [
        ("2026-01-01T00:00:00Z", 1767225600, 0),
        ("2026-01-01T00:00:00.123456789Z", 1767225600, 123456789),
        ("2026-01-01T00:00:00.5Z", 1767225600, 500000000),
        ("2026-01-01T00:00:00.123456+00:00", 1767225600, 123456000),
        ("2026-01-01T05:00:00+05:00", 1767225600, 0),
        ("2025-12-31T19:00:00-05:00", 1767225600, 0),
        ("2025-12-31T19:00:00-0500", 1767225600, 0),
        ("2026-01-01 00:00:00z", 1767225600, 0),
        ("2026-01-01T00:00:00", 1767225600, 0),
        ("1969-12-31T23:59:59.999999999Z", -1, 999999999),
    ],
)
def test_the_datetime_wrapper_is_sent_as_tag_12(
    text: str, seconds: int, nanoseconds: int
) -> None:
    assert encode(Datetime(text)) == dumps(
        CBORTag(12, [seconds, nanoseconds]),
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "yesterday",
        "2026-01-01",
        "2026-01-01T00:00Z",
        "2026-01-01T00:00:00.1234567890Z",
    ],
)
def test_a_datetime_wrapper_that_is_not_rfc_3339_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="RFC 3339"):
        encode(Datetime(text))


def test_a_datetime_wrapper_with_an_impossible_date_is_refused() -> None:
    with pytest.raises(ValueError):
        encode(Datetime("2026-02-30T00:00:00Z"))


def test_a_uuid_is_sent_as_tag_37_with_sixteen_bytes() -> None:
    value = uuid.UUID("12345678-1234-5678-1234-567812345678")

    assert encode(value).hex() == "d82550" + "12345678123456781234567812345678"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Duration.parse("1h30m"), "ce8219151800"),
        (Duration.parse("0s"), "ce820000"),
        (Duration.parse("1ns"), "ce820001"),
        (Duration.parse("1s500ms"), "ce82011a1dcd6500"),
        (Duration.parse("1y999999999ns"), "ce821a01e133801a3b9ac9ff"),
    ],
)
def test_a_duration_is_sent_as_tag_14(value: Duration, expected: str) -> None:
    assert encode(value).hex() == expected


def test_nothing_is_sent_as_tag_0_9_or_13() -> None:
    nested: dict[str, Any] = {
        "at": dt.datetime(2026, 1, 1, tzinfo=UTC),
        "naive": dt.datetime(2026, 1, 1),
        "precise": PreciseDatetime(2026, 1, 1, nanosecond=7),
        "wrapped": Datetime("2026-01-01T00:00:00Z"),
        "id": uuid.uuid4(),
        "for": Duration.parse("2d"),
        "inside": [
            {"deep": [dt.datetime.now(UTC), uuid.uuid4(), Duration.parse("1s")]}
        ],
        "as_set": {1, 2},
        "missing": None,
    }

    tags = _tags(encode(nested))

    assert {0, 9, 13}.isdisjoint(tags)
    assert {12, 14, 37} <= tags


@pytest.mark.parametrize(
    "value",
    [
        dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC),
        dt.datetime(1969, 12, 31, 23, 59, 59, 500000, tzinfo=UTC),
        dt.datetime(1, 1, 1, tzinfo=UTC),
        dt.datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 5, tzinfo=dt.timezone(dt.timedelta(hours=5))),
    ],
)
def test_a_datetime_round_trips(value: dt.datetime) -> None:
    decoded = decode(encode(value))

    assert isinstance(decoded, dt.datetime)
    assert decoded == value
    assert decoded.utcoffset() == dt.timedelta(0)


def test_a_naive_datetime_round_trips_as_utc() -> None:
    assert decode(encode(dt.datetime(2026, 1, 1, 12))) == dt.datetime(
        2026, 1, 1, 12, tzinfo=UTC
    )


def test_nanoseconds_round_trip() -> None:
    sent = PreciseDatetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC, nanosecond=789)

    received = decode(encode(sent))

    assert isinstance(received, PreciseDatetime)
    assert (received.microsecond, received.nanosecond) == (123456, 789)
    assert encode(received) == encode(sent)


def test_the_wrapper_round_trips_with_all_nine_digits() -> None:
    received = decode(encode(Datetime("2026-01-01T00:00:00.123456789Z")))

    assert isinstance(received, PreciseDatetime)
    assert (received.microsecond, received.nanosecond) == (123456, 789)


def test_a_uuid_round_trips() -> None:
    value = uuid.uuid4()

    assert decode(encode(value)) == value


@pytest.mark.parametrize("text", ["0s", "1ns", "1h30m", "1y999999999ns"])
def test_a_duration_round_trips(text: str) -> None:
    assert decode(encode(Duration.parse(text))) == Duration.parse(text)


def test_a_datetime_given_as_text_is_still_decoded() -> None:
    received = decode(dumps(CBORTag(0, "2026-01-01T00:00:00.123456Z")))

    assert received == dt.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC)


def test_a_uuid_given_as_text_is_still_decoded() -> None:
    value = uuid.uuid4()

    assert decode(dumps(CBORTag(9, str(value)))) == value


def test_a_duration_given_as_text_is_still_decoded() -> None:
    assert decode(dumps(CBORTag(13, "1h30m"))) == Duration.parse("1h30m")
    assert decode(dumps(CBORTag(13, [5400, 0]))) == Duration.parse("1h30m")


@pytest.mark.parametrize("value", [2**63, 2**64 - 1, -(2**63) - 1, 2**70])
def test_an_integer_outside_i64_is_refused(value: int) -> None:
    with pytest.raises(ValueError, match="signed 64-bit"):
        encode(value)


@pytest.mark.parametrize("value", [2**63 - 1, -(2**63)])
def test_the_i64_limits_are_sent(value: int) -> None:
    assert decode(encode(value)) == value


def test_none_is_sent_as_tag_6_with_null() -> None:
    assert encode(None).hex() == "c6f6"
    assert _tags(encode({"a": None, "b": [None]})) == {6}
