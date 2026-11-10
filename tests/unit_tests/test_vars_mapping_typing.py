# pyright: reportArgumentType=true, reportCallIssue=true
"""The ``vars`` a connection takes is any ``Mapping[str, Value]``.

``vars: dict[str, Value]`` was invariant, so ``dict[str, str]`` - a perfectly
good set of bound values - was refused, and so was every other ``Mapping``.
``Mapping`` is covariant in its values, so each call below must type-check, and
the one call that binds a value SurrealDB cannot store must still be refused:
widening the parameter must not have turned it into ``Any``.

``assert_type`` and a call are runtime no-ops here, so this module is a
regression guard for the type checkers, not for the runtime. The header turns on
the two pyright rules the project's own configuration leaves off, because the
refused call is only an error with them on. It is checked under mypy and
pyright, which resolve ``Mapping`` against ``dict`` differently.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.types import Value

SQL = "SELECT * FROM person WHERE name = $name AND age > $age"


def test_blocking_connections_accept_any_mapping() -> None:
    if not TYPE_CHECKING:
        return
    strings: dict[str, str] = {"name": "Tobie"}
    ints: Mapping[str, int] = {"age": 18}
    frozen: MappingProxyType[str, str | int] = MappingProxyType(
        {"name": "Tobie", "age": 18}
    )
    values: dict[str, Value] = {"name": "Tobie", "age": 18}

    for db in (
        BlockingWsSurrealConnection("ws://x"),
        BlockingHttpSurrealConnection("http://x"),
    ):
        db.query(SQL, strings)
        db.query(SQL, ints)
        db.query(SQL, frozen)
        db.query(SQL, values)
        db.query(SQL, vars=frozen)
        db.query(SQL)
        db.query_raw(SQL, frozen)
        db.signin(strings)
        db.signup(frozen)
        db.batch().query(SQL, frozen)


async def test_async_connections_accept_any_mapping() -> None:
    if not TYPE_CHECKING:
        return
    strings: dict[str, str] = {"name": "Tobie"}
    ints: Mapping[str, int] = {"age": 18}
    frozen: MappingProxyType[str, str | int] = MappingProxyType(
        {"name": "Tobie", "age": 18}
    )
    values: dict[str, Value] = {"name": "Tobie", "age": 18}

    for db in (
        AsyncWsSurrealConnection("ws://x"),
        AsyncHttpSurrealConnection("http://x"),
    ):
        db.query(SQL, strings)
        db.query(SQL, ints)
        db.query(SQL, frozen)
        db.query(SQL, values)
        db.query(SQL, vars=frozen)
        db.query(SQL)
        await db.query_raw(SQL, frozen)
        await db.signin(strings)
        await db.signup(frozen)
        db.batch().query(SQL, frozen)


def test_vars_are_still_checked() -> None:
    if not TYPE_CHECKING:
        return
    not_a_value: dict[str, Callable[[], int]] = {"name": lambda: 1}
    db = BlockingWsSurrealConnection("ws://x")
    adb = AsyncWsSurrealConnection("ws://x")

    db.query(SQL, not_a_value)  # type: ignore[arg-type]
    adb.query(SQL, not_a_value)  # type: ignore[arg-type]
