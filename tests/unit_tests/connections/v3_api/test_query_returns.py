"""
Tests for the v3.0 query() return shape.

Verifies the fix for GH issue #232: previously query() always returned
``response["result"][0]["result"]``, silently dropping every statement
result after the first. The new behaviour ALWAYS returns a
``list[Value]`` - one entry per statement, even for a single statement -
so transactions and multi-statement queries never lose data. ``.first()``
returns the first statement's result, and ``.into(cls)`` maps the N
statement results positionally onto a dataclass / class.
"""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import UnexpectedResponseError


@pytest.fixture(autouse=True)
async def _async_setup(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query(
        "REMOVE TABLE IF EXISTS multi_q; DEFINE TABLE multi_q SCHEMALESS;"
    )
    yield
    await async_ws_connection.query("REMOVE TABLE IF EXISTS multi_q;")


@pytest.fixture(autouse=True)
def _blocking_setup(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query(
        "REMOVE TABLE IF EXISTS multi_q; DEFINE TABLE multi_q SCHEMALESS;"
    ).execute()
    yield
    blocking_ws_connection.query("REMOVE TABLE IF EXISTS multi_q;").execute()


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_query_single_statement_returns_list(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _blocking_setup: None,
) -> None:
    result = await async_ws_connection.query("RETURN 42;")
    assert result == [42]
    first = await async_ws_connection.query("RETURN 42;").first()
    assert first == 42


@pytest.mark.asyncio
async def test_async_query_multi_statement_returns_list(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _blocking_setup: None,
) -> None:
    result = await async_ws_connection.query("RETURN 1; RETURN 2; RETURN 3;")
    assert isinstance(result, list)
    assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_async_query_transaction_block_surfaces_all_results(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _blocking_setup: None,
) -> None:
    """Reproduction for issue #232.

    The transaction should expose the UPDATE result rather than silently
    dropping it. ``query()`` returns one ``list`` entry per statement, so
    the UPDATE result must be observable somewhere in the list.
    """
    await async_ws_connection.query("CREATE multi_q:1 SET status = 'pending';")
    result = await async_ws_connection.query(
        "BEGIN TRANSACTION;"
        " UPDATE multi_q:1 SET status = 'running';"
        " COMMIT TRANSACTION;"
    )

    def _is_update_result(item: object) -> bool:
        return (
            isinstance(item, list)
            and len(item) > 0
            and isinstance(item[0], dict)
            and item[0].get("status") == "running"
        )

    assert isinstance(result, list)
    assert any(_is_update_result(item) for item in result), result


@pytest.mark.asyncio
async def test_async_query_into_dataclass(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _blocking_setup: None,
) -> None:
    @dataclass
    class Result:
        first: int
        second: int
        third: int

    mapped = await async_ws_connection.query("RETURN 10; RETURN 20; RETURN 30;").into(
        Result
    )
    assert isinstance(mapped, Result)
    assert mapped.first == 10
    assert mapped.second == 20
    assert mapped.third == 30


@pytest.mark.asyncio
async def test_async_query_into_field_count_mismatch(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _blocking_setup: None,
) -> None:
    @dataclass
    class TooManyFields:
        a: int
        b: int
        c: int
        d: int

    with pytest.raises(UnexpectedResponseError):
        await async_ws_connection.query("RETURN 1; RETURN 2;").into(TooManyFields)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def test_blocking_query_single_statement_returns_list(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _blocking_setup: None,
) -> None:
    result = blocking_ws_connection.query("RETURN 42;").execute()
    assert result == [42]
    assert blocking_ws_connection.query("RETURN 42;").first() == 42


def test_blocking_query_multi_statement_returns_list(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _blocking_setup: None,
) -> None:
    result = blocking_ws_connection.query("RETURN 1; RETURN 2; RETURN 3;").execute()
    assert isinstance(result, list)
    assert result == [1, 2, 3]


def test_blocking_query_into_dataclass(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _blocking_setup: None,
) -> None:
    @dataclass
    class Result:
        a: int
        b: int

    mapped = blocking_ws_connection.query("RETURN 7; RETURN 11;").into(Result)
    assert isinstance(mapped, Result)
    assert mapped.a == 7
    assert mapped.b == 11
