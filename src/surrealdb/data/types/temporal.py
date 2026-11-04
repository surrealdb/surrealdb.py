"""SurrealDB 4.0's calendar kinds: date, time, timestamp and interval.

They are the kinds SurrealQL shares with PostgreSQL and MySQL. Over ``cbor.2``
each has its own tag (100, 189, 190 and 191) and is read back as the class here.
Plain ``cbor`` (servers before 4.0) has no tag for them, so they are sent as the
server widens them: a date or timestamp as a datetime (a timestamp's wall clock
read as UTC, a date at midnight UTC), a time as a duration since midnight and an
interval as its ISO 8601 text.

A date or timestamp can be ``infinity`` or ``-infinity``, as in PostgreSQL.
They are the last and first values SurrealDB holds, in the years -262143 to
262142, so they compare and sort as the dates they are. ``datetime`` holds only
the years 1 to 9999 and has no infinities, which is why these are classes of
their own; each converts to and from its ``datetime`` counterpart.
"""

from __future__ import annotations

import re
from datetime import MAXYEAR, MINYEAR, date, datetime, time
from functools import total_ordering
from typing import Any, ClassVar

from surrealdb.data.types.datetime import PreciseDatetime

_NANOS = 1_000_000_000
_SECONDS_PER_DAY = 86_400
_NANOS_PER_DAY = _SECONDS_PER_DAY * _NANOS
_MICROS_PER_DAY = _SECONDS_PER_DAY * 1_000_000
_MICROS_PER_MONTH = 30 * _MICROS_PER_DAY

_I32_MIN = -(2**31)
_I32_MAX = 2**31 - 1
_I64_MIN = -(2**63)
_I64_MAX = 2**63 - 1


def _days_from_civil(year: int, month: int, day: int) -> int:
    """Days since 1970-01-01 of a proleptic Gregorian date (Howard Hinnant's)."""
    y = year - 1 if month <= 2 else year
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (month - 3 if month > 2 else month + 9) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _civil_from_days(days: int) -> tuple[int, int, int]:
    """The proleptic Gregorian ``(year, month, day)`` *days* after 1970-01-01."""
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + 3 if mp < 10 else mp - 9
    return yoe + era * 400 + (1 if month <= 2 else 0), month, day


# The days and instants SurrealDB holds, chrono's range; its two ends are
# `-infinity` and `infinity`.
_MIN_DAYS = _days_from_civil(-262143, 1, 1)
_MAX_DAYS = _days_from_civil(262142, 12, 31)
_MIN_SECONDS = _MIN_DAYS * _SECONDS_PER_DAY
_MAX_SECONDS = _MAX_DAYS * _SECONDS_PER_DAY + _SECONDS_PER_DAY - 1

# ASCII digits only: `\d` would read other scripts' digits as well.
_DATE = re.compile(r"([+-]?[0-9]{4,6})-([0-9]{2})-([0-9]{2})")
_TIME = re.compile(r"([0-9]{1,2}):([0-9]{2})(?::([0-9]{2})(?:\.([0-9]{1,9}))?)?")
_TIMESTAMP = re.compile(r"([^T ]+)[T ](.+)")


def _int(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}: {value!r}")
    return int(value)


def _within(name: str, value: Any, low: int, high: int) -> int:
    number = _int(name, value)
    if not low <= number <= high:
        raise ValueError(f"{name} must be {low} to {high}, got {number}")
    return number


def _days(year: Any, month: Any, day: Any) -> int:
    year, month, day = _int("year", year), _int("month", month), _int("day", day)
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise ValueError(f"{year}-{month:02d}-{day:02d} is not a date")
    days = _days_from_civil(year, month, day)
    if _civil_from_days(days) != (year, month, day):
        raise ValueError(f"{_format_year(year)}-{month:02d} has no day {day}")
    if not _MIN_DAYS <= days <= _MAX_DAYS:
        raise ValueError(
            f"{_format_year(year)}-{month:02d}-{day:02d} is outside the dates "
            "SurrealDB holds, -262143-01-01 to +262142-12-31"
        )
    return days


def _format_year(year: int) -> str:
    if 0 <= year <= 9999:
        return f"{year:04d}"
    return f"{'-' if year < 0 else '+'}{abs(year):04d}"


def _format_date(days: int) -> str:
    year, month, day = _civil_from_days(days)
    return f"{_format_year(year)}-{month:02d}-{day:02d}"


def _format_fraction(nanos: int) -> str:
    """The fraction SurrealDB prints: none, or the shortest of 3, 6 or 9 digits that is exact."""
    if nanos == 0:
        return ""
    if nanos % 1_000_000 == 0:
        return f".{nanos // 1_000_000:03d}"
    if nanos % 1_000 == 0:
        return f".{nanos // 1_000:06d}"
    return f".{nanos:09d}"


def _format_time(nanos: int) -> str:
    seconds, fraction = divmod(nanos, _NANOS)
    return (
        f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
        f"{_format_fraction(fraction)}"
    )


def _parse_date(text: str) -> int:
    word = text.strip()
    if word == "infinity":
        return _MAX_DAYS
    if word == "-infinity":
        return _MIN_DAYS
    match = _DATE.fullmatch(word)
    if match is None:
        raise ValueError(
            f"{text!r} is not a date; pass one such as '2024-02-29', "
            "'+10000-01-01' or 'infinity'"
        )
    return _days(int(match[1]), int(match[2]), int(match[3]))


def _parse_time(text: str) -> int:
    match = _TIME.fullmatch(text.strip())
    if match is not None:
        hours, minutes, seconds = int(match[1]), int(match[2]), int(match[3] or 0)
        nanos = (hours * 3600 + minutes * 60 + seconds) * _NANOS
        nanos += int((match[4] or "").ljust(9, "0"))
        if minutes < 60 and seconds < 60 and nanos <= _NANOS_PER_DAY:
            return nanos
    raise ValueError(
        f"{text!r} is not a time of day; pass one such as '12:34:56.789', up to "
        "'24:00:00'"
    )


def _call_repr(name: str, fields: tuple[int, ...], required: int, nanos: int) -> str:
    """``name(...)`` as ``datetime`` writes its repr, trailing zero fields left out."""
    shown = list(fields)
    while len(shown) > required and shown[-1] == 0:
        shown.pop()
    args = ", ".join(str(field) for field in shown)
    if nanos:
        args += f", nanosecond={nanos}"
    return f"{name}({args})"


@total_ordering
class PlainDate:
    """A calendar date with no time of day or zone (SurrealDB 4.0 ``date``).

    ``PlainDate(2024, 2, 29)`` takes its fields as ``datetime.date`` does, but
    for any year SurrealDB holds, -262143 to 262142; :attr:`INFINITY` and
    :attr:`NEG_INFINITY` are the last and first of them. :meth:`to_date` and
    :meth:`from_date` convert to and from ``datetime.date``, and a
    ``datetime.date`` is sent as a SurrealDB date too.
    """

    __slots__ = ("_days",)

    INFINITY: ClassVar[PlainDate]
    NEG_INFINITY: ClassVar[PlainDate]

    def __init__(self, year: int, month: int, day: int) -> None:
        self._days = _days(year, month, day)

    @classmethod
    def from_days(cls, days: int) -> PlainDate:
        """The date *days* after 1970-01-01, the count tag 100 carries."""
        instance = object.__new__(cls)
        instance._days = _within("days", days, _MIN_DAYS, _MAX_DAYS)
        return instance

    @classmethod
    def parse(cls, text: str) -> PlainDate:
        """A date as SurrealDB prints one: ``2024-02-29``, ``infinity`` or ``-infinity``.

        A year outside 0 to 9999 takes a sign, as ``+10000-01-01`` does.

        :raises ValueError: if *text* is not such a date.
        """
        return cls.from_days(_parse_date(text))

    @classmethod
    def from_date(cls, value: date) -> PlainDate:
        """The calendar date of *value*."""
        return cls(value.year, value.month, value.day)

    @property
    def days(self) -> int:
        """Days since 1970-01-01, negative before it."""
        return self._days

    @property
    def year(self) -> int:
        return _civil_from_days(self._days)[0]

    @property
    def month(self) -> int:
        return _civil_from_days(self._days)[1]

    @property
    def day(self) -> int:
        return _civil_from_days(self._days)[2]

    @property
    def is_infinite(self) -> bool:
        """Whether this is :attr:`INFINITY` or :attr:`NEG_INFINITY`."""
        return self._days in (_MIN_DAYS, _MAX_DAYS)

    def to_date(self) -> date:
        """This date as a ``datetime.date``.

        :raises ValueError: for a date outside the years 1 to 9999 that
            ``datetime.date`` holds, which includes the infinities.
        """
        year, month, day = _civil_from_days(self._days)
        if not MINYEAR <= year <= MAXYEAR:
            raise ValueError(
                f"{self} is outside the years {MINYEAR} to {MAXYEAR} that "
                "datetime.date holds"
            )
        return date(year, month, day)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlainDate):
            return NotImplemented
        return self._days == other._days

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PlainDate):
            return NotImplemented
        return self._days < other._days

    def __hash__(self) -> int:
        return hash((PlainDate, self._days))

    def __repr__(self) -> str:
        if self._days == _MAX_DAYS:
            return "PlainDate.INFINITY"
        if self._days == _MIN_DAYS:
            return "PlainDate.NEG_INFINITY"
        return _call_repr("PlainDate", _civil_from_days(self._days), 3, 0)

    def __str__(self) -> str:
        if self._days == _MAX_DAYS:
            return "infinity"
        if self._days == _MIN_DAYS:
            return "-infinity"
        return _format_date(self._days)


PlainDate.INFINITY = PlainDate.from_days(_MAX_DAYS)
PlainDate.NEG_INFINITY = PlainDate.from_days(_MIN_DAYS)


@total_ordering
class PlainTime:
    """A time of day with no date or zone (SurrealDB 4.0 ``time``), to the nanosecond.

    It runs from 00:00:00 up to and including 24:00:00, as in PostgreSQL. The
    fields are those of ``datetime.time``, plus the sub-microsecond
    ``nanosecond`` (0 to 999) that :class:`PreciseDatetime` keeps.
    :meth:`to_time` and :meth:`from_time` convert to and from
    ``datetime.time``, and a naive ``datetime.time`` is sent as a SurrealDB
    time too.
    """

    __slots__ = ("_nanos",)

    def __init__(
        self,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        nanosecond: int = 0,
    ) -> None:
        nanos = (
            _within("hour", hour, 0, 24) * 3600
            + _within("minute", minute, 0, 59) * 60
            + _within("second", second, 0, 59)
        ) * _NANOS
        nanos += _within("microsecond", microsecond, 0, 999_999) * 1000
        nanos += _within("nanosecond", nanosecond, 0, 999)
        if nanos > _NANOS_PER_DAY:
            raise ValueError("a time of day runs up to 24:00:00, and no later")
        self._nanos = nanos

    @classmethod
    def from_nanoseconds(cls, nanoseconds: int) -> PlainTime:
        """The time *nanoseconds* after midnight, the count tag 189 carries."""
        instance = object.__new__(cls)
        instance._nanos = _within("nanoseconds", nanoseconds, 0, _NANOS_PER_DAY)
        return instance

    @classmethod
    def parse(cls, text: str) -> PlainTime:
        """A time as SurrealDB prints one, ``12:34:56.789``, up to ``24:00:00``.

        :raises ValueError: if *text* is not such a time.
        """
        return cls.from_nanoseconds(_parse_time(text))

    @classmethod
    def from_time(cls, value: time) -> PlainTime:
        """*value*, which must be naive: a SurrealDB time has no zone.

        :raises ValueError: if *value* has a ``tzinfo``.
        """
        if value.tzinfo is not None:
            raise ValueError(
                f"a SurrealDB time has no zone, but {value!r} has one; pass "
                "value.replace(tzinfo=None) for its wall-clock time"
            )
        return cls(value.hour, value.minute, value.second, value.microsecond)

    @property
    def nanoseconds(self) -> int:
        """Nanoseconds since midnight."""
        return self._nanos

    @property
    def hour(self) -> int:
        return self._nanos // (3600 * _NANOS)

    @property
    def minute(self) -> int:
        return self._nanos // (60 * _NANOS) % 60

    @property
    def second(self) -> int:
        return self._nanos // _NANOS % 60

    @property
    def microsecond(self) -> int:
        return self._nanos % _NANOS // 1000

    @property
    def nanosecond(self) -> int:
        """The nanoseconds past :attr:`microsecond`, 0 to 999."""
        return self._nanos % 1000

    def to_time(self) -> time:
        """This time as a ``datetime.time``, without the :attr:`nanosecond` it cannot hold.

        :raises ValueError: for 24:00:00, which ``datetime.time`` does not hold.
        """
        if self._nanos == _NANOS_PER_DAY:
            raise ValueError("datetime.time does not hold 24:00:00")
        return time(self.hour, self.minute, self.second, self.microsecond)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlainTime):
            return NotImplemented
        return self._nanos == other._nanos

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PlainTime):
            return NotImplemented
        return self._nanos < other._nanos

    def __hash__(self) -> int:
        return hash((PlainTime, self._nanos))

    def __repr__(self) -> str:
        fields = (self.hour, self.minute, self.second, self.microsecond)
        return _call_repr("PlainTime", fields, 2, self.nanosecond)

    def __str__(self) -> str:
        return _format_time(self._nanos)


@total_ordering
class Timestamp:
    """A date and time of day with no zone (SurrealDB 4.0 ``timestamp``).

    A wall-clock time, where a ``datetime`` SurrealDB stores is an instant in
    UTC. The fields are those of ``datetime``, plus the sub-microsecond
    ``nanosecond`` (0 to 999) that :class:`PreciseDatetime` keeps, for any year
    SurrealDB holds; :attr:`INFINITY` and :attr:`NEG_INFINITY` are the last and
    first instants. :meth:`to_datetime` and :meth:`from_datetime` convert to
    and from a naive ``datetime``. A ``datetime`` itself is still sent as a
    SurrealDB datetime.
    """

    __slots__ = ("_nanos", "_seconds")

    INFINITY: ClassVar[Timestamp]
    NEG_INFINITY: ClassVar[Timestamp]

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        nanosecond: int = 0,
    ) -> None:
        self._seconds = (
            _days(year, month, day) * _SECONDS_PER_DAY
            + _within("hour", hour, 0, 23) * 3600
            + _within("minute", minute, 0, 59) * 60
            + _within("second", second, 0, 59)
        )
        self._nanos = _within("microsecond", microsecond, 0, 999_999) * 1000
        self._nanos += _within("nanosecond", nanosecond, 0, 999)

    @classmethod
    def from_seconds_and_nanos(cls, seconds: int, nanoseconds: int) -> Timestamp:
        """The ``[seconds, nanoseconds]`` since 1970-01-01T00:00:00 that tag 190 carries."""
        instance = object.__new__(cls)
        instance._seconds = _within("seconds", seconds, _MIN_SECONDS, _MAX_SECONDS)
        instance._nanos = _within("nanoseconds", nanoseconds, 0, _NANOS - 1)
        return instance

    @classmethod
    def parse(cls, text: str) -> Timestamp:
        """A timestamp as SurrealDB prints one, ``2024-02-29T12:34:56.789``.

        ``infinity`` and ``-infinity`` are the last and first instants, and a
        year outside 0 to 9999 takes a sign, as in :meth:`PlainDate.parse`.

        :raises ValueError: if *text* is not such a timestamp.
        """
        word = text.strip()
        if word == "infinity":
            return cls.INFINITY
        if word == "-infinity":
            return cls.NEG_INFINITY
        match = _TIMESTAMP.fullmatch(word)
        if match is None or _TIME.fullmatch(match[2]) is None:
            raise ValueError(
                f"{text!r} is not a timestamp; pass one such as "
                "'2024-02-29T12:34:56.789' or 'infinity'"
            )
        nanos = _parse_time(match[2])
        if nanos == _NANOS_PER_DAY:
            raise ValueError(f"{text!r} is not a timestamp: its time is 24:00:00")
        seconds = _parse_date(match[1]) * _SECONDS_PER_DAY + nanos // _NANOS
        return cls.from_seconds_and_nanos(seconds, nanos % _NANOS)

    @classmethod
    def from_datetime(cls, value: datetime) -> Timestamp:
        """The wall-clock time of *value*, which must be naive: a timestamp has no zone.

        The nanoseconds a :class:`PreciseDatetime` keeps are kept.

        :raises ValueError: if *value* has a ``tzinfo``.
        """
        if value.tzinfo is not None:
            raise ValueError(
                f"a timestamp has no zone, but {value!r} has one; pass "
                "value.replace(tzinfo=None) for its wall-clock time"
            )
        nanosecond = value.nanosecond if isinstance(value, PreciseDatetime) else 0
        return cls(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            nanosecond,
        )

    @property
    def seconds_and_nanos(self) -> tuple[int, int]:
        """Seconds since 1970-01-01T00:00:00, and nanoseconds within the second."""
        return self._seconds, self._nanos

    @property
    def year(self) -> int:
        return _civil_from_days(self._seconds // _SECONDS_PER_DAY)[0]

    @property
    def month(self) -> int:
        return _civil_from_days(self._seconds // _SECONDS_PER_DAY)[1]

    @property
    def day(self) -> int:
        return _civil_from_days(self._seconds // _SECONDS_PER_DAY)[2]

    @property
    def hour(self) -> int:
        return self._seconds % _SECONDS_PER_DAY // 3600

    @property
    def minute(self) -> int:
        return self._seconds % 3600 // 60

    @property
    def second(self) -> int:
        return self._seconds % 60

    @property
    def microsecond(self) -> int:
        return self._nanos // 1000

    @property
    def nanosecond(self) -> int:
        """The nanoseconds past :attr:`microsecond`, 0 to 999."""
        return self._nanos % 1000

    @property
    def is_infinite(self) -> bool:
        """Whether this is :attr:`INFINITY` or :attr:`NEG_INFINITY`."""
        return (self._seconds, self._nanos) in (
            (_MAX_SECONDS, _NANOS - 1),
            (_MIN_SECONDS, 0),
        )

    def to_datetime(self) -> PreciseDatetime:
        """This timestamp as a naive ``datetime``, its nanoseconds kept.

        :raises ValueError: for a year outside the 1 to 9999 that ``datetime``
            holds, which includes the infinities.
        """
        if not MINYEAR <= self.year <= MAXYEAR:
            raise ValueError(
                f"{self} is outside the years {MINYEAR} to {MAXYEAR} that "
                "datetime holds"
            )
        return PreciseDatetime(
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            self.second,
            self.microsecond,
            nanosecond=self.nanosecond,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return (self._seconds, self._nanos) == (other._seconds, other._nanos)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return (self._seconds, self._nanos) < (other._seconds, other._nanos)

    def __hash__(self) -> int:
        return hash((Timestamp, self._seconds, self._nanos))

    def __repr__(self) -> str:
        if self == Timestamp.INFINITY:
            return "Timestamp.INFINITY"
        if self == Timestamp.NEG_INFINITY:
            return "Timestamp.NEG_INFINITY"
        fields = (
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            self.second,
            self.microsecond,
        )
        return _call_repr("Timestamp", fields, 5, self.nanosecond)

    def __str__(self) -> str:
        if self == Timestamp.INFINITY:
            return "infinity"
        if self == Timestamp.NEG_INFINITY:
            return "-infinity"
        days, seconds = divmod(self._seconds, _SECONDS_PER_DAY)
        return f"{_format_date(days)}T{_format_time(seconds * _NANOS + self._nanos)}"


Timestamp.INFINITY = Timestamp.from_seconds_and_nanos(_MAX_SECONDS, _NANOS - 1)
Timestamp.NEG_INFINITY = Timestamp.from_seconds_and_nanos(_MIN_SECONDS, 0)


class Interval:
    """A calendar interval, as PostgreSQL holds one (SurrealDB 4.0 ``interval``).

    It keeps months, days and microseconds apart, each signed on its own,
    since neither a month nor a day has a fixed length on a calendar: years
    fold into months, weeks into days, and hours, minutes and seconds into
    microseconds. ``Interval(14, 3, 14_706_500_000)`` is P1Y2M3DT4H5M6.5S.

    Equality is the server's, which compares intervals normalised, a month as
    30 days and a day as 24 hours: ``Interval(months=1) == Interval(days=30)``
    holds, as it does in SurrealDB, though each keeps its parts as written.
    Compare ``(months, days, microseconds)`` to tell such intervals apart.
    """

    __slots__ = ("_days", "_microseconds", "_months")

    def __init__(self, months: int = 0, days: int = 0, microseconds: int = 0) -> None:
        self._months = _within("months", months, _I32_MIN, _I32_MAX)
        self._days = _within("days", days, _I32_MIN, _I32_MAX)
        self._microseconds = _within("microseconds", microseconds, _I64_MIN, _I64_MAX)

    @property
    def months(self) -> int:
        return self._months

    @property
    def days(self) -> int:
        return self._days

    @property
    def microseconds(self) -> int:
        return self._microseconds

    def _normalised(self) -> int:
        return (
            self._months * _MICROS_PER_MONTH
            + self._days * _MICROS_PER_DAY
            + self._microseconds
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Interval):
            return NotImplemented
        return self._normalised() == other._normalised()

    def __hash__(self) -> int:
        return hash((Interval, self._normalised()))

    def __repr__(self) -> str:
        parts = [
            f"{name}={value}"
            for name, value in (
                ("months", self._months),
                ("days", self._days),
                ("microseconds", self._microseconds),
            )
            if value
        ]
        return f"Interval({', '.join(parts)})"

    def __str__(self) -> str:
        """The ISO 8601 text SurrealDB prints, such as ``P1Y2M3DT4H5M6.5S``."""
        sign = -1 if self._months < 0 else 1
        years, months = divmod(abs(self._months), 12)
        text = "P"
        if years:
            text += f"{sign * years}Y"
        if months:
            text += f"{sign * months}M"
        if self._days:
            text += f"{self._days}D"
        if self._microseconds:
            mark = "-" if self._microseconds < 0 else ""
            hours, rest = divmod(abs(self._microseconds), 3_600_000_000)
            minutes, rest = divmod(rest, 60_000_000)
            seconds, fraction = divmod(rest, 1_000_000)
            text += "T"
            if hours:
                text += f"{mark}{hours}H"
            if minutes:
                text += f"{mark}{minutes}M"
            if seconds or fraction:
                text += f"{mark}{seconds}"
                if fraction:
                    text += f".{fraction:06d}".rstrip("0")
                text += "S"
        return "PT0S" if text == "P" else text
