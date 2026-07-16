from collections.abc import Generator
from typing import Any, overload
from uuid import UUID

from surrealdb.connections.builders import (
    _UNSET,
    M,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
)
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.types import Tokens, Value


class SyncTemplate:
    def close(self) -> None:
        """Closes the persistent connection to the database."""
        raise NotImplementedError(f"close not implemented for: {self}")

    def use(self, namespace: str, database: str) -> None:
        """Switch to a specific namespace and database."""
        raise NotImplementedError(f"use not implemented for: {self}")

    def authenticate(self, token: str) -> None:
        """Authenticate the current connection with a JWT token."""
        raise NotImplementedError(f"authenticate not implemented for: {self}")

    def invalidate(self) -> None:
        """Invalidate the authentication for the current connection."""
        raise NotImplementedError(f"invalidate not implemented for: {self}")

    def signup(self, vars: dict[str, Value]) -> Tokens:
        """Sign this connection up to a specific authentication scope."""
        raise NotImplementedError(f"signup not implemented for: {self}")

    def signin(self, vars: dict[str, Value]) -> Tokens:
        """Sign this connection in to a specific authentication scope."""
        raise NotImplementedError(f"signin not implemented for: {self}")

    def let(self, key: str, value: Value) -> None:
        """Assign a value as a variable for this connection."""
        raise NotImplementedError(f"let not implemented for: {self}")

    def unset(self, key: str) -> None:
        """Removes a variable for this connection."""
        raise NotImplementedError(f"unset not implemented for: {self}")

    def query(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> SyncQueryBuilder:
        """Run one or more SurrealQL statements against the database.

        Returns a builder. Trigger execution explicitly:

        - ``.execute()`` -> ``list[Value]`` (one entry per statement, always a
          list even for a single statement - this is the v3.0 fix for issue
          #232, earlier versions silently dropped every result after the
          first).
        - ``.first()`` -> the first statement's result (``None`` if no
          statements).
        - ``.into(MyResult)`` maps the N statement results positionally onto a
          dataclass or any class accepting keyword arguments.
        - ``.into(Model, rows=True)`` maps each ROW of the single statement
          result onto ``Model``, returning ``list[Model]``.
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    @overload
    def select(self, record: RecordID, *, into: type[M]) -> M | None: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> list[M]: ...
    @overload
    def select(self, record: str, *, into: type[M]) -> M | list[M] | None: ...
    @overload
    def select(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def select(self, record: Table) -> list[Value]: ...
    @overload
    def select(self, record: str) -> Value: ...
    def select(self, record: RecordIdType, *, into: type[M] | None = None) -> Any:
        """Select all records in a table or a specific record.

        A ``RecordID`` (or ``"table:id"`` string) returns the record dict, or
        ``None`` when it is absent. A ``Table`` (or bare table-name string)
        returns the list of records.

        Pass ``into=Model`` to map each record onto a model class (dataclass,
        pydantic ``BaseModel``, or any kwargs-constructible class): a single
        record resolves to ``Model | None``, a table to ``list[Model]``.
        """
        raise NotImplementedError(f"select not implemented for: {self}")

    @overload
    def create(self, record: RecordIdType, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def create(self, record: RecordIdType, data: Value, *, into: type[M]) -> M: ...
    @overload
    def create(self, record: RecordIdType) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(self, record: RecordIdType, data: Value) -> dict[str, Value]: ...
    def create(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M] | None = None
    ) -> Any:
        """Create a record.

        ``db.create(record, data)`` runs ``CREATE ... CONTENT $data`` eagerly
        and returns the created record (``data=None`` runs ``CONTENT NULL``).
        ``db.create(record)`` (no data) returns a :class:`SyncCrudBuilder`;
        pick a terminal clause to run it:

        - ``.content(data)``  -> ``CREATE ... CONTENT $data``
        - ``.replace(data)``  -> ``CREATE ... REPLACE $data``
        - ``.merge(data)``    -> ``CREATE ... MERGE $data``
        - ``.patch(data)``    -> ``CREATE ... PATCH $data``
        - ``.execute()``      -> ``CREATE ...`` (no clause)

        Pass ``into=Model`` to map the created record onto ``Model`` (the eager
        form returns ``Model``; the builder form's clause methods return ``Model``).
        """
        raise NotImplementedError(f"create not implemented for: {self}")

    @overload
    def update(self, record: RecordID, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def update(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def update(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(self, record: RecordID, data: Value, *, into: type[M]) -> M: ...
    @overload
    def update(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def update(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def update(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def update(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def update(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def update(self, record: str, data: Value) -> Value: ...
    def update(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M] | None = None
    ) -> Any:
        """Update records (replacing the existing data by default).

        ``db.update(record, data)`` runs eagerly and returns the result; the
        no-data form returns a :class:`SyncCrudBuilder` with terminal clause
        methods (``.content`` / ``.replace`` / ``.merge`` / ``.patch`` /
        ``.execute``). Pass ``into=Model`` to map the returned record(s) onto
        ``Model`` (a ``RecordID`` target resolves to ``Model``, a ``Table`` to
        ``list[Model]``).
        """
        raise NotImplementedError(f"update not implemented for: {self}")

    @overload
    def upsert(self, record: RecordID, *, into: type[M]) -> SyncCrudBuilder[M]: ...
    @overload
    def upsert(self, record: Table, *, into: type[M]) -> SyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(self, record: str, *, into: type[M]) -> SyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(self, record: RecordID, data: Value, *, into: type[M]) -> M: ...
    @overload
    def upsert(self, record: Table, data: Value, *, into: type[M]) -> list[M]: ...
    @overload
    def upsert(self, record: str, data: Value, *, into: type[M]) -> M | list[M]: ...
    @overload
    def upsert(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(self, record: str) -> SyncCrudBuilder[Value]: ...
    @overload
    def upsert(self, record: RecordID, data: Value) -> dict[str, Value]: ...
    @overload
    def upsert(self, record: Table, data: Value) -> list[Value]: ...
    @overload
    def upsert(self, record: str, data: Value) -> Value: ...
    def upsert(
        self, record: RecordIdType, data: Value = _UNSET, *, into: type[M] | None = None
    ) -> Any:
        """Insert or update records.

        ``db.upsert(record, data)`` runs eagerly and returns the result; the
        no-data form returns a :class:`SyncCrudBuilder` with terminal clause
        methods. Pass ``into=Model`` to map the returned record(s) onto
        ``Model`` (a ``RecordID`` target resolves to ``Model``, a ``Table`` to
        ``list[Model]``).
        """
        raise NotImplementedError(f"upsert not implemented for: {self}")

    @overload
    def delete(self, record: RecordID, *, into: type[M]) -> M | None: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> list[M]: ...
    @overload
    def delete(self, record: str, *, into: type[M]) -> M | list[M] | None: ...
    @overload
    def delete(self, record: RecordID) -> dict[str, Value] | None: ...
    @overload
    def delete(self, record: Table) -> list[Value]: ...
    @overload
    def delete(self, record: str) -> Value: ...
    def delete(self, record: RecordIdType, *, into: type[M] | None = None) -> Any:
        """Delete records eagerly and return the deleted record(s).

        A ``RecordID`` (or ``"table:id"``) returns the deleted record, or
        ``None`` when no record was deleted (matching select); a ``Table``
        (or bare name) returns the list of deleted records. Pass ``into=Model``
        to map the deleted record(s) onto ``Model``.
        """
        raise NotImplementedError(f"delete not implemented for: {self}")

    def info(self) -> Value:
        """Return the record of the authenticated record user."""
        raise NotImplementedError(f"info not implemented for: {self}")

    @overload
    def insert(
        self, table: str | Table, *, relation: bool = False
    ) -> SyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self, table: str | Table, *, into: type[M], relation: bool = False
    ) -> SyncInsertBuilder[M]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, relation: bool = False
    ) -> list[Value]: ...
    @overload
    def insert(
        self, table: str | Table, data: Value, *, into: type[M], relation: bool = False
    ) -> list[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value = _UNSET,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> Any:
        """Insert one or multiple records (or relations) into a table.

        ``db.insert(table, data)`` runs eagerly and returns the inserted
        records. ``db.insert(table)`` (no data) returns a
        :class:`SyncInsertBuilder`; pass ``relation=True`` (or chain
        ``.relation()``) for ``INSERT RELATION INTO`` and run it with
        ``.content(data)`` / ``.execute()``. Pass ``into=Model`` to map the
        inserted records onto ``list[Model]``.
        """
        raise NotImplementedError(f"insert not implemented for: {self}")

    def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        """Run a SurrealDB function and return its result."""
        raise NotImplementedError(f"run not implemented for: {self}")

    def live(self, table: str | Table, diff: bool = False) -> UUID:
        """Initiate a live query on the given table."""
        raise NotImplementedError(f"live not implemented for: {self}")

    def subscribe_live(
        self, query_uuid: str | UUID
    ) -> Generator[dict[str, Value], None, None]:
        """Iterate live notifications for the given live query id."""
        raise NotImplementedError(f"subscribe_live not implemented for: {self}")

    def kill(self, query_uuid: str | UUID) -> None:
        """Kill a running live query by its UUID."""
        raise NotImplementedError(f"kill not implemented for: {self}")
