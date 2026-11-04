"""The text form of a record id, ``table:key``, as tag 8 may carry it.

SurrealDB accepts a record id written as SurrealQL text under tag 8 but never
sends one, so this reads only the forms a record id key takes: an identifier,
a number, a ``⟨…⟩`` or backtick-quoted name, a ``u'…'`` uuid, and array and
object literals of plain values.
"""

import re
import uuid
from decimal import Decimal
from typing import Any

from surrealdb.data.types.null import Null

_I64_MAX = 2**63 - 1
_IDENT = re.compile(r"[A-Za-z0-9_]+")
_NUMBER = re.compile(r"-?(?:\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+|\d+)(f|dec)?")
_ESCAPES = {
    '"': '"',
    "'": "'",
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "0": "\0",
}
_CLOSERS = {"⟨": "⟩", "`": "`"}


class _Text:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def fail(self, what: str) -> ValueError:
        return ValueError(f"record id {self.text!r}: {what} at offset {self.pos}")

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def skip_space(self) -> None:
        while self.peek().isspace():
            self.pos += 1

    def expect(self, char: str) -> None:
        self.skip_space()
        if self.peek() != char:
            raise self.fail(f"expected {char!r}")
        self.pos += 1

    def name(self) -> str:
        """An identifier, or a ``⟨…⟩`` / backtick-quoted name."""
        closer = _CLOSERS.get(self.peek())
        if closer is None:
            match = _IDENT.match(self.text, self.pos)
            if match is None:
                raise self.fail("expected a name")
            self.pos = match.end()
            return match.group()
        self.pos += 1
        out = []
        while (char := self.peek()) != closer:
            if not char:
                raise self.fail(f"expected {closer!r}")
            if char == "\\":
                self.pos += 1
                char = self.peek()
            out.append(char)
            self.pos += 1
        self.pos += 1
        return "".join(out)

    def string(self) -> str:
        quote = self.peek()
        self.pos += 1
        out = []
        while (char := self.peek()) != quote:
            if not char:
                raise self.fail("an unterminated string")
            self.pos += 1
            out.append(self.escape() if char == "\\" else char)
        self.pos += 1
        return "".join(out)

    def escape(self) -> str:
        char = self.peek()
        self.pos += 1
        if char in _ESCAPES:
            return _ESCAPES[char]
        if char != "u":
            raise self.fail(f"unknown escape \\{char}")
        if self.peek() == "{":
            end = self.text.find("}", self.pos)
            digits = self.text[self.pos + 1 : end] if end != -1 else ""
            self.pos = end + 1
        else:
            digits = self.text[self.pos : self.pos + 4]
            self.pos += 4
        try:
            code = int(digits, 16)
        except ValueError:
            raise self.fail(f"bad unicode escape \\u{digits}") from None
        if 0xD800 <= code <= 0xDFFF or code > 0x10FFFF:
            raise self.fail(f"\\u{digits} is not a unicode scalar value")
        return chr(code)

    def key(self) -> Any:
        """A record id key."""
        char = self.peek()
        if char in "[{":
            return self.value()
        if char in "uU" and self.text[self.pos + 1 : self.pos + 2] in ("'", '"'):
            return self.value()
        match = re.compile(r"-?\d+").fullmatch(self.text, self.pos)
        if match is not None:
            self.pos = match.end()
            number = int(match.group())
            return number if abs(number) <= _I64_MAX else match.group()
        return self.name()

    def value(self) -> Any:
        """A plain value inside an array or object key."""
        self.skip_space()
        char = self.peek()
        if char == "[":
            self.pos += 1
            items = []
            self.skip_space()
            while self.peek() != "]":
                items.append(self.value())
                self.skip_space()
                if self.peek() == ",":
                    self.pos += 1
                    self.skip_space()
                elif self.peek() != "]":
                    raise self.fail("expected ',' or ']'")
            self.pos += 1
            return items
        if char == "{":
            self.pos += 1
            fields: dict[str, Any] = {}
            self.skip_space()
            while self.peek() != "}":
                field = self.string() if self.peek() in "'\"" else self.name()
                self.expect(":")
                fields[field] = self.value()
                self.skip_space()
                if self.peek() == ",":
                    self.pos += 1
                    self.skip_space()
                elif self.peek() != "}":
                    raise self.fail("expected ',' or '}'")
            self.pos += 1
            return fields
        if char in "'\"":
            return self.string()
        if char in "uU" and self.text[self.pos + 1 : self.pos + 2] in ("'", '"'):
            self.pos += 1
            try:
                return uuid.UUID(self.string())
            except ValueError:
                raise self.fail("a bad uuid") from None
        match = _NUMBER.match(self.text, self.pos)
        if match is not None:
            self.pos = match.end()
            literal = match.group()
            if match.group(1) == "dec":
                return Decimal(literal[:-3])
            if match.group(1) == "f" or any(c in literal for c in ".eE"):
                return float(literal.rstrip("f"))
            return int(literal)
        word = _IDENT.match(self.text, self.pos)
        constants = {
            "true": True,
            "false": False,
            "null": Null,
            "NULL": Null,
            "NONE": None,
        }
        if word is not None and word.group() in constants:
            self.pos = word.end()
            return constants[word.group()]
        raise self.fail("expected a value")


def parse_record_id(text: str) -> tuple[str, Any]:
    """The table and key of a record id written as ``table:key``.

    :raises ValueError: if *text* is not a record id.
    """
    reader = _Text(text)
    table = reader.name()
    reader.expect(":")
    key = reader.key()
    if reader.pos != len(text):
        raise reader.fail("unexpected text")
    return table, key
