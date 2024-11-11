from dataclasses import dataclass
from math import floor
from typing import Tuple


@dataclass
class Duration:
    elapsed: int = 0  # nanoseconds

    @staticmethod
    def parse(seconds: int, nanoseconds: int):
        return Duration(nanoseconds + (seconds * pow(10, 9)))

    def getSecondsAndNano(self) -> Tuple[int, int]:
        sec = floor(self.elapsed / pow(10, 9))
        nsec = self.elapsed - (sec * pow(10, 9))

        return sec, nsec
