"""
Defines classes for representing bounded ranges, including inclusive and exclusive bounds.
"""

from dataclasses import dataclass
from typing import Any

from surrealdb.data.types.null import Null


class Bound:
    """
    Represents a generic boundary for a range. This is an abstract base class
    that can be extended by specific bound types, such as inclusive or exclusive bounds.
    """

    def __init__(self) -> None:
        """
        Initializes a generic bound.
        """

    def __eq__(self, other: object) -> bool:
        """
        Compares two Bound objects for equality. Must be overridden by subclasses.

        Args:
            other: The object to compare against.

        Returns:
            True if the objects are equal, False otherwise.
        """
        return isinstance(other, Bound)

    def __hash__(self) -> int:
        """
        Returns a hash of the bound. All plain (unbounded) ``Bound``
        instances compare equal, so they share a constant hash.
        """
        return hash(type(self).__name__)


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

    def __hash__(self) -> int:
        return hash(("BoundIncluded", self.value))


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

    def __hash__(self) -> int:
        return hash(("BoundExcluded", self.value))


@dataclass
class Range:
    """
    Represents a range with a beginning and an end bound.

    Attributes:
        begin: The starting bound of the range (inclusive or exclusive), or
            ``None`` / ``Null`` for an open start.
        end: The ending bound of the range, or ``None`` / ``Null`` for an
            open end.
    """

    begin: Any
    end: Any

    def __post_init__(self) -> None:
        """Normalise an open bound spelled ``None`` to ``Null``.

        An open bound is a null on the wire. ``None`` is the natural way to
        spell "no bound" in Python, but it encodes as SurrealDB's NONE, which
        the server refuses inside a range - so ``Range(BoundIncluded(1), None)``
        was rejected with a parse error while the identical range *read back
        from the server* (whose open bound decodes to ``Null``) sent fine. Same
        value, two spellings, one of them unusable.

        Normalising here rather than in the encoder also keeps equality honest:
        a hand-built open range and one read back compare equal.
        """
        if self.begin is None:
            self.begin = Null
        if self.end is None:
            self.end = Null

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

    def __hash__(self) -> int:
        return hash((self.begin, self.end))

    def __str__(self) -> str:
        """
        Renders the range as valid SurrealQL range syntax, e.g. ``1..10``,
        ``1..=10``, ``1>..10`` or ``1>..=10`` depending on the bound types.

        Returns:
            The SurrealQL string representation of the range.
        """
        begin_value = (
            self.begin.value
            if isinstance(self.begin, (BoundIncluded, BoundExcluded))
            else ""
        )
        end_value = (
            self.end.value
            if isinstance(self.end, (BoundIncluded, BoundExcluded))
            else ""
        )
        marker = ">" if isinstance(self.begin, BoundExcluded) else ""
        suffix = "=" if isinstance(self.end, BoundIncluded) else ""
        return f"{begin_value}{marker}..{suffix}{end_value}"
