"""SurrealDB's ``NULL``, which Python's ``None`` cannot represent on its own.

SurrealDB has two ways for a field to hold nothing, and they are not the same
value:

``NONE``
    The field is not there. An unset ``option<T>`` column is NONE, and a NONE
    field does not appear in a record at all when you read it.

``NULL``
    The field is there and its value is null. A column has to be declared to
    permit it - ``option<T>`` alone does not, and rejects NULL.

Python has one ``None``, so the SDK has to say which one it means. ``None``
means NONE, because that is what ``option<T>`` columns take and they are the
common case. ``Null`` means NULL.

This distinction is not cosmetic: without it, reading a record and writing it
back destroyed data. A NULL field read as ``None`` and sent back as NONE does
not stay null - the field is *removed*, silently, on the most ordinary
operation there is:

    row = db.select(rec)      # {"nickname": Null}
    row["name"] = "new name"
    db.update(rec, row)       # nickname stays NULL, because Null went back

Reading a NULL field gives ``Null``, so writing that record back sends NULL
again and the round trip is lossless.
"""

from typing import Any, NoReturn


class NullType:
    """The type of :data:`Null`. There is only ever one instance.

    Falsy, like ``None``, so ``if not row["nickname"]`` behaves the way it
    reads. Deliberately *not* equal to ``None``: the whole point is that the
    two are different values to SurrealDB, and quietly comparing equal would
    put back exactly the confusion this type exists to remove.
    """

    _instance: "NullType | None" = None

    def __new__(cls) -> "NullType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "Null"

    def __bool__(self) -> bool:
        return False

    def __hash__(self) -> int:
        return hash(NullType)

    def __eq__(self, other: object) -> bool:
        return other is self

    def __ne__(self, other: object) -> bool:
        return other is not self

    # Copying and pickling have to preserve the singleton, or `Null` read back
    # out of a deepcopy or a cache would compare unequal to the real one and
    # `is Null` checks would start failing for no visible reason.
    def __copy__(self) -> "NullType":
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> "NullType":
        return self

    def __reduce__(self) -> tuple[type["NullType"], tuple[()]]:
        return (NullType, ())

    def __setattr__(self, name: str, value: Any) -> NoReturn:
        raise AttributeError("Null is immutable")


Null = NullType()
"""SurrealDB's ``NULL``. See :class:`NullType`."""
