"""The row a builder yields is typed, for every shape a builder can take.

``for row in db.select(...)`` and ``db.select(...).rows()`` used to hand back
``Any``, so a typo in ``row["nmae"]`` was invisible to a type checker. The row
type follows from the builder's result type: records are ``dict[str, Value]``,
and ``into=Model`` yields ``Model`` whichever way the target was spelled.

``assert_type`` is a runtime no-op, so this module is a regression guard for the
type checkers, not for the runtime: if an overload is dropped or reordered so a
shape falls through to ``Any`` or the wrong type, mypy fails the call. Every
shape is listed because the result types are unions (``Model | list[Model] |
None`` for a string target with ``into=``) and the overloads that separate them
are order-sensitive - checked under mypy and pyright, which resolve them
differently.
"""

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if sys.version_info >= (3, 11):
    from typing import assert_type
else:
    from typing_extensions import assert_type

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.builders import AsyncRows, SyncRows
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.types import Value

Record = dict[str, Value]


@dataclass
class Person:
    name: str


def test_blocking_builders_yield_typed_rows() -> None:
    if not TYPE_CHECKING:
        return
    db: BlockingWsSurrealConnection = BlockingWsSurrealConnection("ws://x")
    rid = RecordID("person", "tobie")

    for row in db.select(Table("person")):
        assert_type(row, Record)
    for row in db.select(rid):
        assert_type(row, Record)
    for row in db.select("person"):
        assert_type(row, Record)
    for row in db.create(rid):
        assert_type(row, Record)
    for row in db.insert("person"):
        assert_type(row, Record)

    for person in db.select(Table("person"), into=Person):
        assert_type(person, Person)
    for person in db.select(rid, into=Person):
        assert_type(person, Person)
    for person in db.select("person", into=Person):
        assert_type(person, Person)
    for person in db.update("person", into=Person):
        assert_type(person, Person)
    for person in db.create(rid, into=Person):
        assert_type(person, Person)
    for person in db.insert("person", into=Person):
        assert_type(person, Person)
    for person in db.query("SELECT * FROM person").rows(into=Person):
        assert_type(person, Person)

    with db.select(Table("person")).rows() as records:
        assert_type(records, SyncRows[Record])
    with db.select("person", into=Person).rows() as people:
        assert_type(people, SyncRows[Person])
    with db.select(Table("person")).rows(into=Person) as mapped:
        assert_type(mapped, SyncRows[Person])
    with db.insert("person").rows() as inserted:
        assert_type(inserted, SyncRows[Record])
    with db.query("SELECT * FROM person").rows() as anything:
        assert_type(anything, SyncRows[Any])


async def test_async_builders_yield_typed_rows() -> None:
    if not TYPE_CHECKING:
        return
    db: AsyncWsSurrealConnection = AsyncWsSurrealConnection("ws://x")
    rid = RecordID("person", "tobie")

    async for row in db.select(Table("person")):
        assert_type(row, Record)
    async for row in db.select(rid):
        assert_type(row, Record)
    async for row in db.select("person"):
        assert_type(row, Record)
    async for row in db.create(rid):
        assert_type(row, Record)
    async for row in db.insert("person"):
        assert_type(row, Record)

    async for person in db.select(Table("person"), into=Person):
        assert_type(person, Person)
    async for person in db.select(rid, into=Person):
        assert_type(person, Person)
    async for person in db.select("person", into=Person):
        assert_type(person, Person)
    async for person in db.update("person", into=Person):
        assert_type(person, Person)
    async for person in db.create(rid, into=Person):
        assert_type(person, Person)
    async for person in db.insert("person", into=Person):
        assert_type(person, Person)
    async for person in db.query("SELECT * FROM person").rows(into=Person):
        assert_type(person, Person)

    async with db.select(Table("person")).rows() as records:
        assert_type(records, AsyncRows[Record])
    async with db.select("person", into=Person).rows() as people:
        assert_type(people, AsyncRows[Person])
    async with db.select(Table("person")).rows(into=Person) as mapped:
        assert_type(mapped, AsyncRows[Person])
