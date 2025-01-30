"""
Defines a compact representation of datetime using nanoseconds.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Tuple
import pytz  # type: ignore
from math import floor


@dataclass
class DateTimeCompact:
    """
    Represents a compact datetime object stored as a single integer value in nanoseconds.

    Attributes:
        timestamp: The number of nanoseconds since the epoch (1970-01-01T00:00:00Z).
    """
    timestamp: int = 0  # nanoseconds

    @staticmethod
    def parse(seconds: int, nanoseconds: int) -> "DateTimeCompact":
        """
        Creates a DateTimeCompact object from seconds and nanoseconds.

        Args:
            seconds: The number of seconds since the epoch.
            nanoseconds: The additional nanoseconds beyond the seconds.

        Returns:
            A DateTimeCompact object representing the specified time.
        """
        return DateTimeCompact(nanoseconds + (seconds * pow(10, 9)))

    def get_seconds_and_nano(self) -> Tuple[int, int]:
        """
        Extracts the seconds and nanoseconds components from the timestamp.

        Returns:
            A tuple containing:
                - The number of seconds since the epoch.
                - The remaining nanoseconds after the seconds.
        """
        sec = floor(self.timestamp / pow(10, 9))
        nsec = self.timestamp - (sec * pow(10, 9))
        return sec, nsec

    def get_date_time(self, fmt: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> str:
        """
        Converts the timestamp into a formatted datetime string.

        Args:
            fmt: The format string for the datetime. Defaults to ISO 8601 format.

        Returns:
            A string representation of the datetime in the specified format.
        """
        return datetime.fromtimestamp(self.timestamp / pow(10, 9), pytz.UTC).strftime(fmt)

    def __eq__(self, other: object) -> bool:
        """
        Compares two DateTimeCompact objects for equality.

        Args:
            other: The object to compare against.

        Returns:
            True if the objects have the same timestamp, False otherwise.
        """
        if isinstance(other, DateTimeCompact):
            return self.timestamp == other.timestamp
        return False
