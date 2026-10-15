"""``batch()``: several statements sent as one transaction, in one request.

The statements are wrapped in ``BEGIN TRANSACTION; ... COMMIT TRANSACTION;``
and sent as a single query, so they all apply or none do. Unlike
``begin_transaction()``, nothing is held open on the server between requests,
so it works over HTTP and on SurrealDB 2 as well as over a websocket on 3.
On SurrealDB 2, a ``RETURN`` statement ends a transaction early, and its value
is the only result.

Example::

    results = (
        db.batch()
        .query("UPDATE account:a SET balance -= $amount", {"amount": 10})
        .query("UPDATE account:b SET balance += $amount")
        .execute()
    )
"""

from collections.abc import Awaitable, Collection, Mapping, Sequence
from typing import Any, Protocol, TypeVar, cast

from surrealdb.errors import (
    ServerError,
    UnexpectedResponseError,
    parse_query_error,
    parse_rpc_error,
)
from surrealdb.features import parse_version
from surrealdb.types import Value

_NOT_EXECUTED = "not executed due to a failed transaction"


class _RunsQueries(Protocol):
    @property
    def server_version(self) -> str | None: ...

    def query_raw(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> dict[str, Any]: ...


class _RunsQueriesAsync(Protocol):
    @property
    def server_version(self) -> str | None: ...

    def query_raw(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> Awaitable[dict[str, Any]]: ...


_B = TypeVar("_B", bound="_BatchState")


class _BatchState:
    def __init__(self) -> None:
        self._statements: list[str] = []
        self._variables: dict[str, Value] = {}

    def query(self: _B, query: str, vars: Mapping[str, Value] | None = None) -> _B:
        """Add *query* to the batch, with its variables.

        Variables are shared by every statement in the batch, so a name bound
        twice must be bound to the same value, of the same type. *query* may
        hold several statements; each gets its own result.
        """
        text = query.strip().rstrip(";").rstrip()
        if not text:
            raise ValueError("batch().query() needs a statement to add")
        bindings = dict(vars or {})
        for name, value in bindings.items():
            if name in self._variables and not _same(self._variables[name], value):
                raise ValueError(
                    f"${name} is already bound to a different value in this "
                    "batch; the statements share their variables, so give "
                    "this one another name"
                )
        self._variables.update(bindings)
        self._statements.append(text)
        return self

    def _sql(self) -> str:
        if not self._statements:
            raise ValueError("an empty batch has nothing to run; add a query()")
        # Each `;` on a line of its own, so a statement's trailing `--`
        # comment cannot swallow it.
        body = "".join(f"{statement}\n;\n" for statement in self._statements)
        return f"BEGIN TRANSACTION;\n{body}COMMIT TRANSACTION;"


def _same(bound: object, value: object) -> bool:
    """Equal and of the same types throughout, so ``True`` is not ``1``."""
    if type(bound) is not type(value):
        return False
    if isinstance(bound, Mapping):
        other = cast(Mapping[object, object], value)
        bound_map = cast(Mapping[object, object], bound)
        return bound_map.keys() == other.keys() and all(
            _same(bound_map[key], other[key]) for key in bound_map
        )
    if isinstance(bound, (set, frozenset)):
        members = list(cast(Collection[object], value))
        return len(members) == len(cast(Collection[object], bound)) and all(
            any(_same(member, other) for other in members)
            for member in cast(Collection[object], bound)
        )
    if isinstance(bound, (list, tuple)):
        items = cast(Sequence[object], value)
        bound_items = cast(Sequence[object], bound)
        return len(bound_items) == len(items) and all(
            _same(a, b) for a, b in zip(bound_items, items, strict=True)
        )
    return bound == value


def _answers_envelope(server_version: str | None) -> bool:
    """Whether the server answers for ``BEGIN`` and ``COMMIT``: 3.0 onward.

    An unknown version is taken as a current server, as the embedded engine
    is one.
    """
    parsed = parse_version(server_version) if server_version else None
    return parsed is None or parsed >= (3, 0, 0)


def _results(response: dict[str, Any], envelope: bool) -> list[Value]:
    """Each statement's result, or the error that failed the transaction.

    SurrealDB 3 answers for ``BEGIN`` and ``COMMIT`` as well, which
    *envelope* says to drop; SurrealDB 2 does not.
    """
    error = response.get("error")
    if error is not None:
        raise parse_rpc_error(error)
    statements = response.get("result")
    if not isinstance(statements, list):
        raise UnexpectedResponseError(
            f"batch expected a list of statement results; got "
            f"{type(statements).__name__}"
        )
    failures: list[ServerError] = [
        parse_query_error(statement)
        for statement in statements
        if isinstance(statement, dict) and statement.get("status") == "ERR"
    ]
    if failures:
        cause = next(
            (failure for failure in failures if _NOT_EXECUTED not in str(failure)),
            failures[0],
        )
        raise cause
    if envelope and len(statements) >= 2:
        statements = statements[1:-1]
    return [
        statement.get("result") if isinstance(statement, dict) else statement
        for statement in statements
    ]


class Batch(_BatchState):
    """Statements to run as one transaction on a blocking connection."""

    def __init__(self, runner: _RunsQueries) -> None:
        super().__init__()
        self._runner = runner

    def execute(self) -> list[Value]:
        """Run the batch, returning each statement's result.

        :raises ServerError: the statement that failed; none of them applied.
        """
        response = self._runner.query_raw(self._sql(), dict(self._variables))
        return _results(response, _answers_envelope(self._runner.server_version))


class AsyncBatch(_BatchState):
    """Statements to run as one transaction on an async connection."""

    def __init__(self, runner: _RunsQueriesAsync) -> None:
        super().__init__()
        self._runner = runner

    async def execute(self) -> list[Value]:
        """Run the batch, returning each statement's result.

        :raises ServerError: the statement that failed; none of them applied.
        """
        response = await self._runner.query_raw(self._sql(), dict(self._variables))
        return _results(response, _answers_envelope(self._runner.server_version))
