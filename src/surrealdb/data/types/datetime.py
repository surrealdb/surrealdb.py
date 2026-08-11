import json
from datetime import datetime, timedelta, timezone
from typing import Any


class Datetime:
    def __init__(self, dt: str):
        self.dt = dt

    def __str__(self) -> str:
        """
        Renders the datetime as a valid SurrealQL datetime literal, e.g.
        ``d"2025-02-03T12:30:45.123456Z"``. The ISO string is JSON-encoded to
        get proper double-quote/backslash escaping.

        Returns:
            The SurrealQL string representation of the datetime.
        """
        return f"d{json.dumps(self.dt)}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.dt!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Datetime):
            return self.dt == other.dt
        return False

    def __hash__(self) -> int:
        return hash(self.dt)


class PreciseDatetime(datetime):
    """A :class:`datetime` that remembers the nanoseconds it cannot store.

    ``datetime`` resolves to microseconds, so decoding a SurrealDB timestamp
    dropped its last three digits. That was not only a display problem: writing
    the value back stored the truncated form, so an ordinary read-modify-write
    destroyed precision *in the database*.

    Instances are ``datetime`` in every respect - ``isinstance`` holds, they
    compare and sort against plain ``datetime`` values, and pickle and copy
    round-trip - with the leftover nanoseconds kept in :attr:`nanosecond` so a
    value read from SurrealDB can be written back unchanged.

    One limit is inherent: arithmetic goes through ``datetime``'s own
    constructors, which know nothing of the extra field, so a computed result
    carries ``nanosecond == 0``::

        stored.nanosecond                    # 789
        (stored + timedelta(days=1)).nanosecond  # 0

    Precision therefore survives storage and retrieval, but not computation -
    which is strictly better than today, where it survives neither.
    """

    __slots__ = ("nanosecond",)

    # Declared for readers and type checkers; `__new__` sets it, because
    # `datetime` is immutable and has no `__init__` to assign in.
    nanosecond: int  # pyright: ignore[reportUninitializedInstanceVariable]

    def __new__(
        cls, *args: Any, nanosecond: int = 0, **kwargs: Any
    ) -> "PreciseDatetime":
        if not 0 <= nanosecond <= 999:
            raise ValueError(
                f"nanosecond must be the sub-microsecond remainder (0-999), got {nanosecond}"
            )
        instance = super().__new__(cls, *args, **kwargs)
        object.__setattr__(instance, "nanosecond", nanosecond)
        return instance

    @classmethod
    def from_seconds_and_nanos(
        cls, seconds: int, nanoseconds: int
    ) -> "PreciseDatetime":
        """Build one from the ``[seconds, nanoseconds]`` pair SurrealDB sends."""
        microseconds, remainder = divmod(nanoseconds, 1000)
        moment = datetime.fromtimestamp(seconds, timezone.utc) + timedelta(
            microseconds=microseconds
        )
        return cls(
            moment.year,
            moment.month,
            moment.day,
            moment.hour,
            moment.minute,
            moment.second,
            moment.microsecond,
            tzinfo=moment.tzinfo,
            nanosecond=remainder,
        )

    def isoformat_with_nanoseconds(self) -> str:
        """Render with all nine fractional digits, as SurrealDB expects."""
        return (
            self.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.")
            + f"{self.microsecond:06d}{self.nanosecond:03d}Z"
        )
