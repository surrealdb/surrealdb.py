"""SurrealDB 4.0's date, time, timestamp and interval, and how they cross the wire."""

import pickle
from datetime import date, datetime, time, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from surrealdb import Interval, PlainDate, PlainTime, PreciseDatetime, Timestamp
from surrealdb.data import cbor
from surrealdb.errors import UnexpectedResponseError

_EPOCH = date(1970, 1, 1)


@given(st.dates())
def test_a_date_counts_days_as_the_standard_library_does(day: date) -> None:
    plain = PlainDate.from_date(day)
    assert plain.days == (day - _EPOCH).days
    assert (plain.year, plain.month, plain.day) == (day.year, day.month, day.day)
    assert plain.to_date() == day


@given(st.integers(PlainDate.NEG_INFINITY.days, PlainDate.INFINITY.days))
def test_every_day_surrealdb_holds_has_its_own_fields(days: int) -> None:
    plain = PlainDate.from_days(days)
    assert PlainDate(plain.year, plain.month, plain.day).days == days
    assert PlainDate.parse(str(plain)) == plain


def test_the_infinities_are_the_ends_of_the_range() -> None:
    assert PlainDate(262142, 12, 31) == PlainDate.INFINITY
    assert PlainDate(-262143, 1, 1) == PlainDate.NEG_INFINITY
    assert PlainDate.INFINITY.days == 95026236
    assert PlainDate.NEG_INFINITY.days == -96465292
    assert PlainDate.INFINITY.is_infinite
    assert not PlainDate(2024, 2, 29).is_infinite
    assert PlainDate.NEG_INFINITY < PlainDate(1970, 1, 1) < PlainDate.INFINITY


@pytest.mark.parametrize(
    ("text", "fields"),
    [
        ("2024-02-29", (2024, 2, 29)),
        ("0000-01-01", (0, 1, 1)),
        ("+10000-01-01", (10000, 1, 1)),
        ("-0001-12-31", (-1, 12, 31)),
    ],
)
def test_a_date_reads_and_prints_as_the_server_does(
    text: str, fields: tuple[int, int, int]
) -> None:
    plain = PlainDate.parse(text)
    assert (plain.year, plain.month, plain.day) == fields
    assert str(plain) == text


def test_the_infinities_read_and_print_as_words() -> None:
    assert PlainDate.parse("infinity") == PlainDate.INFINITY
    assert PlainDate.parse("-infinity") == PlainDate.NEG_INFINITY
    assert str(PlainDate.INFINITY) == "infinity"
    assert str(PlainDate.NEG_INFINITY) == "-infinity"
    assert repr(PlainDate.INFINITY) == "PlainDate.INFINITY"


@pytest.mark.parametrize(
    "text", ["2024-2-29", "2024-02-30", "2023-02-29", "٢٠٢٤-٠٢-٢٩", "", "today"]
)
def test_a_date_that_is_not_one_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        PlainDate.parse(text)


@pytest.mark.parametrize(
    "fields", [(2023, 2, 29), (2024, 13, 1), (2024, 0, 1), (2024, 1, 0), (262143, 1, 1)]
)
def test_fields_that_name_no_date_are_refused(fields: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        PlainDate(*fields)


def test_a_field_that_is_not_an_int_is_refused() -> None:
    with pytest.raises(TypeError):
        PlainDate(2024.0, 1, 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        PlainDate.from_days(True)


def test_a_date_past_9999_has_no_datetime_date() -> None:
    with pytest.raises(ValueError, match="years 1 to 9999"):
        PlainDate(10000, 1, 1).to_date()
    with pytest.raises(ValueError):
        PlainDate.INFINITY.to_date()


def test_a_date_is_a_value() -> None:
    plain = PlainDate(2024, 2, 29)
    assert plain == PlainDate.parse("2024-02-29")
    assert len({plain, PlainDate.from_days(plain.days)}) == 1
    assert plain != date(2024, 2, 29)
    assert eval(repr(plain), {"PlainDate": PlainDate}) == plain
    assert pickle.loads(pickle.dumps(plain)) == plain


def test_a_date_is_tag_100_over_cbor2() -> None:
    raw = cbor.encode(PlainDate(2024, 2, 29), v2=True)
    assert raw.hex() == "d864194d46"
    assert cbor.decode(raw, v2=True) == PlainDate(2024, 2, 29)


def test_a_date_is_midnight_utc_over_plain_cbor() -> None:
    raw = cbor.encode(PlainDate(2024, 2, 29))
    assert raw.hex() == "cc821a65dfc90000"
    assert cbor.decode(raw) == datetime(2024, 2, 29, tzinfo=timezone.utc)


def test_a_standard_library_date_is_sent_as_a_date() -> None:
    assert cbor.encode(date(2024, 2, 29), v2=True).hex() == "d864194d46"
    assert cbor.encode(date(2024, 2, 29)).hex() == "cc821a65dfc90000"


class _Moment(datetime):
    pass


@pytest.mark.parametrize(
    "moment",
    [
        datetime(2024, 2, 29, tzinfo=timezone.utc),
        _Moment(2024, 2, 29, tzinfo=timezone.utc),
    ],
    ids=["datetime", "a datetime subclass"],
)
def test_a_datetime_is_still_sent_as_a_datetime(moment: datetime) -> None:
    assert cbor.encode(moment, v2=True).hex() == "cc821a65dfc90000"


def test_a_date_is_refused_outside_cbor2() -> None:
    with pytest.raises(UnexpectedResponseError, match=r"outside cbor\.2"):
        cbor.decode(bytes.fromhex("d864194d46"))


def test_a_time_holds_nanoseconds_and_24_00() -> None:
    late = PlainTime(23, 59, 59, 999_999, 999)
    assert late.nanoseconds == 86_399_999_999_999
    assert (late.hour, late.minute, late.second) == (23, 59, 59)
    assert (late.microsecond, late.nanosecond) == (999_999, 999)
    assert PlainTime(24).nanoseconds == 86_400_000_000_000
    with pytest.raises(ValueError, match="24:00:00"):
        PlainTime(24, 0, 0, 0, 1)
    with pytest.raises(ValueError):
        PlainTime(25)
    with pytest.raises(ValueError):
        PlainTime.from_nanoseconds(-1)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (PlainTime(1, 2, 3), "01:02:03"),
        (PlainTime(12, 34, 56, 789_000), "12:34:56.789"),
        (PlainTime(0, 0, 0, 1), "00:00:00.000001"),
        (PlainTime(0, 0, 0, 0, 1), "00:00:00.000000001"),
        (PlainTime(24), "24:00:00"),
    ],
)
def test_a_time_prints_the_fraction_as_the_server_does(
    value: PlainTime, text: str
) -> None:
    assert str(value) == text
    assert PlainTime.parse(text) == value


@pytest.mark.parametrize(
    "text", ["12:60", "12:00:60", "24:00:01", "12:00:00.1234567891", "noon"]
)
def test_a_time_that_is_not_one_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        PlainTime.parse(text)


def test_a_time_converts_to_and_from_the_standard_library() -> None:
    assert PlainTime.from_time(time(12, 34, 56, 789)) == PlainTime(12, 34, 56, 789)
    assert PlainTime(12, 34, 56, 789, 999).to_time() == time(12, 34, 56, 789)
    with pytest.raises(ValueError, match="no zone"):
        PlainTime.from_time(time(12, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="24:00:00"):
        PlainTime(24).to_time()


def test_a_time_is_tag_189_over_cbor2_and_a_duration_otherwise() -> None:
    noon = PlainTime(12, 34, 56, 789_000)
    assert cbor.encode(noon, v2=True).hex() == "d8bd1b000029327b048f40"
    assert cbor.decode(cbor.encode(noon, v2=True), v2=True) == noon
    assert cbor.encode(noon).hex() == "ce8219b0f01a2f072f40"
    assert cbor.encode(time(12, 34, 56, 789_000), v2=True).hex() == (
        "d8bd1b000029327b048f40"
    )


def test_a_timestamp_holds_any_instant_surrealdb_does() -> None:
    stamp = Timestamp(2024, 1, 1, 12, nanosecond=1)
    assert stamp.seconds_and_nanos == (1_704_110_400, 1)
    assert Timestamp.from_seconds_and_nanos(-1, 500_000_000) == Timestamp(
        1969, 12, 31, 23, 59, 59, 500_000
    )
    assert Timestamp.INFINITY.seconds_and_nanos == (8_210_266_876_799, 999_999_999)
    assert Timestamp.NEG_INFINITY.seconds_and_nanos == (-8_334_601_228_800, 0)
    assert Timestamp.NEG_INFINITY < stamp < Timestamp.INFINITY
    with pytest.raises(ValueError):
        Timestamp.from_seconds_and_nanos(0, 1_000_000_000)
    with pytest.raises(ValueError):
        Timestamp.from_seconds_and_nanos(8_210_266_876_800, 0)


@pytest.mark.parametrize(
    "text",
    [
        "1970-01-01T00:00:00",
        "2024-01-01T12:00:00.000000001",
        "1969-12-31T23:59:59.500",
        "+10000-01-01T00:00:00",
        "infinity",
        "-infinity",
    ],
)
def test_a_timestamp_reads_and_prints_as_the_server_does(text: str) -> None:
    assert str(Timestamp.parse(text)) == text


@pytest.mark.parametrize(
    "text", ["2024-01-01", "2024-01-01T24:00:00", "2024-01-01T12:00:00Z", "now"]
)
def test_a_timestamp_that_is_not_one_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        Timestamp.parse(text)


def test_a_timestamp_converts_to_and_from_a_naive_datetime() -> None:
    precise = PreciseDatetime(2024, 1, 1, 12, 0, 0, 5, nanosecond=7)
    stamp = Timestamp.from_datetime(precise)
    assert stamp == Timestamp(2024, 1, 1, 12, 0, 0, 5, 7)
    back = stamp.to_datetime()
    assert back == datetime(2024, 1, 1, 12, 0, 0, 5)
    assert back.tzinfo is None
    assert back.nanosecond == 7
    with pytest.raises(ValueError, match="no zone"):
        Timestamp.from_datetime(datetime(2024, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="years 1 to 9999"):
        Timestamp.INFINITY.to_datetime()


def test_a_timestamp_is_tag_190_over_cbor2_and_a_datetime_otherwise() -> None:
    stamp = Timestamp(2024, 1, 1, 12, nanosecond=1)
    assert cbor.encode(stamp, v2=True).hex() == "d8be821a6592a94001"
    assert cbor.decode(cbor.encode(stamp, v2=True), v2=True) == stamp
    assert cbor.encode(stamp).hex() == "cc821a6592a94001"


def test_a_naive_datetime_is_still_sent_as_a_datetime() -> None:
    assert cbor.encode(datetime(2024, 1, 1, 12), v2=True).hex() == "cc821a6592a94000"


def test_an_interval_keeps_its_parts() -> None:
    interval = Interval(14, 3, 14_706_500_000)
    assert (interval.months, interval.days, interval.microseconds) == (
        14,
        3,
        14_706_500_000,
    )
    assert repr(interval) == "Interval(months=14, days=3, microseconds=14706500000)"
    assert repr(Interval()) == "Interval()"
    with pytest.raises(ValueError):
        Interval(months=2**31)
    with pytest.raises(ValueError):
        Interval(microseconds=2**63)
    with pytest.raises(TypeError):
        Interval(days=True)


@pytest.mark.parametrize(
    ("interval", "text"),
    [
        (Interval(14, 3, 14_706_500_000), "P1Y2M3DT4H5M6.5S"),
        (Interval(), "PT0S"),
        (Interval(months=-1), "P-1M"),
        (Interval(months=-14), "P-1Y-2M"),
        (Interval(microseconds=-1_500_000), "PT-1.5S"),
        (Interval(days=7), "P7D"),
        (Interval(microseconds=1), "PT0.000001S"),
        (Interval(days=1, microseconds=-3_600_000_000), "P1DT-1H"),
    ],
)
def test_an_interval_prints_as_iso_8601(interval: Interval, text: str) -> None:
    assert str(interval) == text


def test_intervals_compare_normalised_as_the_server_does() -> None:
    month, thirty_days = Interval(months=1), Interval(days=30)
    assert month == thirty_days
    assert hash(month) == hash(thirty_days)
    assert len({month, thirty_days}) == 1
    assert (month.months, month.days) != (thirty_days.months, thirty_days.days)
    assert Interval(days=1) == Interval(microseconds=86_400_000_000)


def test_an_interval_is_tag_191_over_cbor2_and_its_text_otherwise() -> None:
    interval = Interval(14, 3, 14_706_500_000)
    assert cbor.encode(interval, v2=True).hex() == "d8bf830e031b000000036c9361a0"
    decoded = cbor.decode(cbor.encode(interval, v2=True), v2=True)
    assert (decoded.months, decoded.days, decoded.microseconds) == (
        14,
        3,
        14_706_500_000,
    )
    assert cbor.decode(cbor.encode(interval)) == "P1Y2M3DT4H5M6.5S"


@pytest.mark.parametrize(
    "hex_",
    ["d8bd00", "d8be820000", "d8bf83000000"],
    ids=["time", "timestamp", "interval"],
)
def test_the_calendar_tags_are_refused_outside_cbor2(hex_: str) -> None:
    with pytest.raises(UnexpectedResponseError, match=r"outside cbor\.2"):
        cbor.decode(bytes.fromhex(hex_))
