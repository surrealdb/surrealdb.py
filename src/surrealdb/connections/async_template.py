from collections.abc import AsyncGenerator, Mapping
from contextlib import AbstractContextManager, nullcontext
from typing import Any, overload
from uuid import UUID

from surrealdb.connections.api import ApiResponse
from surrealdb.connections.builders import (
    _UNSET,
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryBuilder,
    M,
    RelateEdge,
    RelateEnd,
)
from surrealdb.connections.import_export import (
    ExportOptions,
    ExportTarget,
    ImportData,
)
from surrealdb.connections.live import AsyncLiveSubscription
from surrealdb.connections.timeouts import check_timeout
from surrealdb.data.types.null import NullType
from surrealdb.data.types.record_id import RecordID, RecordIdType, StringRecordId
from surrealdb.data.types.table import Table
from surrealdb.types import Tokens, Value


class AsyncTemplate:
    def timeout(self, seconds: float | None) -> AbstractContextManager[None]:
        """Wait *seconds* for each reply to a request made inside the block.

        Remote connections override this. For the embedded engine requests
        never leave the process, so there is nothing to bound and the block
        runs unchanged.
        """
        check_timeout("timeout", seconds)
        return nullcontext()

    async def connect(self, url: str) -> None:
        """Connects to a local or remote database endpoint.

        Args:
            url: The url of the database endpoint to connect to.

        Example:
            await db.connect('https://cloud.surrealdb.com/rpc')
        """
        raise NotImplementedError(f"connect not implemented for: {self}")

    async def close(self) -> None:
        """Closes the persistent connection to the database.

        Example:
            await db.close()
        """
        raise NotImplementedError(f"close not implemented for: {self}")

    async def use(
        self,
        namespace: str | NullType | None = None,
        database: str | NullType | None = None,
    ) -> None:
        """Switch to a specific namespace and database.

        Args:
            namespace: The namespace to select; ``None`` keeps the current
                one and ``Null`` clears it.
            database: The database to select; ``None`` keeps the current one
                and ``Null`` clears it.

        Example:
            await db.use('test', 'test')
        """
        raise NotImplementedError(f"use not implemented for: {self}")

    async def refresh(self, tokens: Tokens | None = None) -> Tokens:
        """Exchange a refresh token for a new access and refresh token.

        Args:
            tokens: The tokens to exchange; by default the ones this
                connection signed in with.
        """
        raise NotImplementedError(f"refresh not implemented for: {self}")

    async def revoke(self, tokens: Tokens | None = None) -> None:
        """Revoke a refresh token so it can never be exchanged again.

        Args:
            tokens: The tokens whose refresh token to revoke; by default the
                ones this connection signed in with.
        """
        raise NotImplementedError(f"revoke not implemented for: {self}")

    async def reset(self) -> None:
        """Clear the namespace, database, variables and authentication."""
        raise NotImplementedError(f"reset not implemented for: {self}")

    async def export(self, options: ExportOptions | None = None) -> str:
        """Export the selected database as SurrealQL."""
        raise NotImplementedError(f"export not implemented for: {self}")

    async def export_to(
        self, target: ExportTarget, options: ExportOptions | None = None
    ) -> None:
        """Export the selected database as SurrealQL into a file, as it arrives."""
        raise NotImplementedError(f"export_to not implemented for: {self}")

    async def import_(self, data: ImportData) -> None:
        """Import SurrealQL into the selected database."""
        raise NotImplementedError(f"import_ not implemented for: {self}")

    async def health(self) -> None:
        """Raise unless the server reports itself healthy."""
        raise NotImplementedError(f"health not implemented for: {self}")

    async def api(
        self,
        path: str,
        *,
        method: str = "get",
        body: Value = None,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> ApiResponse:
        """Call an endpoint defined with ``DEFINE API``."""
        raise NotImplementedError(f"api not implemented for: {self}")

    async def gql(
        self, query: str, vars: Mapping[str, Value] | None = None
    ) -> list[Value]:
        """Run an ISO GQL query and return each statement's result."""
        raise NotImplementedError(f"gql not implemented for: {self}")

    async def graphql(
        self,
        query: str,
        variables: Mapping[str, Value] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Value]:
        """Run a GraphQL query and return the server's ``{data, errors}``."""
        raise NotImplementedError(f"graphql not implemented for: {self}")

    async def authenticate(self, token: str) -> None:
        """Authenticate the current connection with a JWT token.

        Args:
            token: The JWT authentication token.

        Example:
            await db.authenticate('insert token here')
        """
        raise NotImplementedError(f"authenticate not implemented for: {self}")

    async def invalidate(self) -> None:
        """Invalidate the authentication for the current connection.

        Example:
            await db.invalidate()
        """
        raise NotImplementedError(f"invalidate not implemented for: {self}")

    async def signup(self, vars: dict[str, Value]) -> Tokens:
        """Sign this connection up to a specific authentication scope.
        [See the docs](https://surrealdb.com/docs/sdk/python/methods/signup)

        Args:
            vars: Variables used in a signup query (namespace, database, access,
                variables for record auth; or user/pass for system auth).

        Returns:
            Tokens with optional access and refresh. Use access with authenticate().
        """
        raise NotImplementedError(f"signup not implemented for: {self}")

    async def signin(self, vars: dict[str, Value]) -> Tokens:
        """Sign this connection in to a specific authentication scope.
        [See the docs](https://surrealdb.com/docs/sdk/python/methods/signin)

        Args:
            vars: Variables for signin: username/password (system), or
                namespace, database, access, variables (record), or
                namespace, database, access, key (bearer), or
                namespace, database, access, refresh (refresh token).

        Returns:
            Tokens with optional access and refresh. Use access with authenticate().
        """
        raise NotImplementedError(f"signin not implemented for: {self}")

    async def let(self, key: str, value: Value) -> None:
        """Assign a value as a variable for this connection.

        Args:
            key: Specifies the name of the variable.
            value: Assigns the value to the variable name.

        Example:
            await db.let('name', {'first': 'Tobie', 'last': 'Morgan Hitchcock'})
            await db.query('CREATE person SET name = $name')
        """
        raise NotImplementedError(f"let not implemented for: {self}")

    async def set(self, key: str, value: Value) -> None:
        """Assign a value as a variable for this connection; ``let`` by its JS name."""
        await self.let(key, value)

    async def unset(self, key: str) -> None:
        """Removes a variable for this connection.

        Args:
            key: Specifies the name of the variable.
        """
        raise NotImplementedError(f"unset not implemented for: {self}")

    def query(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> AsyncQueryBuilder:
        """Run one or more SurrealQL statements against the database.

        Returns an awaitable builder. Awaiting it (or calling ``.execute()``)
        returns ``list[Value]`` - one entry per statement, always a list even
        for a single statement (this is the v3.0 fix for issue #232 - earlier
        versions silently dropped every result after the first).

        Use ``.first()`` for the first statement's result, or ``.into(MyResult)``
        to map the N statement results positionally onto a dataclass or any
        class accepting keyword arguments. ``.into(Model, rows=True)`` instead
        maps each ROW of the single statement result onto ``Model``, returning
        ``list[Model]``.

        Args:
            query: SurrealQL statement(s).
            vars: Variables referenced in the query.

        Example:
            rows = await db.query('SELECT * FROM person')  # list of statements
            first = await db.query('SELECT * FROM person').first()
            many = await db.query('SELECT * FROM person; SELECT count() FROM person GROUP ALL')
            mapped = await db.query('CREATE ...; SELECT ...').into(MyResult)
            people = await db.query('SELECT * FROM person').into(Person, rows=True)
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    @overload
    def select(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def select(self, record: Table, *, into: type[M]) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def select(
        self, record: str, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def select(
        self, record: RecordID | StringRecordId
    ) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def select(self, record: Table) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def select(self, record: str) -> AsyncCrudBuilder[Value]: ...
    def select(
        self, record: RecordIdType, *, into: type[M] | None = None
    ) -> AsyncCrudBuilder[Any]:
        """Select all records in a table or a specific record.

        A ``RecordID`` (or ``"table:id"`` string) returns the record dict, or
        ``None`` when it is absent. A ``Table`` (or bare table-name string)
        returns the list of records.

        Pass ``into=Model`` to map each record onto a model class (dataclass,
        pydantic ``BaseModel``, or any kwargs-constructible class): a single
        record resolves to ``Model | None``, a table to ``list[Model]``.

        Args:
            record: The table or record ID to select.
            into: Optional model class to map the selected record(s) onto.
        """
        raise NotImplementedError(f"select not implemented for: {self}")

    @overload
    def create(
        self, record: RecordIdType, data: Value | None = None, *, into: type[M]
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def create(
        self, record: RecordID | StringRecordId, data: Value | None = None
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value | None = None
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value | None = None
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self,
        record: RecordIdType,
        data: Value | None = None,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Create a record.

        Returns an awaitable builder. Optional clause methods:

        - ``.content(data)``  -> ``CREATE ... CONTENT $data``
        - ``.replace(data)``  -> ``CREATE ... REPLACE $data``
        - ``.merge(data)``    -> ``CREATE ... MERGE $data``
        - ``.patch(data)``    -> ``CREATE ... PATCH $data``

        ``db.create(record, data)`` is sugar for ``db.create(record).content(data)``.
        Pass ``into=Model`` to map the created record onto ``Model`` (the
        builder and its clause methods then resolve to ``Model``).

        Example:
            await db.create(RecordID('person', 'tobie'), {'name': 'Tobie'})
            await db.create(RecordID('person', 'tobie')).merge({'name': 'Tobie'})
            await db.create(RecordID('person', 'tobie'), data, into=Person)
        """
        raise NotImplementedError(f"create not implemented for: {self}")

    @overload
    def update(
        self,
        record: RecordID | StringRecordId,
        data: Value | None = None,
        *,
        into: type[M],
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def update(
        self, record: Table, data: Value | None = None, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def update(
        self, record: str, data: Value | None = None, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def update(
        self, record: RecordID | StringRecordId, data: Value | None = None
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value | None = None
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def update(
        self, record: str, data: Value | None = None
    ) -> AsyncCrudBuilder[Value]: ...
    def update(
        self,
        record: RecordIdType,
        data: Value | None = None,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Update records (replacing the existing data by default).

        Returns an awaitable builder. Optional clause methods:
        ``.content(data)``, ``.replace(data)``, ``.merge(data)``, ``.patch(data)``.
        Pass ``into=Model`` to map the returned record(s) onto ``Model`` (a
        ``RecordID`` target resolves to ``Model``, a ``Table`` to ``list[Model]``).
        """
        raise NotImplementedError(f"update not implemented for: {self}")

    @overload
    def upsert(
        self,
        record: RecordID | StringRecordId,
        data: Value | None = None,
        *,
        into: type[M],
    ) -> AsyncCrudBuilder[M]: ...
    @overload
    def upsert(
        self, record: Table, data: Value | None = None, *, into: type[M]
    ) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def upsert(
        self, record: str, data: Value | None = None, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M]]: ...
    @overload
    def upsert(
        self, record: RecordID | StringRecordId, data: Value | None = None
    ) -> AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value | None = None
    ) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(
        self, record: str, data: Value | None = None
    ) -> AsyncCrudBuilder[Value]: ...
    def upsert(
        self,
        record: RecordIdType,
        data: Value | None = None,
        *,
        into: type[M] | None = None,
    ) -> AsyncCrudBuilder[Any]:
        """Insert or update records.

        Returns an awaitable builder. Optional clause methods:
        ``.content(data)``, ``.replace(data)``, ``.merge(data)``, ``.patch(data)``.
        Pass ``into=Model`` to map the returned record(s) onto ``Model`` (a
        ``RecordID`` target resolves to ``Model``, a ``Table`` to ``list[Model]``).
        """
        raise NotImplementedError(f"upsert not implemented for: {self}")

    @overload
    def delete(
        self, record: RecordID | StringRecordId, *, into: type[M]
    ) -> AsyncCrudBuilder[M | None]: ...
    @overload
    def delete(self, record: Table, *, into: type[M]) -> AsyncCrudBuilder[list[M]]: ...
    @overload
    def delete(
        self, record: str, *, into: type[M]
    ) -> AsyncCrudBuilder[M | list[M] | None]: ...
    @overload
    def delete(
        self, record: RecordID | StringRecordId
    ) -> AsyncCrudBuilder[dict[str, Value] | None]: ...
    @overload
    def delete(self, record: Table) -> AsyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> AsyncCrudBuilder[Value]: ...
    def delete(
        self, record: RecordIdType, *, into: type[M] | None = None
    ) -> AsyncCrudBuilder[Any]:
        """Delete records.

        Returns an awaitable builder. A ``RecordID`` (or ``"table:id"``)
        resolves to the deleted record, or ``None`` when no record was
        deleted (matching select); a ``Table`` (or bare name) resolves to the
        list of deleted records. ``DELETE`` does not support clause methods.
        Pass ``into=Model`` to map the deleted record(s) onto ``Model``.
        """
        raise NotImplementedError(f"delete not implemented for: {self}")

    async def info(self) -> Value:
        """Return the record of the authenticated record user."""
        raise NotImplementedError(f"info not implemented for: {self}")

    @overload
    def insert(
        self, table: str | Table, data: Value | None = None, *, relation: bool = False
    ) -> AsyncInsertBuilder[Value]: ...
    @overload
    def insert(
        self,
        table: str | Table,
        data: Value | None = None,
        *,
        into: type[M],
        relation: bool = False,
    ) -> AsyncInsertBuilder[M]: ...
    def insert(
        self,
        table: str | Table,
        data: Value | None = None,
        *,
        into: type[M] | None = None,
        relation: bool = False,
    ) -> AsyncInsertBuilder[Any]:
        """Insert one or multiple records (or relations) into a table.

        Pass ``relation=True`` to issue ``INSERT RELATION INTO``, or chain
        ``.relation()`` on the returned builder. Pass ``into=Model`` to map the
        inserted records onto ``list[Model]``.

        Example:
            await db.insert(Table('person'), [{...}, {...}])
            await db.insert(Table('likes'), {...}, relation=True)
            await db.insert(Table('likes')).relation().content({...})
            await db.insert(Table('person'), [{...}], into=Person)
        """
        raise NotImplementedError(f"insert not implemented for: {self}")

    async def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        """Run a SurrealDB function and return its result.

        Args:
            name: Function name (e.g. ``"fn::increment"``).
            args: Positional arguments forwarded to the function.
            version: Optional function version selector.

        Example:
            await db.run('fn::increment', [1])
        """
        raise NotImplementedError(f"run not implemented for: {self}")

    async def live(
        self, table: str | Table, diff: bool = False
    ) -> AsyncLiveSubscription:
        """Initiate a live query on the given table.

        Args:
            table: The table name to listen for changes on.
            diff: If True, notifications include JSON Patch diffs rather than
                full records. Defaults to False.

        Returns:
            The live query UUID.
        """
        raise NotImplementedError(f"live not implemented for: {self}")

    async def subscribe_live(
        self, query_uuid: str | UUID
    ) -> AsyncGenerator[dict[str, Value], None]:
        """Iterate live notifications for the given live query id."""
        raise NotImplementedError(f"subscribe_live not implemented for: {self}")

    def live_of(self, live_id: str | UUID) -> AsyncLiveSubscription:
        """Attach to a live query started some other way, by its id."""
        raise NotImplementedError(f"live_of not implemented for: {self}")

    async def kill(self, query_uuid: str | UUID) -> None:
        """Kill a running live query by its UUID."""
        raise NotImplementedError(f"kill not implemented for: {self}")

    def relate(
        self,
        from_: RelateEnd,
        edge: RelateEdge,
        to: RelateEnd,
        data: Value = _UNSET,
    ) -> AsyncCrudBuilder[Any]:
        """Relate *from_* to *to* through *edge*: ``RELATE from->edge->to``."""
        raise NotImplementedError(f"relate not implemented for: {self}")
