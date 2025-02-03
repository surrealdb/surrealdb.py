from dataclasses import dataclass
from math import floor
from typing import Tuple
from datetime import datetime
import pytz


class DatetimeWrapper:

    def __init__(self, dt: datetime):
        self.dt = dt

    @staticmethod
    def now() -> "DatetimeWrapper":
        return DatetimeWrapper(datetime.now())


class IsoDateTimeWrapper:

    def __init__(self, dt: str):
        self.dt = dt

# @dataclass
# class DateTimeCompact:
#     """
#     Represents a compact datetime object stored as a single integer value in nanoseconds.
#
#     Attributes:
#         timestamp: The number of nanoseconds since the epoch (1970-01-01T00:00:00Z).
#     """
#     timestamp: int = 0  # nanoseconds
#
#     @staticmethod
#     def from_datetime(dt: datetime) -> 'DateTimeCompact':
#         pass
#
#     @staticmethod
#     def parse(seconds: int, nanoseconds: int) -> "DateTimeCompact":
#         """
#         Creates a DateTimeCompact object from seconds and nanoseconds.
#
#         Args:
#             seconds: The number of seconds since the epoch.
#             nanoseconds: The additional nanoseconds beyond the seconds.
#
#         Returns:
#             A DateTimeCompact object representing the specified time.
#         """
#         return DateTimeCompact(nanoseconds + (seconds * pow(10, 9)))
#
#     @staticmethod
#     def from_iso_string(iso_str: str) -> "DateTimeCompact":
#         """
#         Creates a DateTimeCompact object from an ISO 8601 datetime string.
#
#         Args:
#             iso_str: A string representation of a datetime in ISO 8601 format.
#
#         Returns:
#             A DateTimeCompact object.
#         """
#         dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))  # Handle UTC 'Z' case
#         timestamp = int(dt.timestamp() * pow(10, 9))  # Convert to nanoseconds
#         return DateTimeCompact(timestamp)
#
#     def get_seconds_and_nano(self) -> Tuple[int, int]:
#         """
#         Extracts the seconds and nanoseconds components from the timestamp.
#
#         Returns:
#             A tuple containing:
#                 - The number of seconds since the epoch.
#                 - The remaining nanoseconds after the seconds.
#         """
#         sec = floor(self.timestamp / pow(10, 9))
#         nsec = self.timestamp - (sec * pow(10, 9))
#         return sec, nsec
#
#     def get_date_time(self, fmt: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> str:
#         """
#         Converts the timestamp into a formatted datetime string.
#
#         Args:
#             fmt: The format string for the datetime. Defaults to ISO 8601 format.
#
#         Returns:
#             A string representation of the datetime in the specified format.
#         """
#         return datetime.fromtimestamp(self.timestamp / pow(10, 9), pytz.UTC).strftime(fmt)
#
#     def __eq__(self, other: object) -> bool:
#         """
#         Compares two DateTimeCompact objects for equality.
#
#         Args:
#             other: The object to compare against.
#
#         Returns:
#             True if the objects have the same timestamp, False otherwise.
#         """
#         if isinstance(other, DateTimeCompact):
#             return self.timestamp == other.timestamp
#         return False
