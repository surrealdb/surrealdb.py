"""Static + runtime guards for connection CRUD overload precision (#16).

``AsyncSurrealSession`` / ``AsyncSurrealTransaction`` (and their blocking
equivalents) must expose the same ``@overload`` precision as the base
connection: ``RecordID`` narrows the builder to a single ``dict`` result,
``Table`` to a ``list`` result, and a raw ``str`` to a bare ``Value``.

``assert_type`` is a runtime no-op, so this module doubles as a type-checker
regression guard: if any wrapper drops its overloads and falls back to
``CrudBuilder[Any]``, both mypy and pyright fail the ``assert_type`` calls
below (``Any`` does not match the asserted concrete type).
"""

import sys
from uuid import uuid4

if sys.version_info >= (3, 11):
    from typing import assert_type
else:
    from typing_extensions import assert_type

from surrealdb.connections.async_ws import (
    AsyncSurrealSession,
    AsyncSurrealTransaction,
    AsyncWsSurrealConnection,
)
from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingSurrealTransaction,
    BlockingWsSurrealConnection,
)
from surrealdb.connections.builders import AsyncCrudBuilder, SyncCrudBuilder
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.types import Value


def test_async_session_crud_overload_precision() -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    session = AsyncSurrealSession(conn, uuid4())

    assert_type(
        session.create(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.create(Table("person")), AsyncCrudBuilder[dict[str, Value]])
    assert_type(session.create("person"), AsyncCrudBuilder[dict[str, Value]])

    assert_type(
        session.update(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.update(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(session.update("person"), AsyncCrudBuilder[Value])

    assert_type(
        session.upsert(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.upsert(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(session.upsert("person"), AsyncCrudBuilder[Value])

    assert_type(
        session.delete(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.delete(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(session.delete("person"), AsyncCrudBuilder[Value])


def test_async_transaction_crud_overload_precision() -> None:
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    txn = AsyncSurrealTransaction(conn, uuid4(), uuid4())

    assert_type(txn.create(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]])
    assert_type(txn.create(Table("person")), AsyncCrudBuilder[dict[str, Value]])
    assert_type(txn.create("person"), AsyncCrudBuilder[dict[str, Value]])

    assert_type(txn.update(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]])
    assert_type(txn.update(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(txn.update("person"), AsyncCrudBuilder[Value])

    assert_type(txn.upsert(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]])
    assert_type(txn.upsert(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(txn.upsert("person"), AsyncCrudBuilder[Value])

    assert_type(txn.delete(RecordID("person", 1)), AsyncCrudBuilder[dict[str, Value]])
    assert_type(txn.delete(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(txn.delete("person"), AsyncCrudBuilder[Value])


def test_blocking_session_crud_overload_precision() -> None:
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    session = BlockingSurrealSession(conn, uuid4())

    assert_type(
        session.create(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.create(Table("person")), SyncCrudBuilder[dict[str, Value]])
    assert_type(session.create("person"), SyncCrudBuilder[dict[str, Value]])

    assert_type(
        session.update(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.update(Table("person")), SyncCrudBuilder[list[Value]])
    assert_type(session.update("person"), SyncCrudBuilder[Value])

    assert_type(
        session.upsert(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.upsert(Table("person")), SyncCrudBuilder[list[Value]])
    assert_type(session.upsert("person"), SyncCrudBuilder[Value])

    assert_type(
        session.delete(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]]
    )
    assert_type(session.delete(Table("person")), SyncCrudBuilder[list[Value]])
    assert_type(session.delete("person"), SyncCrudBuilder[Value])


def test_blocking_transaction_crud_overload_precision() -> None:
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    txn = BlockingSurrealTransaction(conn, uuid4(), uuid4())

    assert_type(txn.create(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]])
    assert_type(txn.create(Table("person")), SyncCrudBuilder[dict[str, Value]])
    assert_type(txn.create("person"), SyncCrudBuilder[dict[str, Value]])

    assert_type(txn.update(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]])
    assert_type(txn.update(Table("person")), SyncCrudBuilder[list[Value]])
    assert_type(txn.update("person"), SyncCrudBuilder[Value])

    assert_type(txn.upsert(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]])
    assert_type(txn.upsert(Table("person")), SyncCrudBuilder[list[Value]])
    assert_type(txn.upsert("person"), SyncCrudBuilder[Value])

    assert_type(txn.delete(RecordID("person", 1)), SyncCrudBuilder[dict[str, Value]])
    assert_type(txn.delete(Table("person")), SyncCrudBuilder[list[Value]])
    assert_type(txn.delete("person"), SyncCrudBuilder[Value])
