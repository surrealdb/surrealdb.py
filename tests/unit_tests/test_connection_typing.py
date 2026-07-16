"""Static + runtime guards for connection CRUD overload precision.

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
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

if sys.version_info >= (3, 11):
    from typing import assert_type
else:
    from typing_extensions import assert_type

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import (
    AsyncSurrealSession,
    AsyncSurrealTransaction,
    AsyncWsSurrealConnection,
)
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingSurrealTransaction,
    BlockingWsSurrealConnection,
)
from surrealdb.connections.builders import (
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryIntoBuilder,
    SyncCrudBuilder,
    SyncInsertBuilder,
)
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.types import Value


@dataclass
class _Person:
    id: object
    name: str


def test_async_session_crud_overload_precision() -> None:
    if not TYPE_CHECKING:
        # Static type-guard only: ``assert_type`` is a runtime no-op, and the
        # eager sync CRUD methods must not perform real I/O when exercised
        # purely for their return type. mypy still checks the body below.
        return
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
        session.delete(RecordID("person", 1)),
        AsyncCrudBuilder[dict[str, Value] | None],
    )
    assert_type(session.delete(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(session.delete("person"), AsyncCrudBuilder[Value])


def test_async_transaction_crud_overload_precision() -> None:
    if not TYPE_CHECKING:
        # Static type-guard only: ``assert_type`` is a runtime no-op, and the
        # eager sync CRUD methods must not perform real I/O when exercised
        # purely for their return type. mypy still checks the body below.
        return
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

    assert_type(
        txn.delete(RecordID("person", 1)),
        AsyncCrudBuilder[dict[str, Value] | None],
    )
    assert_type(txn.delete(Table("person")), AsyncCrudBuilder[list[Value]])
    assert_type(txn.delete("person"), AsyncCrudBuilder[Value])


def test_blocking_session_crud_overload_precision() -> None:
    if not TYPE_CHECKING:
        # Static type-guard only: ``assert_type`` is a runtime no-op, and the
        # eager sync CRUD methods must not perform real I/O when exercised
        # purely for their return type. mypy still checks the body below.
        return
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

    # delete is eager on sync connections: it returns the result directly.
    assert_type(session.delete(RecordID("person", 1)), dict[str, Value] | None)
    assert_type(session.delete(Table("person")), list[Value])
    assert_type(session.delete("person"), Value)


def test_blocking_transaction_crud_overload_precision() -> None:
    if not TYPE_CHECKING:
        # Static type-guard only: ``assert_type`` is a runtime no-op, and the
        # eager sync CRUD methods must not perform real I/O when exercised
        # purely for their return type. mypy still checks the body below.
        return
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

    # delete is eager on sync connections: it returns the result directly.
    assert_type(txn.delete(RecordID("person", 1)), dict[str, Value] | None)
    assert_type(txn.delete(Table("person")), list[Value])
    assert_type(txn.delete("person"), Value)


# ---------------------------------------------------------------------------
# into= row-model overload precision
# ---------------------------------------------------------------------------


async def test_async_connection_into_overload_precision() -> None:
    if not TYPE_CHECKING:
        return
    ws = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    http = AsyncHttpSurrealConnection("http://localhost:8000")

    for conn in (ws, http):
        # select: single -> M | None, table -> list[M] (async -> awaited).
        assert_type(
            await conn.select(RecordID("person", 1), into=_Person), _Person | None
        )
        assert_type(await conn.select(Table("person"), into=_Person), list[_Person])
        assert_type(
            await conn.select("person", into=_Person), _Person | list[_Person] | None
        )

        # create is always single -> AsyncCrudBuilder[M].
        assert_type(
            conn.create(RecordID("person", 1), into=_Person),
            AsyncCrudBuilder[_Person],
        )
        assert_type(
            conn.create(RecordID("person", 1), {"name": "x"}, into=_Person),
            AsyncCrudBuilder[_Person],
        )

        # update / upsert vary by target.
        assert_type(
            conn.update(RecordID("person", 1), into=_Person),
            AsyncCrudBuilder[_Person],
        )
        assert_type(
            conn.update(Table("person"), into=_Person),
            AsyncCrudBuilder[list[_Person]],
        )
        assert_type(
            conn.upsert(Table("person"), into=_Person),
            AsyncCrudBuilder[list[_Person]],
        )

        # delete single -> M | None, table -> list[M].
        assert_type(
            conn.delete(RecordID("person", 1), into=_Person),
            AsyncCrudBuilder[_Person | None],
        )
        assert_type(
            conn.delete(Table("person"), into=_Person),
            AsyncCrudBuilder[list[_Person]],
        )

        # insert always -> AsyncInsertBuilder[M] (awaits to list[M]).
        assert_type(
            conn.insert(Table("person"), into=_Person), AsyncInsertBuilder[_Person]
        )
        assert_type(conn.insert(Table("person")), AsyncInsertBuilder[Value])

        # query().into(...) row-mapping.
        q = conn.query("SELECT * FROM person")
        assert_type(q.into(_Person), AsyncQueryIntoBuilder[_Person])
        assert_type(q.into(_Person, rows=True), AsyncQueryIntoBuilder[list[_Person]])


async def test_async_wrapper_into_overload_precision() -> None:
    if not TYPE_CHECKING:
        return
    conn = AsyncWsSurrealConnection("ws://localhost:8000/rpc")
    session = AsyncSurrealSession(conn, uuid4())
    txn = AsyncSurrealTransaction(conn, uuid4(), uuid4())

    for wrapper in (session, txn):
        assert_type(
            await wrapper.select(RecordID("person", 1), into=_Person), _Person | None
        )
        assert_type(await wrapper.select(Table("person"), into=_Person), list[_Person])
        assert_type(
            wrapper.create(RecordID("person", 1), into=_Person),
            AsyncCrudBuilder[_Person],
        )
        assert_type(
            wrapper.update(Table("person"), into=_Person),
            AsyncCrudBuilder[list[_Person]],
        )
        assert_type(
            wrapper.delete(RecordID("person", 1), into=_Person),
            AsyncCrudBuilder[_Person | None],
        )
        assert_type(
            wrapper.insert(Table("person"), into=_Person), AsyncInsertBuilder[_Person]
        )


def test_blocking_connection_into_overload_precision() -> None:
    if not TYPE_CHECKING:
        return
    ws = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    http = BlockingHttpSurrealConnection("http://localhost:8000")

    for conn in (ws, http):
        # select is eager: single -> M | None, table -> list[M].
        assert_type(conn.select(RecordID("person", 1), into=_Person), _Person | None)
        assert_type(conn.select(Table("person"), into=_Person), list[_Person])

        # no-data create -> builder carrying M; eager data form -> M.
        assert_type(
            conn.create(RecordID("person", 1), into=_Person),
            SyncCrudBuilder[_Person],
        )
        assert_type(
            conn.create(RecordID("person", 1), {"name": "x"}, into=_Person), _Person
        )

        # update no-data builder vs eager result.
        assert_type(
            conn.update(Table("person"), into=_Person),
            SyncCrudBuilder[list[_Person]],
        )
        assert_type(
            conn.update(Table("person"), {"name": "x"}, into=_Person), list[_Person]
        )

        # delete is eager on sync: single -> M | None, table -> list[M].
        assert_type(conn.delete(RecordID("person", 1), into=_Person), _Person | None)
        assert_type(conn.delete(Table("person"), into=_Person), list[_Person])

        # insert: no-data builder carrying M vs eager list[M].
        assert_type(
            conn.insert(Table("person"), into=_Person), SyncInsertBuilder[_Person]
        )
        assert_type(
            conn.insert(Table("person"), [{"name": "x"}], into=_Person), list[_Person]
        )

        # query().into(...) row-mapping is eager on sync.
        sq = conn.query("SELECT * FROM person")
        assert_type(sq.into(_Person), _Person)
        assert_type(sq.into(_Person, rows=True), list[_Person])


def test_blocking_wrapper_into_overload_precision() -> None:
    if not TYPE_CHECKING:
        return
    conn = BlockingWsSurrealConnection("ws://localhost:8000/rpc")
    session = BlockingSurrealSession(conn, uuid4())
    txn = BlockingSurrealTransaction(conn, uuid4(), uuid4())

    for wrapper in (session, txn):
        assert_type(wrapper.select(RecordID("person", 1), into=_Person), _Person | None)
        assert_type(wrapper.select(Table("person"), into=_Person), list[_Person])
        assert_type(
            wrapper.create(RecordID("person", 1), into=_Person),
            SyncCrudBuilder[_Person],
        )
        assert_type(
            wrapper.create(RecordID("person", 1), {"name": "x"}, into=_Person), _Person
        )
        assert_type(wrapper.delete(RecordID("person", 1), into=_Person), _Person | None)
        assert_type(
            wrapper.insert(Table("person"), into=_Person), SyncInsertBuilder[_Person]
        )
