"""
Awaitable / eager CRUD and query builders shared across all connection types.

The builders capture the operation state (target resource, optional clause,
data payload) and execute it through an injected ``executor`` callback.
This keeps wire-level concerns (session/transaction routing, websocket vs
http transport) in the connection classes while the SQL construction and
result extraction live in one place.

Async vs sync
-------------
- **Async** builders are awaitable - ``await db.create(...)`` runs the
  operation. Their clause methods (``.content`` / ``.replace`` / ``.merge``
  / ``.patch``) return ``self`` so the builder stays awaitable, and the RPC
  only fires on ``await`` / ``.execute()``.
- **Sync** builders are *eager*: there is no ``await`` to defer execution to,
  so the sync connection methods run single-shot operations immediately and
  hand back the plain result. A sync builder is only returned for the
  deferred forms - ``db.create(record)`` with no data, or ``db.insert(table)``
  with no data - and every terminal method on it (``.content`` / ``.replace``
  / ``.merge`` / ``.patch`` / ``.relation().content(...)`` / ``.execute()``)
  runs the operation and returns the underlying result. Sync builders carry
  **no** magic dunders: they never auto-execute on ``bool()``, ``==``,
  indexing, iteration, or attribute access.

Idempotency (async only)
------------------------
Async builders cache their result: awaiting the same instance twice (or from
concurrent tasks) runs the operation **once** via an ``asyncio.Future`` so
concurrent awaits all wait on the same in-flight operation rather than firing
duplicate RPC calls. ``query().into(MyResult)`` shares the cached fetch with
the parent ``query()`` builder, so ``await q.into(T)`` followed by ``await q``
issues only one server round-trip. Sync builders keep a simple ``_executed``
flag + lock so an explicit ``.execute()`` after a terminal clause returns the
cached result rather than re-issuing the RPC.

query() always returns a sequence
---------------------------------
Both :class:`AsyncQueryBuilder` and :class:`SyncQueryBuilder` return
``list[Value]`` - one entry per statement - even for a single statement
(fixes the historic silent-discard behaviour, GH issue #232). Use
``.first()`` to pull the first statement's result, or ``.into(cls)`` to map
the N statement results positionally onto a dataclass / class.
``.into(cls, rows=True)`` instead maps each ROW of the single statement
result onto ``cls`` and returns ``list[cls]``.

Safety
------
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
from collections.abc import Awaitable, Callable, Generator, Mapping
from dataclasses import fields, is_dataclass
from typing import Any, Generic, Literal, TypeVar, cast, overload

from surrealdb.data.types.record_id import RecordID, RecordIdType, escape_identifier
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
# Covariant output type for ``AsyncQueryIntoBuilder`` - ``T_co`` only ever
# appears in return position (``execute`` / ``__await__``), so covariance is
# sound and lets the ``.into(..., rows=...)`` overloads (whose returns are
# ``Builder[U]`` vs ``Builder[U | list[U]]``) type-check without overlap
# conflicts (an invariant generic would reject the narrowing).
T_co = TypeVar("T_co", covariant=True)
# Row-model type variable for the ``into=`` mapping surface. ``M`` binds the
# user's model class so ``select``/``create``/``query().into(..., rows=True)``
# return precisely typed model instances (``M`` / ``list[M]`` / ``M | None``)
# rather than the raw ``dict`` / ``list[Value]`` shapes.
M = TypeVar("M")

AsyncExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
SyncExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]

# Sentinel marking "no data argument was supplied". The eager sync CRUD
# methods must distinguish ``db.create(rec)`` (defer - return a builder) from
# ``db.create(rec, None)`` (execute eagerly with ``CONTENT NULL``). ``None`` is
# a valid ``Value`` so it cannot double as the "absent" marker. Typed as
# ``Any`` so it is accepted as the default of a ``data: Value`` parameter
# without widening the public signature to ``Value | None``.
_UNSET: Any = object()


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
    r"^[A-Za-z_][A-Za-z0-9_]*"  # table identifier
    r":"
    r"[A-Za-z0-9_\-]*"  # optional start bound
    r"\.\.=?"  # `..` or `..=`
    r"[A-Za-z0-9_\-]*$"  # optional end bound
)


def _string_to_record_id(s: str, var_name: str) -> RecordID:
    """Parse a ``"table:id"`` string into a :class:`RecordID`.

    Mirrors SurrealQL's parsing of bare record-id literals: a non-negative
    pure-digit id is coerced to ``int`` so ``"user:1234"`` and the inline
    literal ``user:1234`` resolve to the same record. Negative numeric ids
    fall through to the string-id branch - the SurrealQL literal parser's
    semantics for negative ints are version-dependent, so we don't guess;
    pass an explicit ``RecordID(table, -5)`` if you need an int id.

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
        raise SurrealError(f"Invalid record-id string {s!r} for resource '{var_name}'")
    # Both checks matter: ``str.isdigit()`` returns True for unicode
    # digits like ``"²"`` which would round-trip through ``int()`` for
    # most but not all unicode digit forms; restricting to ASCII digits
    # keeps the coercion predictable and matches SurrealQL's bare-int
    # literal grammar.
    if ident.isascii() and ident.isdigit():
        return RecordID(table, int(ident))
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
        into: type[Any] | None = None,
    ) -> None:
        self._operation = operation
        self._record = record
        self._op_name = op_name
        self._always_unwrap = always_unwrap
        self._single = always_unwrap or _is_single_record_operation(record)
        self._mode: str = _Clause.DEFAULT
        self._data: Value | None = None
        # Optional row-model class. When set, the extracted result is mapped
        # through ``_map_result`` (which delegates to ``_map_to_class``) before
        # being returned, so ``into=Model`` yields ``Model`` / ``list[Model]``.
        self._into: type[Any] | None = into

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
        if self._single and isinstance(result, list):
            # Single-record DELETE aligns with select's absent-record
            # handling: an empty result (no record was deleted) unwraps to
            # None, otherwise the deleted record dict. Other single-record
            # operations only unwrap the one-element list they produce.
            if self._operation == "DELETE":
                return result[0] if result else None
            if len(result) == 1:
                return result[0]
        return result


class _InsertState:
    """State for INSERT builder."""

    def __init__(
        self,
        table: str | Table,
        data: Value | None,
        relation: bool,
        into: type[Any] | None = None,
    ) -> None:
        if isinstance(table, RecordID):
            raise SurrealError(
                "There was a problem with the database: Can not execute "
                f"INSERT statement using value '{table}'"
            )
        self._table = table
        self._data = data
        self._relation = relation
        # Optional row-model class; when set the inserted records are mapped
        # element-wise through ``_map_to_class`` into ``list[into]``.
        self._into: type[Any] | None = into

    def _check_not_executed(self) -> None:
        """Subclasses override to consult their own execution state."""

    def _build(self) -> tuple[str, dict[str, Any]]:
        if self._data is None:
            raise SurrealError(
                "INSERT requires data; pass via insert(table, data) or .content(data)"
            )
        variables: dict[str, Any] = {"_data": self._data}
        rel = "RELATION " if self._relation else ""
        # SurrealDB does not accept ``type::table(...)`` (or any parameter
        # binding) for the INSERT target across the supported server
        # versions - the parser rejects ``INSERT INTO type::table($x)`` at
        # the ``::``. So we inline the table name, but for ``Table`` we
        # trust the typed boundary and use the same ``⟨...⟩`` escape as
        # ``RecordID.__str__`` to safely pass through hyphens, spaces, and
        # other non-ASCII-identifier characters (any ``⟩`` inside the name
        # is escaped as ``\⟩``).
        if isinstance(self._table, Table):
            escaped = escape_identifier(self._table.table_name)
            return f"INSERT {rel}INTO {escaped} $_data", variables
        # Raw string: keep the strict identifier check so user-supplied
        # strings can never be concatenated into SurrealQL. Point users
        # at ``Table(...)`` for non-trivial names rather than risking
        # round-tripping unknown escape rules.
        if not _TABLE_ID_PATTERN.match(self._table):
            raise SurrealError(
                f"INSERT requires a simple identifier for a raw string target "
                f"(got {self._table!r}). Wrap the name in `Table(...)` for "
                "non-trivial names, or use `query()` with an escaped "
                "identifier `INSERT INTO ⟨...⟩ $data`."
            )
        return f"INSERT {rel}INTO {self._table} $_data", variables

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


def _map_to_class(cls: type[T], values: list[Any] | Mapping[str, Any]) -> T:
    """Construct ``cls`` from statement results or a single record row.

    Two calling conventions share this one kwargs-construction helper:

    - A ``Mapping`` (a single record dict, as produced by ``select`` /
      ``create`` / ``query().into(cls, rows=True)`` with ``into=``) is expanded
      straight into keyword arguments - ``cls(**row)``. This covers
      dataclasses, pydantic ``BaseModel``, and any class whose constructor
      accepts the record's fields as keywords.
    - A ``list`` (the N statement results from ``query().into(cls)``) is mapped
      positionally onto the fields / constructor parameters of ``cls`` - the
      historic ``into(cls)`` behaviour, unchanged.
    """
    if isinstance(values, Mapping):
        # Row -> model: the record's keys are the constructor kwargs. Works
        # uniformly for dataclasses, pydantic models, and plain classes.
        return cls(**values)

    if is_dataclass(cls):
        field_list = list(fields(cls))
        if len(field_list) != len(values):
            raise UnexpectedResponseError(
                f"query().into({cls.__name__}) expects {len(field_list)} statement "
                f"results to match dataclass fields, got {len(values)}"
            )
        kwargs = {f.name: v for f, v in zip(field_list, values, strict=True)}
        return cls(**kwargs)

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


def _statement_rows(values: list[Any]) -> list[Any]:
    """Return the rows of the first statement result for row-mapping.

    ``query(sql).into(cls, rows=True)`` maps each ROW of a single statement's
    result. The query builder yields one entry per statement, so row-mapping
    uses the first statement's result (the common single-``SELECT`` case):

    - a ``list`` result is returned as-is (its elements are the rows),
    - a scalar / single record is wrapped as a one-row list,
    - ``None`` (or no statements at all) yields ``[]``.
    """
    if not values:
        return []
    first = values[0]
    if isinstance(first, list):
        return first
    if first is None:
        return []
    return [first]


def _map_result(into: type[Any] | None, result: Any) -> Any:
    """Map an extracted ``select`` / CRUD result onto ``into`` by runtime shape.

    ``into`` is a model class (dataclass, pydantic ``BaseModel``, or any
    kwargs-constructible class). Mapping follows the shape the operation
    already produced so the static ``@overload`` return type and the runtime
    value stay in lock-step:

    - a ``list`` maps element-wise to ``list[into]`` (``Table`` targets),
    - ``None`` stays ``None`` (an absent single record),
    - anything else (a record dict) maps to a single ``into`` instance.

    Construction goes through :func:`_map_to_class`, the shared kwargs mapper -
    there is deliberately no parallel row mapper. ``into=None`` returns the
    result untouched, so the no-``into`` path is byte-for-byte unchanged.
    """
    if into is None:
        return result
    if isinstance(result, list):
        return [_map_to_class(into, row) for row in result]
    if result is None:
        return None
    return _map_to_class(into, result)


# ---------------------------------------------------------------------------
# Async idempotent execution helpers
# ---------------------------------------------------------------------------


def _suppress_unretrieved_exception(future: asyncio.Future[Any]) -> None:
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

    @property
    def has_started(self) -> bool:
        """``True`` once :meth:`run` has been entered at least once."""
        return self._future is not None

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


class AsyncCrudBuilder(_CrudState, Generic[T]):
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
        into: type[Any] | None = None,
    ) -> None:
        super().__init__(operation, record, op_name, always_unwrap, into)
        self._executor = executor
        self._runner = _AsyncCachedRunner()
        if data is not None:
            self._mode = _Clause.CONTENT
            self._data = data

    def _check_not_executed(self) -> None:
        """Raise if the builder has already completed an execution.

        After a cancellation the runner resets its cache, so reconfiguration
        IS permitted in that case (the operation never reached completion -
        the user should be able to retry with the same builder). See
        ``_AsyncCachedRunner.run`` for the full cancellation contract.
        """
        if self._runner.has_started:
            raise SurrealError(
                f"Cannot reconfigure a {self.__class__.__name__} after it has "
                "executed. Create a new builder for a fresh operation."
            )

    def content(self, data: Value) -> AsyncCrudBuilder[T]:
        self._set_clause(_Clause.CONTENT, data)
        return self

    def replace(self, data: Value) -> AsyncCrudBuilder[T]:
        self._set_clause(_Clause.REPLACE, data)
        return self

    def merge(self, data: Value) -> AsyncCrudBuilder[T]:
        self._set_clause(_Clause.MERGE, data)
        return self

    def patch(self, data: Value) -> AsyncCrudBuilder[T]:
        self._set_clause(_Clause.PATCH, data)
        return self

    async def _do_execute(self) -> T:
        query, variables = self._build()
        response = await self._executor(query, variables)
        return cast(T, _map_result(self._into, self._extract(response)))

    async def execute(self) -> T:
        return cast(T, await self._runner.run(self._do_execute))

    def __await__(self) -> Generator[Any, None, T]:
        return self.execute().__await__()


class AsyncInsertBuilder(_InsertState, Generic[T]):
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
        into: type[Any] | None = None,
    ) -> None:
        super().__init__(table, data, relation, into)
        self._executor = executor
        self._runner = _AsyncCachedRunner()

    def _check_not_executed(self) -> None:
        """Raise if the builder has already completed an execution.

        After a cancellation the runner resets its cache, so reconfiguration
        IS permitted in that case (the operation never reached completion -
        the user should be able to retry with the same builder). See
        ``_AsyncCachedRunner.run`` for the full cancellation contract.
        """
        if self._runner.has_started:
            raise SurrealError(
                f"Cannot reconfigure a {self.__class__.__name__} after it has "
                "executed. Create a new builder for a fresh operation."
            )

    def relation(self) -> AsyncInsertBuilder[T]:
        self._check_not_executed()
        self._relation = True
        return self

    def content(self, data: Value) -> AsyncInsertBuilder[T]:
        self._check_not_executed()
        self._data = data
        return self

    async def _do_execute(self) -> list[T]:
        query, variables = self._build()
        response = await self._executor(query, variables)
        return cast(list[T], _map_result(self._into, self._extract(response)))

    async def execute(self) -> list[T]:
        return cast(list[T], await self._runner.run(self._do_execute))

    def __await__(self) -> Generator[Any, None, list[T]]:
        return self.execute().__await__()


class AsyncQueryBuilder(_QueryState):
    """Awaitable QUERY builder for async connections.

    Always returns ``list[Value]`` - one entry per statement - even for a
    single statement (fixes the historic silent-discard behaviour, GH issue
    #232). Use ``.first()`` for the first statement's result.

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

    @overload
    def into(self, cls: type[U]) -> AsyncQueryIntoBuilder[U]: ...
    @overload
    def into(
        self, cls: type[U], *, rows: Literal[True]
    ) -> AsyncQueryIntoBuilder[list[U]]: ...
    @overload
    def into(
        self, cls: type[U], *, rows: Literal[False]
    ) -> AsyncQueryIntoBuilder[U]: ...
    @overload
    def into(
        self, cls: type[U], *, rows: bool
    ) -> AsyncQueryIntoBuilder[U | list[U]]: ...
    def into(self, cls: type[U], *, rows: bool = False) -> AsyncQueryIntoBuilder[Any]:
        """Map the query result onto ``cls``.

        Default (``rows`` unset): map the N statement results positionally onto
        the fields / constructor parameters of ``cls`` (awaiting yields one
        ``cls``). ``rows=True``: map each ROW of the single statement result to
        ``cls`` (awaiting yields ``list[cls]``).

        Either way the into-builder reuses *self*'s cached fetch rather than
        issuing a second RPC.
        """
        return AsyncQueryIntoBuilder(self, cls, rows=rows)

    async def execute(self) -> list[Value]:
        return cast("list[Value]", await self._fetch_values())

    async def first(self) -> Value:
        """Return the first statement's result (``None`` if no statements)."""
        values = await self._fetch_values()
        if not values:
            return None
        return cast(Value, values[0])

    def __await__(self) -> Generator[Any, None, list[Value]]:
        return self.execute().__await__()


class AsyncQueryIntoBuilder(Generic[T_co]):
    """Async query builder that maps results onto a user-supplied class.

    Reuses the parent :class:`AsyncQueryBuilder`'s cached fetch so that
    ``await q`` and ``await q.into(T)`` together still only round-trip
    once. ``T_co`` is the *output* type: ``U`` for the default statements-to-
    fields mapping, ``list[U]`` when created with ``rows=True``.
    """

    def __init__(
        self, parent: AsyncQueryBuilder, cls: type[Any], rows: bool = False
    ) -> None:
        self._parent = parent
        self._cls = cls
        self._rows = rows

    async def execute(self) -> T_co:
        values = await self._parent._fetch_values()  # pyright: ignore[reportPrivateUsage]
        if self._rows:
            return cast(
                "T_co",
                [_map_to_class(self._cls, row) for row in _statement_rows(values)],
            )
        return cast("T_co", _map_to_class(self._cls, values))

    def __await__(self) -> Generator[Any, None, T_co]:
        return self.execute().__await__()


# ---------------------------------------------------------------------------
# Sync builders
# ---------------------------------------------------------------------------


class SyncCrudBuilder(_CrudState, Generic[T]):
    """Eager CRUD builder for sync connections.

    Sync connection methods run single-shot operations (``db.create(record,
    data)``) immediately and return the plain result. This builder is only
    handed back for the deferred no-data form (``db.create(record)``) so the
    caller can pick a clause. Every terminal method here runs the operation
    the moment it is called and returns the underlying result:

    - ``.content(data)`` / ``.replace(data)`` / ``.merge(data)`` /
      ``.patch(data)`` run ``CREATE/UPDATE/UPSERT ... <CLAUSE> $data``.
    - ``.execute()`` runs the clause-less form.

    There are **no** magic dunders: the builder never auto-executes on
    ``bool()``, ``==``, indexing, iteration, or attribute access. Repeat
    ``.execute()`` calls return the cached result; calling another clause
    method after the builder has executed raises rather than silently
    returning the stale result.

    Thread safety: ``_run_once()`` is guarded by a per-builder lock so
    consuming the same builder from multiple threads issues exactly one
    RPC. The builder is **not** safe for concurrent *reconfiguration* -
    calling ``.merge()`` on one thread while another calls ``.execute()``
    races on ``_mode`` / ``_data``. Treat builders as single-shot,
    single-owner values.
    """

    def __init__(
        self,
        executor: SyncExecutor,
        operation: str,
        record: RecordIdType,
        op_name: str,
        data: Value | None = None,
        always_unwrap: bool = False,
        into: type[Any] | None = None,
    ) -> None:
        super().__init__(operation, record, op_name, always_unwrap, into)
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
                self._cached_result = _map_result(self._into, self._extract(response))
                self._executed = True
            return self._cached_result


class SyncInsertBuilder(_InsertState, Generic[T]):
    """Eager INSERT builder for sync connections.

    Handed back only for the deferred no-data form (``db.insert(table)``).
    ``.content(data)`` and ``.execute()`` run the operation and return the
    inserted record(s); ``.relation()`` toggles ``INSERT RELATION`` and
    returns ``self`` for chaining. There are **no** magic dunders.
    Reconfiguring the builder *after* it has executed raises rather than
    silently returning the cached result.
    """

    def __init__(
        self,
        executor: SyncExecutor,
        table: str | Table,
        data: Value | None = None,
        relation: bool = False,
        into: type[Any] | None = None,
    ) -> None:
        super().__init__(table, data, relation, into)
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

    def relation(self) -> SyncInsertBuilder[T]:
        self._check_not_executed()
        self._relation = True
        return self

    def content(self, data: Value) -> list[T]:
        self._check_not_executed()
        self._data = data
        return cast(list[T], self._run_once())

    def execute(self) -> list[T]:
        return cast(list[T], self._run_once())

    def _run_once(self) -> Any:
        with self._lock:
            if not self._executed:
                query, variables = self._build()
                response = self._executor(query, variables)
                self._cached_result = _map_result(self._into, self._extract(response))
                self._executed = True
            return self._cached_result


class SyncQueryBuilder(_QueryState):
    """Eager QUERY builder for sync connections.

    ``db.query(sql)`` returns this builder; the caller triggers execution
    explicitly:

    - ``.execute()`` -> ``list[Value]`` (one entry per statement, always a
      list - even for a single statement).
    - ``.first()`` -> the first statement's result (``None`` if no
      statements).
    - ``.into(cls)`` -> the N statement results mapped positionally onto a
      dataclass / class.

    There are **no** magic dunders. Idempotent: ``.execute()``,
    ``.first()``, and ``.into(cls)`` all share a single cached fetch.
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
        self._cached_values: list[Any] | None = None
        self._lock = threading.Lock()

    @overload
    def into(self, cls: type[T]) -> T: ...
    @overload
    def into(self, cls: type[T], *, rows: Literal[True]) -> list[T]: ...
    @overload
    def into(self, cls: type[T], *, rows: Literal[False]) -> T: ...
    @overload
    def into(self, cls: type[T], *, rows: bool) -> T | list[T]: ...
    def into(self, cls: type[T], *, rows: bool = False) -> Any:
        """Map the query result onto ``cls``.

        Default (``rows`` unset): map the N statement results positionally onto
        the fields / constructor parameters of ``cls`` (returns one ``cls``).
        ``rows=True``: map each ROW of the single statement result to ``cls``
        (returns ``list[cls]``).

        Reuses this builder's cached fetch so ``.execute()`` plus ``.into(T)``
        on the same instance only issue one RPC.
        """
        values = self._run_once()
        if rows:
            return [_map_to_class(cls, row) for row in _statement_rows(values)]
        return _map_to_class(cls, values)

    def execute(self) -> list[Value]:
        return cast("list[Value]", self._run_once())

    def first(self) -> Value:
        """Return the first statement's result (``None`` if no statements)."""
        values = self._run_once()
        if not values:
            return None
        return cast(Value, values[0])

    def _run_once(self) -> list[Any]:
        with self._lock:
            if not self._executed:
                response = self._executor(self._query, self._variables)
                self._cached_values = self._statement_values(response)
                self._executed = True
            assert self._cached_values is not None
            return self._cached_values


__all__ = [
    "AsyncCrudBuilder",
    "AsyncInsertBuilder",
    "AsyncQueryBuilder",
    "AsyncQueryIntoBuilder",
    "M",
    "SyncCrudBuilder",
    "SyncInsertBuilder",
    "SyncQueryBuilder",
    "_UNSET",
    "_map_result",
]
