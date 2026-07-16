"""
Defines the data type for the record ID.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Union, cast

from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo

from surrealdb.data.types.table import Table
from surrealdb.errors import InvalidRecordIdError

if TYPE_CHECKING:
    from pydantic import GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue

RecordIdType = Union[str, "RecordID", Table]


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

    def __init__(self, table_name: str, identifier: Any) -> None:
        """
        The constructor for the RecordID class.

        Args:
            table_name: The table name associated with the record ID
            identifier: The ID of the row
        """
        from surrealdb.types import Value  # imported here to prevent circular import

        self.table_name: str = table_name
        self.id: Value = cast(Value, identifier)

    def __str__(self) -> str:
        # Only escape if the identifier is a string
        if isinstance(self.id, str):
            return f"{self.table_name}:{escape_identifier(self.id)}"
        if isinstance(self.id, bytes):
            return f"{self.table_name}:{escape_identifier(self.id.decode())}"
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
