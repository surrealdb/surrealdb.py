from collections.abc import AsyncGenerator
from typing import overload
from uuid import UUID

from surrealdb.connections.builders import (
    _AsyncCrudBuilder,
    _AsyncInsertBuilder,
    _AsyncQueryBuilder,
)
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.types import Tokens, Value


class AsyncTemplate:
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

    async def use(self, namespace: str, database: str) -> None:
        """Switch to a specific namespace and database.

        Args:
            namespace: Switches to a specific namespace.
            database: Switches to a specific database.

        Example:
            await db.use('test', 'test')
        """
        raise NotImplementedError(f"use not implemented for: {self}")

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

    async def unset(self, key: str) -> None:
        """Removes a variable for this connection.

        Args:
            key: Specifies the name of the variable.
        """
        raise NotImplementedError(f"unset not implemented for: {self}")

    def query(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> _AsyncQueryBuilder:
        """Run one or more SurrealQL statements against the database.

        Returns an awaitable builder. Awaiting the builder returns:

        - The result Value when the server returned exactly one statement result
        - A ``tuple[Value, ...]`` of all statement results when N>1 statements ran
          (this is the v3.0 fix for issue #232 - earlier versions silently
          dropped every result after the first).

        Use ``.into(MyResult)`` to map the N statement results positionally onto
        a dataclass or any class accepting keyword arguments.

        Args:
            query: SurrealQL statement(s).
            vars: Variables referenced in the query.

        Example:
            single = await db.query('SELECT * FROM person')
            many = await db.query('SELECT * FROM person; SELECT count() FROM person GROUP ALL')
            mapped = await db.query('CREATE ...; SELECT ...').into(MyResult)
        """
        raise NotImplementedError(f"query not implemented for: {self}")

    async def select(self, record: RecordIdType) -> Value:
        """Select all records in a table or a specific record.

        Args:
            record: The table or record ID to select.
        """
        raise NotImplementedError(f"select not implemented for: {self}")

    @overload
    def create(
        self, record: RecordID, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self, record: RecordIdType, data: Value | None = None
    ) -> _AsyncCrudBuilder:
        """Create a record.

        Returns an awaitable builder. Optional clause methods:

        - ``.content(data)``  -> ``CREATE ... CONTENT $data``
        - ``.replace(data)``  -> ``CREATE ... REPLACE $data``
        - ``.merge(data)``    -> ``CREATE ... MERGE $data``
        - ``.patch(data)``    -> ``CREATE ... PATCH $data``

        ``db.create(record, data)`` is sugar for ``db.create(record).content(data)``.

        Example:
            await db.create(RecordID('person', 'tobie'), {'name': 'Tobie'})
            await db.create(RecordID('person', 'tobie')).merge({'name': 'Tobie'})
        """
        raise NotImplementedError(f"create not implemented for: {self}")

    @overload
    def update(
        self, record: RecordID, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value | None = None
    ) -> _AsyncCrudBuilder[list[Value]]: ...
    @overload
    def update(
        self, record: str, data: Value | None = None
    ) -> _AsyncCrudBuilder[Value]: ...
    def update(
        self, record: RecordIdType, data: Value | None = None
    ) -> _AsyncCrudBuilder:
        """Update records (replacing the existing data by default).

        Returns an awaitable builder. Optional clause methods:
        ``.content(data)``, ``.replace(data)``, ``.merge(data)``, ``.patch(data)``.
        """
        raise NotImplementedError(f"update not implemented for: {self}")

    @overload
    def upsert(
        self, record: RecordID, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value | None = None
    ) -> _AsyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(
        self, record: str, data: Value | None = None
    ) -> _AsyncCrudBuilder[Value]: ...
    def upsert(
        self, record: RecordIdType, data: Value | None = None
    ) -> _AsyncCrudBuilder:
        """Insert or update records.

        Returns an awaitable builder. Optional clause methods:
        ``.content(data)``, ``.replace(data)``, ``.merge(data)``, ``.patch(data)``.
        """
        raise NotImplementedError(f"upsert not implemented for: {self}")

    @overload
    def delete(self, record: RecordID) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def delete(self, record: Table) -> _AsyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> _AsyncCrudBuilder[Value]: ...
    def delete(self, record: RecordIdType) -> _AsyncCrudBuilder:
        """Delete records.

        Returns an awaitable builder. ``DELETE`` does not support clause methods.
        """
        raise NotImplementedError(f"delete not implemented for: {self}")

    async def info(self) -> Value:
        """Return the record of the authenticated record user."""
        raise NotImplementedError(f"info not implemented for: {self}")

    def insert(
        self,
        table: str | Table,
        data: Value | None = None,
        *,
        relation: bool = False,
    ) -> _AsyncInsertBuilder:
        """Insert one or multiple records (or relations) into a table.

        Pass ``relation=True`` to issue ``INSERT RELATION INTO``, or chain
        ``.relation()`` on the returned builder.

        Example:
            await db.insert(Table('person'), [{...}, {...}])
            await db.insert(Table('likes'), {...}, relation=True)
            await db.insert(Table('likes')).relation().content({...})
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

    async def live(self, table: str | Table, diff: bool = False) -> UUID:
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

    async def kill(self, query_uuid: str | UUID) -> None:
        """Kill a running live query by its UUID."""
        raise NotImplementedError(f"kill not implemented for: {self}")
