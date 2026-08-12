import re
from dataclasses import dataclass
from math import floor

from surrealdb.errors import InvalidDurationError

UNITS = {
    "ns": 1,
    "µs": int(1e3),  # Microsecond (µ symbol)
    "us": int(1e3),  # Microsecond (us)
    "ms": int(1e6),
    "s": int(1e9),
    "m": int(60 * 1e9),
    "h": int(3600 * 1e9),
    "d": int(86400 * 1e9),
    "w": int(604800 * 1e9),
    "y": int(365 * 86400 * 1e9),  # Year (365 days)
}


_UNIT_PATTERN = r"ns|µs|us|ms|[smhdwy]"

# One `<digits><unit>` part, used to add the parts up.
_PART_RE = re.compile(rf"(\d+)({_UNIT_PATTERN})")

# The whole string must be nothing but those parts. Anchored on purpose:
# `findall` alone matched parts *anywhere* and ignored everything around them,
# so a string the server rejects outright silently became a different duration -
# "1.5s" parsed as the "5s" inside it, "-1s" lost its sign and came out
# positive, and "1e3s" became three seconds. Each produced a wrong value rather
# than an error, which is the worst of the three possible outcomes.
_DURATION_RE = re.compile(rf"^(?:\d+(?:{_UNIT_PATTERN}))+$")


@dataclass
class Duration:
    elapsed: int = 0  # nanoseconds

    @staticmethod
    def parse(value: str | int, nanoseconds: int = 0) -> "Duration":
        """Build a ``Duration`` from ``"1h30m"``-style text, or from seconds.

        Accepts one or more ``<digits><unit>`` parts and nothing else, matching
        what SurrealDB itself accepts for a duration literal. Fractional
        ("1.5s"), signed ("-1s") and exponent ("1e3s") forms are rejected here
        because the server rejects them too.

        :raises InvalidDurationError: if *value* is not a duration the server
            would accept.
        """
        if isinstance(value, int):
            if value < 0:
                raise InvalidDurationError(
                    f"Duration cannot be negative, got {value} seconds"
                )
            return Duration(nanoseconds + value * UNITS["s"])

        # Support compound durations: "1h30m", "2d3h15m", etc.
        text = value.lower()
        if not _DURATION_RE.match(text):
            raise InvalidDurationError(f"Invalid duration format: {value}")

        total_ns = nanoseconds
        for num_str, unit in _PART_RE.findall(text):
            total_ns += int(num_str) * UNITS[unit]

        return Duration(total_ns)

    def get_seconds_and_nano(self) -> tuple[int, int]:
        sec = floor(self.elapsed / UNITS["s"])
        nsec = self.elapsed - (sec * UNITS["s"])
        return sec, nsec

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Duration):
            return self.elapsed == other.elapsed
        return False

    def __hash__(self) -> int:
        return hash(self.elapsed)

    @property
    def nanoseconds(self) -> int:
        return self.elapsed

    @property
    def microseconds(self) -> int:
        return self.elapsed // UNITS["us"]

    @property
    def milliseconds(self) -> int:
        return self.elapsed // UNITS["ms"]

    @property
    def seconds(self) -> int:
        return self.elapsed // UNITS["s"]

    @property
    def minutes(self) -> int:
        return self.elapsed // UNITS["m"]

    @property
    def hours(self) -> int:
        return self.elapsed // UNITS["h"]

    @property
    def days(self) -> int:
        return self.elapsed // UNITS["d"]

    @property
    def weeks(self) -> int:
        return self.elapsed // UNITS["w"]

    @property
    def years(self) -> int:
        return self.elapsed // UNITS["y"]

    def to_string(self) -> str:
        result = ""
        remaining = self.elapsed
        for unit in ["y", "w", "d", "h", "m", "s", "ms", "us", "ns"]:
            amount, remaining = divmod(remaining, UNITS[unit])
            if amount > 0:
                result += f"{amount}{unit}"
        return result or "0ns"

    def __str__(self) -> str:
        """
        Renders the duration as valid SurrealQL compact-unit syntax, e.g.
        ``1h30m`` or ``500ms``. Equivalent to :meth:`to_string`.

        Returns:
            The SurrealQL string representation of the duration.
        """
        return self.to_string()

    def to_compact(self) -> list[int]:
        return [self.elapsed // UNITS["s"]]
