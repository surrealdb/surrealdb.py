"""SurrealDB 4.0's ``regex``: a pattern, in the syntax SurrealQL regexes use."""

from __future__ import annotations


class Regex:
    """A SurrealQL regex, held as the text of its pattern.

    SurrealQL regexes use the syntax of Rust's ``regex`` crate, not Python's
    ``re``, so the pattern is kept as text rather than compiled. Most patterns
    mean the same in both, but the server refuses the lookarounds and
    backreferences ``re`` has; ``re.compile(r.pattern)`` compiles one with
    Python's engine. A compiled ``re.Pattern`` is not sent for the same
    reason: wrap its ``pattern`` in a ``Regex`` once it means the same in Rust.

    Over ``cbor.2`` (SurrealDB 4.0) it is tag 193. Plain ``cbor`` has no form
    for a regex, so one cannot be sent to a server before 4.0.
    """

    __slots__ = ("_pattern",)

    def __init__(self, pattern: str) -> None:
        if not isinstance(pattern, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(
                f"a Regex pattern must be a str, not {type(pattern).__name__}: "
                f"{pattern!r}"
            )
        self._pattern = pattern

    @property
    def pattern(self) -> str:
        return self._pattern

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Regex):
            return NotImplemented
        return self._pattern == other._pattern

    def __hash__(self) -> int:
        return hash((Regex, self._pattern))

    def __repr__(self) -> str:
        return f"Regex({self._pattern!r})"

    def __str__(self) -> str:
        return self._pattern
