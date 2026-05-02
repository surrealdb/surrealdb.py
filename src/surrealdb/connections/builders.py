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
"""

from __future__ import annotations

import inspect
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
# Helpers (replicated from UtilsMixin to avoid coupling)
# ---------------------------------------------------------------------------


def _resource_to_variable(
    resource: RecordIdType, variables: dict[str, Any], var_name: str
) -> str:
    if isinstance(resource, Table):
        return resource.table_name
    if isinstance(resource, RecordID):
        variables[var_name] = resource
        return f"${var_name}"
    return resource


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


_CRUD_OPERATIONS = {"CREATE", "UPDATE", "UPSERT"}


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

    def _set_clause(self, mode: str, data: Value | None) -> None:
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

    def _build(self) -> tuple[str, dict[str, Any]]:
        if self._data is None:
            raise SurrealError("INSERT requires data; pass via insert(table, data) or .content(data)")
        variables: dict[str, Any] = {}
        table_ref = _resource_to_variable(self._table, variables, "_table")
        variables["_data"] = self._data
        rel = "RELATION " if self._relation else ""
        return f"INSERT {rel}INTO {table_ref} $_data", variables

    def _extract(self, response: dict[str, Any]) -> Any:
        op_name = "insert_relation" if self._relation else "insert"
        stmts = _check_response(response, op_name)
        return _check_first_statement(stmts)


class _QueryState:
    """State for query builder."""

    def __init__(self, query: str, variables: dict[str, Value] | None) -> None:
        self._query = query
        self._variables: dict[str, Any] = dict(variables) if variables else {}

    def _execute_results(self, response: dict[str, Any]) -> list[Any]:
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
# Async builders
# ---------------------------------------------------------------------------


class _AsyncCrudBuilder(_CrudState, Generic[T]):
    """Awaitable CRUD builder for async connections."""

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
        if data is not None:
            self._mode = _Clause.CONTENT
            self._data = data

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

    async def execute(self) -> T:
        query, variables = self._build()
        response = await self._executor(query, variables)
        return cast(T, self._extract(response))

    def __await__(self) -> Generator[Any, None, T]:
        return self.execute().__await__()


class _AsyncInsertBuilder(_InsertState):
    """Awaitable INSERT builder for async connections."""

    def __init__(
        self,
        executor: AsyncExecutor,
        table: str | Table,
        data: Value | None = None,
        relation: bool = False,
    ) -> None:
        super().__init__(table, data, relation)
        self._executor = executor

    def relation(self) -> "_AsyncInsertBuilder":
        self._relation = True
        return self

    def content(self, data: Value) -> "_AsyncInsertBuilder":
        self._data = data
        return self

    async def execute(self) -> list[Value]:
        query, variables = self._build()
        response = await self._executor(query, variables)
        return cast(list[Value], self._extract(response))

    def __await__(self) -> Generator[Any, None, list[Value]]:
        return self.execute().__await__()


class _AsyncQueryBuilder(_QueryState):
    """Awaitable QUERY builder for async connections.

    Returns a single Value when the server returned exactly one statement
    result, otherwise a tuple of all statement results (fixes the historic
    silent-discard behaviour - GH issue #232).
    """

    def __init__(
        self,
        executor: AsyncExecutor,
        query: str,
        variables: dict[str, Value] | None = None,
    ) -> None:
        super().__init__(query, variables)
        self._executor = executor

    def into(self, cls: type[U]) -> "_AsyncQueryIntoBuilder[U]":
        return _AsyncQueryIntoBuilder(self._executor, self._query, self._variables, cls)

    async def execute(self) -> Value | tuple[Value, ...]:
        response = await self._executor(self._query, self._variables)
        values = self._execute_results(response)
        if len(values) == 1:
            return values[0]
        return tuple(values)

    def __await__(self) -> Generator[Any, None, Value | tuple[Value, ...]]:
        return self.execute().__await__()


class _AsyncQueryIntoBuilder(_QueryState, Generic[T]):
    """Async query builder that maps results onto a user-supplied class."""

    def __init__(
        self,
        executor: AsyncExecutor,
        query: str,
        variables: dict[str, Value] | None,
        cls: type[T],
    ) -> None:
        super().__init__(query, variables)
        self._executor = executor
        self._cls = cls

    async def execute(self) -> T:
        response = await self._executor(self._query, self._variables)
        values = self._execute_results(response)
        return _map_to_class(self._cls, values)

    def __await__(self) -> Generator[Any, None, T]:
        return self.execute().__await__()


# ---------------------------------------------------------------------------
# Sync builders
# ---------------------------------------------------------------------------


class _SyncBuilderMixin:
    """Magic methods that auto-execute the builder when used as a result.

    Subclasses must define ``_run_once()`` returning the cached result.

    Builders are *lazy*: the operation only runs when you consume the
    result (via indexing, iteration, comparison, etc.) or call
    ``.execute()`` explicitly. This means ``db.query("DELETE foo")`` on a
    sync connection does **not** execute - call ``.execute()`` (or capture
    and use the result) to trigger the operation.
    """

    _executed: bool
    _cached_result: Any

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
        # Eagerly execute so ``print(builder)`` shows the real result
        # rather than a pending placeholder. Use a try/except so the repr
        # itself never raises - debugging tools (logging, pytest output)
        # commonly call repr() and we shouldn't break those if the operation
        # would fail.
        try:
            return repr(self._run_once())
        except Exception as exc:  # noqa: BLE001 - safe repr fallback
            return f"<{self.__class__.__name__} error: {exc}>"

    def __str__(self) -> str:
        return str(self._run_once())

    def __getattr__(self, name: str) -> Any:
        # __getattr__ is only invoked when the attribute is missing on the
        # instance. Internal attributes start with ``_`` and are always set
        # in __init__ so we never reach here for them.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._run_once(), name)


class _SyncCrudBuilder(_CrudState, _SyncBuilderMixin, Generic[T]):
    """Lazy CRUD builder for sync connections.

    Clause methods (``content``/``replace``/``merge``/``patch``) are terminal:
    they execute immediately and return the result. The plain
    ``db.create(record)`` form returns this builder; use ``.execute()`` or
    just access the result via dict/list operations to trigger execution.
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
        if data is not None:
            self._mode = _Clause.CONTENT
            self._data = data

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
        if not self._executed:
            query, variables = self._build()
            response = self._executor(query, variables)
            self._cached_result = self._extract(response)
            self._executed = True
        return self._cached_result


class _SyncInsertBuilder(_InsertState, _SyncBuilderMixin):
    """Lazy INSERT builder for sync connections."""

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

    def relation(self) -> "_SyncInsertBuilder":
        self._relation = True
        return self

    def content(self, data: Value) -> list[Value]:
        self._data = data
        return cast(list[Value], self._run_once())

    def execute(self) -> list[Value]:
        return cast(list[Value], self._run_once())

    def _run_once(self) -> Any:
        if not self._executed:
            query, variables = self._build()
            response = self._executor(query, variables)
            self._cached_result = self._extract(response)
            self._executed = True
        return self._cached_result


class _SyncQueryBuilder(_QueryState, _SyncBuilderMixin):
    """Lazy QUERY builder for sync connections."""

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

    def into(self, cls: type[T]) -> T:
        builder = _SyncQueryIntoBuilder(
            self._executor, self._query, self._variables, cls
        )
        return builder.execute()

    def execute(self) -> Value | tuple[Value, ...]:
        return cast("Value | tuple[Value, ...]", self._run_once())

    def _run_once(self) -> Any:
        if not self._executed:
            response = self._executor(self._query, self._variables)
            values = self._execute_results(response)
            if len(values) == 1:
                self._cached_result = values[0]
            else:
                self._cached_result = tuple(values)
            self._executed = True
        return self._cached_result


class _SyncQueryIntoBuilder(_QueryState, Generic[T]):
    """Sync query builder that maps results onto a user-supplied class."""

    def __init__(
        self,
        executor: SyncExecutor,
        query: str,
        variables: dict[str, Value] | None,
        cls: type[T],
    ) -> None:
        super().__init__(query, variables)
        self._executor = executor
        self._cls = cls

    def execute(self) -> T:
        response = self._executor(self._query, self._variables)
        values = self._execute_results(response)
        return _map_to_class(self._cls, values)


__all__ = [
    "_AsyncCrudBuilder",
    "_AsyncInsertBuilder",
    "_AsyncQueryBuilder",
    "_AsyncQueryIntoBuilder",
    "_SyncCrudBuilder",
    "_SyncInsertBuilder",
    "_SyncQueryBuilder",
    "_SyncQueryIntoBuilder",
]
