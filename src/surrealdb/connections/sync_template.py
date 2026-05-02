from collections.abc import Generator
from typing import Any, overload
from uuid import UUID

from surrealdb.connections.builders import (
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

        Returns a lazy builder. Triggering execution (e.g. by indexing,
        iterating, or calling ``.execute()``) returns:

        - The result Value when the server returned exactly one statement result
        - A ``tuple[Value, ...]`` of all statement results when N>1 statements
          ran (this is the v3.0 fix for issue #232 - earlier versions silently
          dropped every result after the first).

        Use ``.into(MyResult)`` to map the N statement results positionally onto
        a dataclass or any class accepting keyword arguments.
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    def select(self, record: RecordIdType) -> Value:
        """Select all records in a table or a specific record."""
        raise NotImplementedError(f"select not implemented for: {self}")

    @overload
    def create(
        self, record: RecordID, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self, record: RecordIdType, data: Value | None = None
    ) -> SyncCrudBuilder[Any]:
        """Create a record.

        Returns a lazy builder. Optional terminal clause methods:

        - ``.content(data)``  -> ``CREATE ... CONTENT $data``
        - ``.replace(data)``  -> ``CREATE ... REPLACE $data``
        - ``.merge(data)``    -> ``CREATE ... MERGE $data``
        - ``.patch(data)``    -> ``CREATE ... PATCH $data``

        ``db.create(record, data)`` is sugar for ``db.create(record).content(data)``.
        """
        raise NotImplementedError(f"create not implemented for: {self}")

    @overload
    def update(
        self, record: RecordID, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value | None = None
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def update(
        self, record: str, data: Value | None = None
    ) -> SyncCrudBuilder[Value]: ...
    def update(
        self, record: RecordIdType, data: Value | None = None
    ) -> SyncCrudBuilder[Any]:
        """Update records (replacing the existing data by default)."""
        raise NotImplementedError(f"update not implemented for: {self}")

    @overload
    def upsert(
        self, record: RecordID, data: Value | None = None
    ) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value | None = None
    ) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(
        self, record: str, data: Value | None = None
    ) -> SyncCrudBuilder[Value]: ...
    def upsert(
        self, record: RecordIdType, data: Value | None = None
    ) -> SyncCrudBuilder[Any]:
        """Insert or update records."""
        raise NotImplementedError(f"upsert not implemented for: {self}")

    @overload
    def delete(self, record: RecordID) -> SyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def delete(self, record: Table) -> SyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> SyncCrudBuilder[Value]: ...
    def delete(self, record: RecordIdType) -> SyncCrudBuilder[Any]:
        """Delete records."""
        raise NotImplementedError(f"delete not implemented for: {self}")

    def info(self) -> Value:
        """Return the record of the authenticated record user."""
        raise NotImplementedError(f"info not implemented for: {self}")

    def insert(
        self,
        table: str | Table,
        data: Value | None = None,
        *,
        relation: bool = False,
    ) -> SyncInsertBuilder:
        """Insert one or multiple records (or relations) into a table.

        Pass ``relation=True`` to issue ``INSERT RELATION INTO``, or chain
        ``.relation()`` on the returned builder.
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
