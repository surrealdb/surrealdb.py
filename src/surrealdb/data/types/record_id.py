"""
Defines the data type for the record ID.
"""

from __future__ import annotations

import uuid as uuid_module
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Union, cast

from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo

from surrealdb.data.types.range import Range
from surrealdb.data.types.set import SurrealSet
from surrealdb.data.types.table import Table, table_name_type_error
from surrealdb.errors import InvalidRecordIdError

if TYPE_CHECKING:
    from pydantic import GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue

RecordIdType = Union[str, "RecordID", Table]

#: What SurrealDB accepts as a record id. Exported so callers have a name to
#: annotate or cast against - ``RecordID.id`` is deliberately wider (see the
#: attribute's docs), so this is the type to use for a value you construct.
RecordIdValue = Union[
    str, int, uuid_module.UUID, "list[Any]", "tuple[Any, ...]", "dict[str, Any]", Range
]

# The runtime half of `RecordIdValue`. Derived by probing every candidate value
# against live 2.0.5 and 3.2.3 servers rather than from the documentation: these
# are exactly the id types a server accepts and hands back, plus `Range`, which
# is never a *stored* id but is how this SDK spells the `person:1..=3` target.
#
# `tuple` earns its place empirically. `RecordID(t, ("a", 1))` round-trips on
# both servers - cbor2 encodes a tuple as a CBOR array - so leaving it out would
# have silently broken anyone using composite keys.
_ID_TYPES: tuple[type, ...] = (str, int, uuid_module.UUID, list, tuple, dict, Range)

# Two allowed types have subclasses the server refuses, and `isinstance` would
# wave both through: `bool` is a subclass of `int`, and `SurrealSet` is a
# subclass of `list`. They are excluded before the allowlist is consulted.
_ID_TYPE_IMPOSTORS: tuple[type, ...] = (bool, SurrealSet)

_ID_TYPE_NAMES = "str, int, uuid.UUID, list, tuple, dict or Range"


def _id_type_error(identifier: Any) -> TypeError:
    """Build the message for a record id of an unusable type.

    Three types get a hint of their own, because the generic "use one of these
    instead" reads as wrong to the caller who hit them: someone passing a bool
    knows perfectly well that a bool is an int, someone passing ``None`` has not
    made a typo at all, and someone passing a float wants to know which way to
    round.
    """
    got = type(identifier).__name__
    if isinstance(identifier, bool):
        hint = (
            " Python's bool is a subclass of int, but SurrealDB has no boolean"
            " record id - pass 1 or 0 if you meant the numeric id."
        )
    elif identifier is None:
        hint = (
            " SurrealDB has no NONE record id. To have the server generate one,"
            " pass the table instead - e.g. db.create(Table('person'), data)."
        )
    elif isinstance(identifier, float):
        hint = (
            f" SurrealDB has no float record id - use an int, or"
            f" {str(identifier)!r} for a string id."
        )
    elif isinstance(identifier, SurrealSet):
        hint = (
            " A SurrealSet is a set on the wire, which is not a record id -"
            " pass list(...) if you meant an array id."
        )
    else:
        hint = ""
    return TypeError(
        f"RecordID() id must be one of {_ID_TYPE_NAMES}, got {got}:"
        f" {identifier!r}.{hint}"
    )


def escape_identifier(identifier: str) -> str:
    """Escape a string identifier for use inside SurrealQL.

    Wraps the identifier in ``⟨...⟩`` (with any ``⟩`` inside replaced by
    ``\\⟩``) when it contains characters outside the safe-identifier
    subset - i.e. anything other than alphanumerics or underscore, OR
    a name that is all-digit / all-symbol (no alphabetic char) and would
    otherwise be ambiguous with a numeric id. Plain identifiers are
    returned unchanged.

    Used by :meth:`RecordID.__str__` for record-id rendering and by the
    v3 CRUD builders for ``INSERT`` target inlining (SurrealDB rejects
    parameter binding such as ``type::table($x)`` on INSERT targets, so
    the SDK escapes the target identifier instead).
    """
    if not identifier:
        return f"⟨{identifier}⟩"

    has_special_chars = any(not c.isalnum() and c != "_" for c in identifier)
    # All-digit or all-symbol names need escaping to disambiguate from
    # numeric IDs in SurrealQL's record-id literal syntax.
    has_no_alpha = not any(c.isalpha() for c in identifier)

    if has_special_chars or has_no_alpha:
        escaped = identifier.replace("⟩", "\\⟩")
        return f"⟨{escaped}⟩"
    return identifier


class RecordID:
    """
    An identifier of the record. This class houses the ID of the row, and the table name.

    To reference a record in a query, prefer binding the whole ``RecordID``
    as a query variable — it is transmitted as a typed CBOR value, never
    concatenated into query text, so no escaping (or injection) is possible
    by construction::

        db.query("RELATE $a->owns->$b;", vars={"a": alice, "b": record_id})
        db.query("SELECT * FROM $rid;", vars={"rid": record_id})

    Note that only the *whole* record id can be bound: SurrealQL does not
    accept a variable as just the id part of a record-id literal
    (``company:$id`` is a parse error).

    Attributes:
        table_name: The table name associated with the record ID. This is
            the raw, unescaped table name.
        id: The ID of the row. This is the raw, unescaped value — for a
            string id, it does **not** carry the quoting information
            SurrealQL needs to tell it apart from a numeric id of the same
            digits (e.g. the string id ``"231"`` vs. the numeric id
            ``231``). Interpolating ``.id`` directly into a hand-built
            query string is unsafe for exactly this reason. When you cannot
            bind (composing query *text*, e.g. for logs, migration files,
            or an ``INSERT`` target — the one spot where the server rejects
            parameter binding), use ``str(record_id)`` for the full
            ``table:id`` target, or
            ``surrealdb.escape_identifier(str(record_id.id))`` for just the
            escaped id fragment.
    """

    def __init__(self, table_name: str, identifier: RecordIdValue) -> None:
        """
        The constructor for the RecordID class.

        Args:
            table_name: The table name associated with the record ID
            identifier: The ID of the row

        Raises:
            TypeError: if *table_name* is not a string, or *identifier* is not
                a type SurrealDB accepts as a record id.

        Both arguments used to accept anything at all, and the mistake surfaced
        only after a round trip: ``RecordID(1, "x")``, ``RecordID("t", 1.5)``
        and ``RecordID("t", None)`` all encoded cleanly and came back from the
        server as ``ValidationError: Parse error`` - which names neither the
        argument nor what was wrong with it, for a mistake that was fully
        decidable before any I/O.

        The check is *not* an invariant on the attributes: values decoded from
        the wire bypass it (see :meth:`_unchecked`), so this catches what you
        construct rather than guaranteeing what ``.id`` holds.
        """
        from surrealdb.types import Value  # imported here to prevent circular import

        if not isinstance(table_name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise table_name_type_error(
                "RecordID", table_name, "table_name", identifier
            )
        if isinstance(identifier, _ID_TYPE_IMPOSTORS) or not isinstance(
            identifier, _ID_TYPES
        ):
            raise _id_type_error(identifier)

        self.table_name: str = table_name
        #: Deliberately wider than :data:`RecordIdValue`. Every record read back
        #: is built through :meth:`_unchecked`, so a server the SDK has not been
        #: taught about can put anything here; narrowing the annotation would
        #: describe hand-built ids correctly and every decoded one wrongly.
        self.id: Value = cast(Value, identifier)

    @classmethod
    def _unchecked(cls, table_name: Any, identifier: Any) -> RecordID:
        """Build a ``RecordID`` without validating, for the CBOR decoder.

        The decoder builds one of these for every record it reads, so a check
        here would run against whatever a server sends rather than against
        anything a caller wrote - and a future server's new id type would stop
        the record being *readable* at all. That is strictly worse than the
        late error this validation exists to replace: you can work around a bad
        write, but not a record you cannot load.

        Worse still, ``tag_decoder`` runs inside the decode of a whole response,
        so raising here loses every other row with it. This module has shipped
        that failure twice already - the empty-``Duration`` ``IndexError`` and
        the ``set``-of-dicts ``unhashable type`` - and neither is worth a third.
        """
        record = object.__new__(cls)
        record.table_name = table_name
        record.id = identifier
        return record

    def __str__(self) -> str:
        # Only escape if the identifier is a string
        if isinstance(self.id, str):
            return f"{self.table_name}:{escape_identifier(self.id)}"
        if isinstance(self.id, bytes):
            # Rendered, not decoded. `_unchecked` means a wire value can still
            # be bytes, so this branch is live - and decoding it was wrong
            # twice over: it raised `UnicodeDecodeError` on anything that was
            # not UTF-8, and it rendered b"xy" as `t:xy`, which is a *different*
            # record from the one it names.
            return f"{self.table_name}:{self.id!r}"
        return f"{self.table_name}:{self.id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(table_name={self.table_name}, record_id={self.id!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecordID):
            return self.table_name == other.table_name and self.id == other.id
        return False

    def __hash__(self) -> int:
        # ``id`` may be an unhashable value (e.g. a dict or list) for
        # object/array record ids, so hash its string form to stay total.
        # This mirrors ``__eq__``: equal RecordIDs have equal ``table_name``
        # and equal ``id``, hence equal ``str(id)``.
        return hash((self.table_name, str(self.id)))

    @staticmethod
    def parse(record_str: str) -> RecordID:
        """
        Converts a string to a RecordID object.

        The string is split on the *first* colon only, so ids that
        themselves contain colons are preserved intact (e.g.
        ``"user:complex:id:here"`` yields table ``"user"`` and id
        ``"complex:id:here"``). ``parse`` always yields a string id — use
        the :class:`RecordID` constructor directly for numeric, array or
        object ids.

        Args:
            record_str: The string representation of the record ID

        Returns: A RecordID object.

        """
        if ":" not in record_str:
            raise InvalidRecordIdError(
                'invalid string provided for parse. the expected string format is "table_name:record_id"'
            )

        table, record_id = record_str.split(":", 1)
        return RecordID(table, record_id)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,  # pyright: ignore[reportExplicitAny, reportAny]
        _handler: Callable[[Any], core_schema.CoreSchema],  # pyright: ignore[reportExplicitAny]
    ) -> core_schema.CoreSchema:
        def validate_from_str(value: str, _info: ValidationInfo) -> RecordID:
            return RecordID.parse(value)

        from_str_schema = core_schema.str_schema()
        from_chain_schema = core_schema.chain_schema(
            [
                from_str_schema,
                core_schema.with_info_plain_validator_function(validate_from_str),
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=from_chain_schema,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(RecordID),
                    from_chain_schema,
                ]
            ),
            serialization=core_schema.wrap_serializer_function_ser_schema(
                lambda value, _handler, info: (
                    value if info.mode == "python" else str(value)
                ),
                info_arg=True,
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.str_schema())
