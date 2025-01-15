from dataclasses import dataclass
from typing import Tuple

from math import floor


@dataclass
class Duration:
    elapsed: int = 0  # nanoseconds

    @staticmethod
    def parse(seconds: int, nanoseconds: int):
        return Duration(nanoseconds + (seconds * pow(10, 9)))

    def get_seconds_and_nano(self) -> Tuple[int, int]:
        sec = floor(self.elapsed / pow(10, 9))
        nsec = self.elapsed - (sec * pow(10, 9))

        return sec, nsec
