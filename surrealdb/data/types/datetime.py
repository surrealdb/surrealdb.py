import pytz

from dataclasses import dataclass
from datetime import datetime
from math import floor
from typing import Tuple


@dataclass
class DateTimeCompact:
    timestamp: int = 0  # nanoseconds

    @staticmethod
    def parse(seconds: int, nanoseconds: int):
        return DateTimeCompact(nanoseconds + (seconds * pow(10, 9)))

    def get_seconds_and_nano(self) -> Tuple[int, int]:
        sec = floor(self.timestamp / pow(10, 9))
        nsec = self.timestamp - (sec * pow(10, 9))

        return sec, nsec

    def get_date_time(self, fmt: str = "%Y-%m-%dT%H:%M:%S.%fZ"):
        return datetime.fromtimestamp(self.timestamp / pow(10, 9), pytz.UTC).strftime(
            fmt
        )
