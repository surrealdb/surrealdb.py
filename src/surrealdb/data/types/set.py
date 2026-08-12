"""SurrealDB's ``set<T>``, which neither a Python ``set`` nor a ``list`` models.

A SurrealDB set is a *deduplicated sequence*. Two things follow, and no builtin
gives both:

* it holds any value, including objects and arrays - ``set<object>`` is an
  ordinary column - which a Python ``set`` cannot, because its members must be
  hashable;
* it is a distinct type from an array, and the server enforces that: a
  schemafull ``set<T>`` field refuses a plain array, and a schemaless field that
  holds a set stops deduplicating once it is overwritten with one.

Decoding into a Python ``set`` failed the first: ``unhashable type: 'dict'``,
raised while decoding, took the whole response with it, so any ``SELECT *``
touching such a field died and the record could not be read in its native form.

Decoding into a plain ``list`` failed the second, and did it silently. Reading a
record and writing it back - the most ordinary operation there is - either
failed outright::

    row = db.select(rec)          # {"nums": [1, 2]}
    db.update(rec, row)
    # InternalError: Couldn't coerce value for field `nums`:
    #                Expected `set` but found `[1, 2]`

or, on a schemaless table, quietly changed the field's type::

    stored before: {'a', 'b'}
    stored after : ['a', 'b']      # after a read-modify-write
    after += 'a' : ['a', 'b', 'a'] # deduplication gone

:class:`SurrealSet` is a ``list`` subclass, so it reads and indexes like the
sequence it is and compares equal to the equivalent list, and it encodes back
under SurrealDB's set tag, so the round trip keeps the field a set.

The order is whatever the server sent - SurrealDB normalises a set, so
``<set>[3,1,2]`` comes back as ``[1,2,3]`` - and it is significant for equality,
as it is for any list. Writing a plain Python ``set`` still works and is still
sent as a set; that path never changed.
"""

from typing import Any


class SurrealSet(list[Any]):
    """A SurrealDB ``set<T>``. See the module docstring for why it exists."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"SurrealSet({list.__repr__(self)})"
