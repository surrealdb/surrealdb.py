"""
Awaitable / lazy CRUD and query builders shared across all connection types.

The builders capture the operation state (target resource, optional clause,
data payload) and execute it through an injected ``executor`` callback.
This keeps wire-level concerns (session/transaction routing, websocket vs
http transport) in the connection classes while the SQL construction and
result extraction live in one place.

Async builders are awaitable - ``await db.create(...)`` runs the operation.
Sync builders implement magic methods so the returned object behaves like
the result it produces; clause methods on sync builders are *terminal* and
execute immediately, returning the underlying result. An explicit
``execute()`` method is also available for callers that want to be explicit.

Idempotency
-----------
Builders cache their result. Awaiting (or consuming) the same instance
twice runs the operation **once**:

- Async builders use an ``asyncio.Future`` so concurrent awaits all wait on
  the same in-flight operation rather than firing duplicate RPC calls.
- Sync builders use a simple ``_executed`` flag plus cached result.

In both cases ``query().into(MyResult)`` shares the cached fetch with the
parent ``query()`` builder, so ``await q.into(T)`` followed by ``await q``
issues only one server round-trip.

Safety
------
- ``__repr__`` and ``__str__`` on sync builders return a ``"<...pending>"``
  placeholder when the operation has not yet been triggered, so debuggers,
  loggers, or pytest introspection cannot accidentally execute a pending
  query / mutation.
- Plain ``str`` resource targets are bound through ``type::thing()`` /
  ``type::table()`` (parameterised) rather than concatenated into the SQL,
  guarding against the classic injection footgun where untrusted input
  flows into a record-id or table-name string.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import threading
from collections.abc import Awaitable, Callable, Generator, Iterator
from dataclasses import fields, is_dataclass
from typing import Any, Generic, TypeVar, cast

from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import (
    SurrealError,
    UnexpectedResponseError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.types import Value

T = TypeVar("T")
U = TypeVar("U")

AsyncExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
SyncExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Conservative identifier patterns. SurrealDB allows broader syntax (escaped
# identifiers ``⟨...⟩`` etc.) but we deliberately accept only the common safe
# subsets for inline use; anything else is parameter-bound through ``RecordID``
# / ``type::table()`` so user-supplied strings can never be concatenated into
# the generated SurrealQL.
_TABLE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Range syntax such as ``user:1..10`` or ``user:a..=z``. We require a
# safe-identifier table prefix and only permit alphanumerics, ``_`` and ``-``
# in the bound positions so the inline fallback path cannot smuggle in
# arbitrary SurrealQL.
_RANGE_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*"   # table identifier
    r":"
    r"[A-Za-z0-9_\-]*"           # optional start bound
    r"\.\.=?"                    # `..` or `..=`
    r"[A-Za-z0-9_\-]*$"          # optional end bound
)


def _string_to_record_id(s: str, var_name: str) -> RecordID:
    """Parse a ``"table:id"`` string into a :class:`RecordID`.

    Mirrors SurrealQL's parsing of bare record-id literals: a pure-digit id
    is coerced to ``int`` so ``"user:1234"`` and the inline literal
    ``user:1234`` resolve to the same record.

    Strings with more than one ``:`` are rejected because the partitioning
    rule (split on the first colon) cannot reliably round-trip with the
    server's literal-parsing rules for compound identifiers - the user
    should construct a :class:`RecordID` explicitly so the id type and
    encoding are unambiguous.
    """
    if s.count(":") != 1:
        raise SurrealError(
            f"Ambiguous record-id string {s!r} for resource '{var_name}': "
            "strings with more than one ':' cannot be safely parsed - pass "
            "an explicit RecordID instance instead."
        )
    table, _, ident = s.partition(":")
    if not table or not ident:
        raise SurrealError(
            f"Invalid record-id string {s!r} for resource '{var_name}'"
        )
    if ident.lstrip("-").isdigit():
        try:
            return RecordID(table, int(ident))
        except ValueError:  # pragma: no cover - defensive
            pass
    return RecordID(table, ident)


def _resource_to_variable(
    resource: RecordIdType, variables: dict[str, Any], var_name: str
) -> str:
    """Render *resource* as a variable reference inside generated SurrealQL.

    Parameter binding is used for every code path so user-supplied
    record-id or table-name strings cannot inject SurrealQL:

    - ``RecordID`` is bound directly as a CBOR-typed value.
    - ``Table`` is wrapped in ``type::table($var)`` so the table name is
      a parameter rather than concatenated into the SQL.
    - ``"table:id"`` strings are parsed client-side into a ``RecordID``
      (matching SurrealQL's bare-literal semantics) and bound directly.
    - Bare table-name strings (``"user"``) use ``type::table($var)``.
    - Range syntax (``"user:1..10"`` / ``"user:a..=z"``) is matched
      against a strict allow-list pattern and only then inlined - no
      runtime helper currently parses it for parameter binding.

    Anything that matches none of the above is rejected with
    :class:`SurrealError` rather than being concatenated into the SQL.
    """
    if isinstance(resource, RecordID):
        variables[var_name] = resource
        return f"${var_name}"

    if isinstance(resource, Table):
        variables[var_name] = resource.table_name
        return f"type::table(${var_name})"

    if ":" in resource and ".." not in resource:
        variables[var_name] = _string_to_record_id(resource, var_name)
        return f"${var_name}"

    if _TABLE_ID_PATTERN.match(resource):
        variables[var_name] = resource
        return f"type::table(${var_name})"

    if _RANGE_PATTERN.match(resource):
        # Strictly-validated range literal; inline is safe because the
        # allow-list excludes every SurrealQL meta-character.
        return resource

    raise SurrealError(
        f"Cannot use raw string {resource!r} as a SurrealDB resource target. "
        "Pass a RecordID, Table, or Range instance, or simplify the string "
        "to a bare identifier or 'table:id' form."
    )


def _is_single_record_operation(resource: RecordIdType) -> bool:
    if isinstance(resource, RecordID):
        return True
    if isinstance(resource, Table):
        return False
    if ":" in resource and ".." not in resource:
        return True
    return False


def _check_response(response: dict[str, Any], op_name: str) -> list[dict[str, Any]]:
    """Validate top-level response and return the list of statement results."""
    error = response.get("error")
    if error is not None:
        raise parse_rpc_error(error)
    if "result" not in response:
        raise SurrealError(f"no result {op_name}: {response}")
    result = response["result"]
    if not isinstance(result, list):
        raise UnexpectedResponseError(
            f"{op_name} expected list of statement results, got {type(result).__name__}"
        )
    return result


def _check_first_statement(stmts: list[dict[str, Any]]) -> Any:
    """Validate the first statement and return its ``result`` payload."""
    if not stmts:
        return None
    first = stmts[0]
    if first.get("status") == "ERR":
        raise parse_query_error(first)
    return first.get("result")


# ---------------------------------------------------------------------------
# Clause modes
# ---------------------------------------------------------------------------


class _Clause:
    DEFAULT = "default"
    CONTENT = "content"
    REPLACE = "replace"
    MERGE = "merge"
    PATCH = "patch"


# ---------------------------------------------------------------------------
# CRUD builder shared logic
# ---------------------------------------------------------------------------


class _CrudState:
    """Holds the configurable state for a CRUD builder."""

    def __init__(
        self,
        operation: str,
        record: RecordIdType,
        op_name: str,
        always_unwrap: bool,
    ) -> None:
        self._operation = operation
        self._record = record
        self._op_name = op_name
        self._always_unwrap = always_unwrap
        self._single = always_unwrap or _is_single_record_operation(record)
        self._mode: str = _Clause.DEFAULT
        self._data: Value | None = None

    def _check_not_executed(self) -> None:
        """Raise if this builder has already been executed.

        Subclasses override to consult their own execution state. The
        default no-op keeps :class:`_CrudState` usable on its own.
        """

    def _set_clause(self, mode: str, data: Value | None) -> None:
        self._check_not_executed()
        if self._operation == "DELETE":
            raise SurrealError(
                "DELETE does not support .content/.replace/.merge/.patch clauses"
            )
        self._mode = mode
        self._data = data

    def _build(self) -> tuple[str, dict[str, Any]]:
        variables: dict[str, Any] = {}
        resource_ref = _resource_to_variable(self._record, variables, "_resource")

        if self._operation == "DELETE":
            return f"DELETE {resource_ref} RETURN BEFORE", variables

        op = self._operation
        if self._mode == _Clause.DEFAULT:
            return f"{op} {resource_ref}", variables
        if self._mode == _Clause.CONTENT:
            variables["_content"] = self._data
            return f"{op} {resource_ref} CONTENT $_content", variables
        if self._mode == _Clause.REPLACE:
            variables["_data"] = self._data
            return f"{op} {resource_ref} REPLACE $_data", variables
        if self._mode == _Clause.MERGE:
            variables["_data"] = self._data if self._data is not None else {}
            return f"{op} {resource_ref} MERGE $_data", variables
        if self._mode == _Clause.PATCH:
            variables["_patches"] = self._data if self._data is not None else []
            return f"{op} {resource_ref} PATCH $_patches", variables
        raise SurrealError(f"unknown clause mode: {self._mode}")

    def _extract(self, response: dict[str, Any]) -> Any:
        stmts = _check_response(response, self._op_name)
        result = _check_first_statement(stmts)
        if self._single and isinstance(result, list) and len(result) == 1:
            return result[0]
        return result


class _InsertState:
    """State for INSERT builder."""

    def __init__(
        self,
        table: str | Table,
        data: Value | None,
        relation: bool,
    ) -> None:
        if isinstance(table, RecordID):
            raise SurrealError(
                "There was a problem with the database: Can not execute "
                f"INSERT statement using value '{table}'"
            )
        self._table = table
        self._data = data
        self._relation = relation

    def _check_not_executed(self) -> None:
        """Subclasses override to consult their own execution state."""

    def _build(self) -> tuple[str, dict[str, Any]]:
        if self._data is None:
            raise SurrealError(
                "INSERT requires data; pass via insert(table, data) or .content(data)"
            )
        # INSERT does not accept `type::table(...)` or arbitrary parameter
        # binding for its target across all SurrealDB versions, so we
        # validate the table name strictly client-side and only inline
        # values matching the safe identifier pattern. Anything else is
        # rejected up-front rather than risking SQL injection.
        if isinstance(self._table, Table):
            table_name: str = self._table.table_name
        else:
            table_name = self._table
        if not _TABLE_ID_PATTERN.match(table_name):
            raise SurrealError(
                f"INSERT requires a simple identifier for the target table "
                f"(got {table_name!r}). Use query_raw() for non-trivial cases."
            )
        variables: dict[str, Any] = {"_data": self._data}
        rel = "RELATION " if self._relation else ""
        return f"INSERT {rel}INTO {table_name} $_data", variables

    def _extract(self, response: dict[str, Any]) -> Any:
        op_name = "insert_relation" if self._relation else "insert"
        stmts = _check_response(response, op_name)
        return _check_first_statement(stmts)


class _QueryState:
    """State for query builder."""

    def __init__(self, query: str, variables: dict[str, Value] | None) -> None:
        self._query = query
        self._variables: dict[str, Any] = dict(variables) if variables else {}

    def _statement_values(self, response: dict[str, Any]) -> list[Any]:
        stmts = _check_response(response, "query")
        for stmt in stmts:
            if stmt.get("status") == "ERR":
                raise parse_query_error(stmt)
        return [stmt.get("result") for stmt in stmts]


def _map_to_class(cls: type[T], values: list[Any]) -> T:
    """Map the N statement results positionally onto the fields of ``cls``."""
    if is_dataclass(cls):
        field_list = list(fields(cls))
        if len(field_list) != len(values):
            raise UnexpectedResponseError(
                f"query().into({cls.__name__}) expects {len(field_list)} statement "
                f"results to match dataclass fields, got {len(values)}"
            )
        kwargs = {f.name: v for f, v in zip(field_list, values, strict=True)}
        return cls(**kwargs)  # type: ignore[return-value]

    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError) as exc:
        raise UnexpectedResponseError(
            f"query().into({cls.__name__}) cannot inspect constructor: {exc}"
        ) from exc

    accepted = (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )
    param_names = [
        name
        for name, param in sig.parameters.items()
        if name != "self" and param.kind in accepted
    ]
    if len(param_names) != len(values):
        raise UnexpectedResponseError(
            f"query().into({cls.__name__}) expects {len(param_names)} statement "
            f"results to match constructor parameters, got {len(values)}"
        )
    kwargs = {name: value for name, value in zip(param_names, values, strict=True)}
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Async idempotent execution helpers
# ---------------------------------------------------------------------------


def _suppress_unretrieved_exception(future: asyncio.Future) -> None:
    """``add_done_callback`` helper that pre-reads ``exception()``.

    This prevents asyncio from logging "Future exception was never
    retrieved" when an idempotent builder fails on its first await and
    no further task ever awaits the cached future. Real awaiters still
    receive the exception via ``await future``.
    """
    if not future.cancelled():
        future.exception()


class _AsyncCachedRunner:
    """Future-based "run once" cache for async builders.

    The first call to :meth:`run` schedules the wrapped coroutine and caches
    the resulting :class:`asyncio.Future`. Subsequent calls (including
    concurrent ones) await the same future, so we issue exactly one RPC
    regardless of how many times the builder is awaited or how many tasks
    consume it.

    Cancellation:
        If the *initiating* awaiter is cancelled while the operation is
        still in flight, we deliberately do **not** propagate
        :class:`asyncio.CancelledError` onto the shared future - other
        awaiters did not request cancellation and shouldn't see phantom
        cancellation semantics. Instead the runner resets its cache so a
        subsequent call retries from scratch, and any awaiters already
        blocked on the original future receive a
        :class:`SurrealError` explaining what happened.
    """

    def __init__(self) -> None:
        self._future: asyncio.Future[Any] | None = None

    async def run(self, coro_factory: Callable[[], Awaitable[Any]]) -> Any:
        if self._future is not None:
            return await self._future

        loop = asyncio.get_running_loop()
        active = loop.create_future()
        self._future = active
        # Pre-consume any exception so a discarded failed builder does not
        # trip asyncio's "Future exception was never retrieved" warning.
        active.add_done_callback(_suppress_unretrieved_exception)
        try:
            value = await coro_factory()
        except asyncio.CancelledError:
            # Cancellation belongs to the initiating awaiter only.
            if not active.done():
                active.set_exception(
                    SurrealError(
                        "Cached async builder operation was cancelled by its "
                        "initiating awaiter; please retry."
                    )
                )
            # Reset so subsequent (uncancelled) callers can retry cleanly.
            if self._future is active:
                self._future = None
            raise
        except BaseException as exc:
            if not active.done():
                active.set_exception(exc)
            raise
        else:
            if not active.done():
                active.set_result(value)
            return value


# ---------------------------------------------------------------------------
# Async builders
# ---------------------------------------------------------------------------


class _AsyncCrudBuilder(_CrudState, Generic[T]):
    """Awaitable CRUD builder for async connections.

    Awaiting the same builder twice (or from concurrent tasks) only issues
    one RPC; the cached result is returned thereafter. Re-configuring the
    builder *after* it has executed (calling another clause method)
    raises - cached results would otherwise silently mask the new clause.
    """

    def __init__(
        self,
        executor: AsyncExecutor,
        operation: str,
        record: RecordIdType,
        op_name: str,
        data: Value | None = None,
        always_unwrap: bool = False,
    ) -> None:
        super().__init__(operation, record, op_name, always_unwrap)
        self._executor = executor
        self._runner = _AsyncCachedRunner()
        if data is not None:
            self._mode = _Clause.CONTENT
            self._data = data

    def _check_not_executed(self) -> None:
        if self._runner._future is not None:
            raise SurrealError(
                f"Cannot reconfigure a {self.__class__.__name__} after it has "
                "executed. Create a new builder for a fresh operation."
            )

    def content(self, data: Value) -> "_AsyncCrudBuilder[T]":
        self._set_clause(_Clause.CONTENT, data)
        return self

    def replace(self, data: Value) -> "_AsyncCrudBuilder[T]":
        self._set_clause(_Clause.REPLACE, data)
        return self

    def merge(self, data: Value) -> "_AsyncCrudBuilder[T]":
        self._set_clause(_Clause.MERGE, data)
        return self

    def patch(self, data: Value) -> "_AsyncCrudBuilder[T]":
        self._set_clause(_Clause.PATCH, data)
        return self

    async def _do_execute(self) -> T:
        query, variables = self._build()
        response = await self._executor(query, variables)
        return cast(T, self._extract(response))

    async def execute(self) -> T:
        return cast(T, await self._runner.run(self._do_execute))

    def __await__(self) -> Generator[Any, None, T]:
        return self.execute().__await__()


class _AsyncInsertBuilder(_InsertState):
    """Awaitable INSERT builder for async connections (idempotent).

    Re-configuring the builder *after* it has executed raises rather than
    silently returning the cached result.
    """

    def __init__(
        self,
        executor: AsyncExecutor,
        table: str | Table,
        data: Value | None = None,
        relation: bool = False,
    ) -> None:
        super().__init__(table, data, relation)
        self._executor = executor
        self._runner = _AsyncCachedRunner()

    def _check_not_executed(self) -> None:
        if self._runner._future is not None:
            raise SurrealError(
                f"Cannot reconfigure a {self.__class__.__name__} after it has "
                "executed. Create a new builder for a fresh operation."
            )

    def relation(self) -> "_AsyncInsertBuilder":
        self._check_not_executed()
        self._relation = True
        return self

    def content(self, data: Value) -> "_AsyncInsertBuilder":
        self._check_not_executed()
        self._data = data
        return self

    async def _do_execute(self) -> list[Value]:
        query, variables = self._build()
        response = await self._executor(query, variables)
        return cast(list[Value], self._extract(response))

    async def execute(self) -> list[Value]:
        return cast(list[Value], await self._runner.run(self._do_execute))

    def __await__(self) -> Generator[Any, None, list[Value]]:
        return self.execute().__await__()


class _AsyncQueryBuilder(_QueryState):
    """Awaitable QUERY builder for async connections.

    Returns a single Value when the server returned exactly one statement
    result, otherwise a tuple of all statement results (fixes the historic
    silent-discard behaviour - GH issue #232).

    Idempotent: the underlying RPC fires once, and ``.into(cls)`` shares
    the same cached fetch.
    """

    def __init__(
        self,
        executor: AsyncExecutor,
        query: str,
        variables: dict[str, Value] | None = None,
    ) -> None:
        super().__init__(query, variables)
        self._executor = executor
        self._runner = _AsyncCachedRunner()

    async def _fetch_values(self) -> list[Any]:
        async def _do() -> list[Any]:
            response = await self._executor(self._query, self._variables)
            return self._statement_values(response)

        return cast(list[Any], await self._runner.run(_do))

    def into(self, cls: type[U]) -> "_AsyncQueryIntoBuilder[U]":
        # Hand the into-builder a reference to *self* so it reuses the
        # already-fetched (or about-to-be-fetched) values rather than
        # issuing a second RPC.
        return _AsyncQueryIntoBuilder(self, cls)

    async def execute(self) -> Value | tuple[Value, ...]:
        values = await self._fetch_values()
        if len(values) == 1:
            return values[0]
        return tuple(values)

    def __await__(self) -> Generator[Any, None, Value | tuple[Value, ...]]:
        return self.execute().__await__()


class _AsyncQueryIntoBuilder(Generic[T]):
    """Async query builder that maps results onto a user-supplied class.

    Reuses the parent :class:`_AsyncQueryBuilder`'s cached fetch so that
    ``await q`` and ``await q.into(T)`` together still only round-trip
    once.
    """

    def __init__(self, parent: _AsyncQueryBuilder, cls: type[T]) -> None:
        self._parent = parent
        self._cls = cls

    async def execute(self) -> T:
        values = await self._parent._fetch_values()
        return _map_to_class(self._cls, values)

    def __await__(self) -> Generator[Any, None, T]:
        return self.execute().__await__()


# ---------------------------------------------------------------------------
# Sync builders
# ---------------------------------------------------------------------------


class _SyncBuilderMixin:
    """Magic methods that auto-execute the builder when used as a result.

    Subclasses must define ``_run_once()`` returning the cached result and
    a ``_lock: threading.Lock`` attribute. Subclasses' ``_run_once()``
    implementations must acquire ``self._lock`` around their cache check
    so two threads consuming the same builder don't issue duplicate RPCs
    or corrupt cached state.

    Builders are *lazy* — the operation only runs when you ask for the
    result. The methods that auto-execute are:

    - ``__getitem__`` (``builder[key]``)
    - ``__iter__`` (``for x in builder``)
    - ``__len__`` (``len(builder)``)
    - ``__contains__`` (``x in builder``)
    - ``__eq__`` / ``__ne__`` (``builder == other``)
    - ``__bool__`` (``if builder:`` or ``not builder``)
    - ``__getattr__`` (any unknown attribute lookup)

    .. warning::

        ``__bool__`` and ``__eq__`` mean that **any** truthiness check or
        comparison fires the operation, including idioms like
        ``if db.query("DELETE foo;"): ...`` or
        ``assert db.create(...)``. If you don't intend to consume the
        result, call ``.execute()`` explicitly (for fire-and-forget) or
        bind the builder to a name and only access it conditionally.

    ``__repr__`` / ``__str__`` deliberately do **not** trigger execution -
    they return a ``"<...pending>"`` placeholder when the builder has not
    yet been run. This keeps loggers, debuggers, and test introspection
    from accidentally firing pending queries.

    Thread safety:
        ``_run_once()`` is guarded by a per-builder lock so that
        consuming the same builder from multiple threads issues exactly
        one RPC. The builder is **not** safe for concurrent
        *reconfiguration* across threads though - calling ``.merge()``
        on one thread while another consumes the result is a race on
        ``_mode`` / ``_data`` that the lock does not cover. Treat
        builders as single-shot, single-owner values; pass the realised
        result between threads, not the builder itself.
    """

    _executed: bool
    _cached_result: Any
    _lock: threading.Lock

    def _run_once(self) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError

    def __getitem__(self, key: Any) -> Any:
        return self._run_once()[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._run_once())

    def __len__(self) -> int:
        return len(self._run_once())

    def __contains__(self, item: Any) -> bool:
        return item in self._run_once()

    def __eq__(self, other: object) -> bool:
        return bool(self._run_once() == other)

    def __ne__(self, other: object) -> bool:
        return bool(self._run_once() != other)

    def __bool__(self) -> bool:
        return bool(self._run_once())

    def __repr__(self) -> str:
        if self._executed:
            return repr(self._cached_result)
        return f"<{self.__class__.__name__} pending - call .execute() or consume to run>"

    def __str__(self) -> str:
        if self._executed:
            return str(self._cached_result)
        return self.__repr__()

    def __getattr__(self, name: str) -> Any:
        # __getattr__ is only invoked when the attribute is missing on the
        # instance. Internal attributes start with ``_`` and are always set
        # in __init__ so we never reach here for them.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._run_once(), name)


class _SyncCrudBuilder(_CrudState, _SyncBuilderMixin, Generic[T]):
    """Lazy CRUD builder for sync connections.

    Important - sync vs async difference:

    - On **async** connections the clause methods (``content`` / ``replace``
      / ``merge`` / ``patch``) return ``self`` so the builder remains
      awaitable: ``await db.create(rec).merge({"x": 1})``.
    - On **sync** connections the clause methods are **terminal**: they run
      the operation immediately and return the result value. There is no
      sync ``await`` to defer execution to, so chaining further would have
      no effect.

    For the no-clause case (plain ``db.create(record)``) the sync builder
    is lazy and only runs once the result is consumed (indexed, iterated,
    compared, etc.) or ``.execute()`` is called explicitly. Repeat consumes
    return the same cached result; calling another clause method after the
    builder has executed raises rather than silently returning the stale
    result.
    """

    def __init__(
        self,
        executor: SyncExecutor,
        operation: str,
        record: RecordIdType,
        op_name: str,
        data: Value | None = None,
        always_unwrap: bool = False,
    ) -> None:
        super().__init__(operation, record, op_name, always_unwrap)
        self._executor = executor
        self._executed = False
        self._cached_result: Any = None
        self._lock = threading.Lock()
        if data is not None:
            self._mode = _Clause.CONTENT
            self._data = data

    def _check_not_executed(self) -> None:
        if self._executed:
            raise SurrealError(
                f"Cannot reconfigure a {self.__class__.__name__} after it has "
                "executed. Create a new builder for a fresh operation."
            )

    def content(self, data: Value) -> T:
        self._set_clause(_Clause.CONTENT, data)
        return cast(T, self._run_once())

    def replace(self, data: Value) -> T:
        self._set_clause(_Clause.REPLACE, data)
        return cast(T, self._run_once())

    def merge(self, data: Value) -> T:
        self._set_clause(_Clause.MERGE, data)
        return cast(T, self._run_once())

    def patch(self, data: Value) -> T:
        self._set_clause(_Clause.PATCH, data)
        return cast(T, self._run_once())

    def execute(self) -> T:
        return cast(T, self._run_once())

    def _run_once(self) -> Any:
        with self._lock:
            if not self._executed:
                query, variables = self._build()
                response = self._executor(query, variables)
                self._cached_result = self._extract(response)
                self._executed = True
            return self._cached_result


class _SyncInsertBuilder(_InsertState, _SyncBuilderMixin):
    """Lazy INSERT builder for sync connections (idempotent).

    Reconfiguring the builder *after* it has executed raises rather than
    silently returning the cached result.
    """

    def __init__(
        self,
        executor: SyncExecutor,
        table: str | Table,
        data: Value | None = None,
        relation: bool = False,
    ) -> None:
        super().__init__(table, data, relation)
        self._executor = executor
        self._executed = False
        self._cached_result: Any = None
        self._lock = threading.Lock()

    def _check_not_executed(self) -> None:
        if self._executed:
            raise SurrealError(
                f"Cannot reconfigure a {self.__class__.__name__} after it has "
                "executed. Create a new builder for a fresh operation."
            )

    def relation(self) -> "_SyncInsertBuilder":
        self._check_not_executed()
        self._relation = True
        return self

    def content(self, data: Value) -> list[Value]:
        self._check_not_executed()
        self._data = data
        return cast(list[Value], self._run_once())

    def execute(self) -> list[Value]:
        return cast(list[Value], self._run_once())

    def _run_once(self) -> Any:
        with self._lock:
            if not self._executed:
                query, variables = self._build()
                response = self._executor(query, variables)
                self._cached_result = self._extract(response)
                self._executed = True
            return self._cached_result


class _SyncQueryBuilder(_QueryState, _SyncBuilderMixin):
    """Lazy QUERY builder for sync connections.

    Idempotent: ``.execute()``, magic-method consumption, and
    ``.into(cls)`` all share a single cached fetch and update
    ``_executed`` consistently, so ``repr(builder)`` after any of them
    no longer shows ``"pending"``.
    """

    def __init__(
        self,
        executor: SyncExecutor,
        query: str,
        variables: dict[str, Value] | None = None,
    ) -> None:
        super().__init__(query, variables)
        self._executor = executor
        self._executed = False
        self._cached_result: Any = None
        self._cached_values: list[Any] | None = None
        self._lock = threading.Lock()

    def into(self, cls: type[T]) -> T:
        # Reuse this builder's cached fetch so `await q` plus `q.into(T)`
        # on the same instance only issues one RPC. Going through
        # ``_run_once`` (rather than ``_fetch_values`` directly) keeps
        # ``_executed`` and ``_cached_result`` in lockstep so subsequent
        # ``repr(builder)`` shows the real result, not "pending".
        self._run_once()
        assert self._cached_values is not None  # set by _run_once
        return _map_to_class(cls, self._cached_values)

    def execute(self) -> Value | tuple[Value, ...]:
        return cast("Value | tuple[Value, ...]", self._run_once())

    def _run_once(self) -> Any:
        with self._lock:
            if not self._executed:
                response = self._executor(self._query, self._variables)
                values = self._statement_values(response)
                self._cached_values = values
                if len(values) == 1:
                    self._cached_result = values[0]
                else:
                    self._cached_result = tuple(values)
                self._executed = True
            return self._cached_result


__all__ = [
    "_AsyncCrudBuilder",
    "_AsyncInsertBuilder",
    "_AsyncQueryBuilder",
    "_AsyncQueryIntoBuilder",
    "_SyncCrudBuilder",
    "_SyncInsertBuilder",
    "_SyncQueryBuilder",
]
