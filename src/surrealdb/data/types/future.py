"""
Defines a simple Future class to hold a value of any type.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Future:
    """
    Represents a placeholder for a value that may be unset or resolved in the future.

    Attributes:
        value: The value held by the Future object. This can be of any type.
    """

    value: Any

    def __eq__(self, other: object) -> bool:
        """
        Compares two Future objects for equality.

        Args:
            other: The object to compare against.

        Returns:
            True if the values held by both Future objects are equal, False otherwise.
        """
        if isinstance(other, Future):
            return self.value == other.value
        return False
