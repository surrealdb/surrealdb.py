import re
from dataclasses import dataclass
from math import floor
from typing import Union

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


@dataclass
class Duration:
    elapsed: int = 0  # nanoseconds

    @staticmethod
    def parse(value: Union[str, int], nanoseconds: int = 0) -> "Duration":
        if isinstance(value, int):
            return Duration(nanoseconds + value * UNITS["s"])
        else:
            # Support compound durations: "1h30m", "2d3h15m", etc.
            pattern = r"(\d+)(ns|µs|us|ms|[smhdwy])"
            matches = re.findall(pattern, value.lower())

            if not matches:
                raise ValueError(f"Invalid duration format: {value}")

            total_ns = nanoseconds
            for num_str, unit in matches:
                num = int(num_str)
                if unit not in UNITS:
                    # this will never happen because the regex only matches valid units
                    raise ValueError(f"Unknown duration unit: {unit}")
                total_ns += num * UNITS[unit]

            return Duration(total_ns)

    def get_seconds_and_nano(self) -> tuple[int, int]:
        sec = floor(self.elapsed / UNITS["s"])
        nsec = self.elapsed - (sec * UNITS["s"])
        return sec, nsec

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Duration):
            return self.elapsed == other.elapsed
        return False

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
        for unit in ["y", "w", "d", "h", "m", "s", "ms", "us", "ns"]:
            value = self.elapsed // UNITS[unit]
            if value > 0:
                return f"{value}{unit}"
        return "0ns"

    def to_compact(self) -> list[int]:
        return [self.elapsed // UNITS["s"]]
