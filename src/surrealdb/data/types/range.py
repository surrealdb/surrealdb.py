"""
Defines classes for representing bounded ranges, including inclusive and exclusive bounds.
"""

from dataclasses import dataclass
from typing import Any


class Bound:
    """
    Represents a generic boundary for a range. This is an abstract base class
    that can be extended by specific bound types, such as inclusive or exclusive bounds.
    """

    def __init__(self) -> None:
        """
        Initializes a generic bound.
        """
        pass

    def __eq__(self, other: object) -> bool:
        """
        Compares two Bound objects for equality. Must be overridden by subclasses.

        Args:
            other: The object to compare against.

        Returns:
            True if the objects are equal, False otherwise.
        """
        return isinstance(other, Bound)


@dataclass
class BoundIncluded(Bound):
    """
    Represents an inclusive bound of a range.

    Attributes:
        value: The value of the inclusive bound.
    """

    value: Any

    def __init__(self, value: Any) -> None:
        """
        Initializes an inclusive bound with a specific value.

        Args:
            value: The value of the bound.
        """
        super().__init__()
        self.value = value

    def __eq__(self, other: object) -> bool:
        """
        Compares two BoundIncluded objects for equality.

        Args:
            other: The object to compare against.

        Returns:
            True if the objects have the same value, False otherwise.
        """
        if isinstance(other, BoundIncluded):
            return self.value == other.value
        return False


@dataclass
class BoundExcluded(Bound):
    """
    Represents an exclusive bound of a range.

    Attributes:
        value: The value of the exclusive bound.
    """

    value: Any

    def __init__(self, value: Any) -> None:
        """
        Initializes an exclusive bound with a specific value.

        Args:
            value: The value of the bound.
        """
        super().__init__()
        self.value = value

    def __eq__(self, other: object) -> bool:
        """
        Compares two BoundExcluded objects for equality.

        Args:
            other: The object to compare against.

        Returns:
            True if the objects have the same value, False otherwise.
        """
        if isinstance(other, BoundExcluded):
            return self.value == other.value
        return False


@dataclass
class Range:
    """
    Represents a range with a beginning and an end bound.

    Attributes:
        begin: The starting bound of the range (inclusive or exclusive).
        end: The ending bound of the range (inclusive or exclusive).
    """

    begin: Bound
    end: Bound

    def __eq__(self, other: object) -> bool:
        """
        Compares two Range objects for equality.

        Args:
            other: The object to compare against.

        Returns:
            True if the beginning and ending bounds are equal, False otherwise.
        """
        if isinstance(other, Range):
            return self.begin == other.begin and self.end == other.end
        return False
