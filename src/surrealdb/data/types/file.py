"""A reference to a file in a storage bucket."""

from __future__ import annotations

from typing import Any

# The characters SurrealQL's `f"bucket:/key"` literal syntax accepts. Taken from
# the parser's own refusal, which is the only documentation of it:
#
#   Parse error: Unexpected character ` `, file strings key's only allow alpha
#   numeric characters and `_`, `-`, `.`, and `/`
#
# There is no escape mechanism - not for spaces, not for unicode, not with
# backslashes - so a key outside this set simply cannot be written as a literal.
# It can still be *sent*, as a bound parameter, which is what this type is for.
_LITERAL_SAFE = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-./"
)


def file_type_error(argument: str, value: Any) -> TypeError:
    return TypeError(
        f"File {argument} must be a str, not {type(value).__name__}: {value!r}"
    )


class File:
    """A ``bucket`` plus a ``key``, identifying a file the server stores.

    This is a *reference*, not contents: it holds no bytes and is not a Python
    file object. Read and write the contents through the ``file::*`` functions,
    or the ``files`` helper on a connection, which bind it for you::

        f = File("images", "/photos/avatar.png")
        db.files.put(f, png_bytes)
        png_bytes = db.files.get(f)

    ``key`` is normalised to start with ``/``, matching the JavaScript SDK, so
    ``File("b", "a.txt")`` and ``File("b", "/a.txt")`` are the same file. Without
    that the two would encode differently and address different objects.
    """

    __slots__ = ("bucket", "key")

    def __init__(self, bucket: str, key: str) -> None:
        if not isinstance(bucket, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise file_type_error("bucket", bucket)
        if not isinstance(key, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise file_type_error("key", key)
        self.bucket: str = bucket
        self.key: str = key if key.startswith("/") else f"/{key}"

    @classmethod
    def _unchecked(cls, bucket: str, key: str) -> File:
        """Build without validating - for the decoder, where the server is the source."""
        instance = object.__new__(cls)
        instance.bucket = bucket
        instance.key = key if key.startswith("/") else f"/{key}"
        return instance

    def is_literal_safe(self) -> bool:
        """Whether ``str(self)`` is a literal SurrealQL can actually parse.

        False for a key or bucket containing anything outside
        ``[A-Za-z0-9_-./]`` - a space, an accent, an emoji, a quote. Those files
        are perfectly usable; they just have to be bound as parameters rather
        than written into a query, because the literal syntax has no way to
        express them.
        """
        return _LITERAL_SAFE.issuperset(self.bucket) and _LITERAL_SAFE.issuperset(
            self.key
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, File):
            return NotImplemented
        return self.bucket == other.bucket and self.key == other.key

    def __hash__(self) -> int:
        return hash((File, self.bucket, self.key))

    def __repr__(self) -> str:
        return f"File(bucket={self.bucket!r}, key={self.key!r})"

    def __str__(self) -> str:
        """The SurrealQL literal form, when there is one.

        Display only. For a key the literal syntax cannot express this is not
        valid SurrealQL, and there is no escaping that would make it so - so
        never build a query by interpolating this. Bind the ``File`` instead;
        that carries any key, and the ``files`` helpers do it for you.
        """
        return f'f"{self.bucket}:{self.key}"'
