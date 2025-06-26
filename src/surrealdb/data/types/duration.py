from dataclasses import dataclass
from math import floor
from typing import Union

UNITS = {
    "ns": 1,
    "us": int(1e3),
    "ms": int(1e6),
    "s": int(1e9),
    "m": int(60 * 1e9),
    "h": int(3600 * 1e9),
    "d": int(86400 * 1e9),
    "w": int(604800 * 1e9),
}


@dataclass
class Duration:
    elapsed: int = 0  # nanoseconds

    @staticmethod
    def parse(value: Union[str, int], nanoseconds: int = 0) -> "Duration":
        if isinstance(value, int):
            return Duration(nanoseconds + value * UNITS["s"])
        elif isinstance(value, str):
            unit = value[-1]
            num = int(value[:-1])
            if unit in UNITS:
                return Duration(num * UNITS[unit])
            else:
                raise ValueError(f"Unknown duration unit: {unit}")
        else:
            raise TypeError("Duration must be initialized with an int or str")

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

    def to_string(self) -> str:
        for unit in reversed(["w", "d", "h", "m", "s", "ms", "us", "ns"]):
            value = self.elapsed // UNITS[unit]
            if value > 0:
                return f"{value}{unit}"
        return "0ns"

    def to_compact(self) -> list:
        return [self.elapsed // UNITS["s"]]
