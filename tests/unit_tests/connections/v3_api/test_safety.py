"""
Tests for the v3.0 builder safety properties:

- idempotent execution (no duplicate server round-trips on repeated awaits
  or `.into()` after `.execute()`)
- safe ``__repr__`` / ``__str__`` (no auto-execute on debugger inspection)
- string injection rejection in resource targets
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import SurrealError


@pytest.fixture(autouse=True)
async def _async_setup(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query(
        "REMOVE TABLE IF EXISTS counter;"
        "DEFINE TABLE counter SCHEMALESS;"
        "DEFINE FIELD n ON counter TYPE int DEFAULT 0;"
    )
    yield
    await async_ws_connection.query("REMOVE TABLE IF EXISTS counter;")


@pytest.fixture(autouse=True)
def _sync_setup(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query(
        "REMOVE TABLE IF EXISTS counter;"
        "DEFINE TABLE counter SCHEMALESS;"
        "DEFINE FIELD n ON counter TYPE int DEFAULT 0;"
    ).execute()
    yield
    blocking_ws_connection.query("REMOVE TABLE IF EXISTS counter;").execute()


# ---------------------------------------------------------------------------
# Idempotency: async builders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_query_awaited_twice_runs_once(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """Awaiting the same async query builder twice must reuse the cache."""
    await async_ws_connection.query("CREATE counter:trace SET n = 1")
    builder = async_ws_connection.query(
        "UPDATE counter:trace SET n = n + 1 RETURN AFTER"
    )
    first = await builder
    second = await builder
    # Both await results are identical (same cached fetch)
    assert first == second
    # Server-side, the UPDATE only ran once - n is 2, not 3
    after = await async_ws_connection.query(
        "SELECT n FROM counter:trace"
    )
    assert after[0]["n"] == 2


@pytest.mark.asyncio
async def test_async_query_concurrent_awaits_run_once(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.query("CREATE counter:concurrent SET n = 0")
    builder = async_ws_connection.query(
        "UPDATE counter:concurrent SET n = n + 1 RETURN AFTER"
    )
    a, b, c = await asyncio.gather(builder, builder, builder)
    assert a == b == c
    after = await async_ws_connection.query("SELECT n FROM counter:concurrent")
    assert after[0]["n"] == 1


@pytest.mark.asyncio
async def test_async_crud_awaited_twice_runs_once(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    builder = async_ws_connection.create("counter:once", {"n": 1})
    first = await builder
    second = await builder
    assert first == second
    # If the CREATE had run twice the second await would have raised on
    # the duplicate record - reaching this point proves it ran once.


# ---------------------------------------------------------------------------
# Idempotency: query().into() shares parent's fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_into_shares_parent_fetch(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    @dataclass
    class Pair:
        a: int
        b: int

    await async_ws_connection.query("CREATE counter:share SET n = 7")
    builder = async_ws_connection.query(
        "UPDATE counter:share SET n = n + 1 RETURN AFTER;"
        "RETURN 99;"
    )
    direct = await builder
    mapped = await builder.into(Pair)
    # `direct` is a tuple (update_list, 99); `mapped` repacks the same
    # values into Pair. They reference the same cached fetch.
    assert direct[0] == mapped.a
    assert direct[1] == mapped.b
    # Server-side, the UPDATE ran only once - the n value is 8 (was 7, +1).
    after = await async_ws_connection.query("SELECT n FROM counter:share")
    assert after[0]["n"] == 8


def test_sync_into_shares_parent_fetch(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    @dataclass
    class Pair:
        a: int
        b: int

    blocking_ws_connection.query("CREATE counter:sync_share SET n = 5").execute()
    builder = blocking_ws_connection.query(
        "UPDATE counter:sync_share SET n = n + 1 RETURN AFTER;"
        "RETURN 11;"
    )
    direct = builder.execute()
    mapped = builder.into(Pair)
    assert direct[0] == mapped.a
    assert direct[1] == mapped.b
    after = blocking_ws_connection.query("SELECT n FROM counter:sync_share")
    assert after[0]["n"] == 6


# ---------------------------------------------------------------------------
# Safe __repr__ / __str__
# ---------------------------------------------------------------------------


def test_sync_builder_repr_does_not_execute(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """Calling repr()/str() on a pending builder must not run the query."""
    blocking_ws_connection.query("CREATE counter:repr_safe SET n = 1").execute()
    blocking_ws_connection.update("counter:repr_safe").merge({"n": 999})
    # Fresh pending builder - just inspecting must not execute it.
    pending = blocking_ws_connection.update("counter:repr_safe", {"n": 555})
    assert "pending" in repr(pending)
    assert "pending" in str(pending)
    after = blocking_ws_connection.query(
        "SELECT n FROM counter:repr_safe"
    ).execute()
    # n is whatever the previously-terminal merge set, not 555.
    assert after[0]["n"] == 999


# ---------------------------------------------------------------------------
# String-target injection rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_unsafe_string_record_rejected(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """A semicolon in a str target must be rejected up-front."""
    with pytest.raises(SurrealError):
        # Range-syntax fallback path - ".." present so we don't parse as
        # record-id - then the unsafe-character check fires.
        await async_ws_connection.delete("counter:1..10; REMOVE TABLE counter;")


def test_sync_unsafe_string_record_rejected(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    with pytest.raises(SurrealError):
        blocking_ws_connection.delete(
            "counter:1..10; REMOVE TABLE counter;"
        ).execute()


@pytest.mark.asyncio
async def test_string_record_id_bound_safely(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """A normal `"table:id"` string is bound as a parameterised RecordID."""
    await async_ws_connection.create("counter:abc", {"n": 42})
    out = await async_ws_connection.select("counter:abc")
    assert isinstance(out, list)
    assert out[0]["n"] == 42


@pytest.mark.asyncio
async def test_table_string_with_safe_chars_works(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create("counter").content({"n": 1})
    rows = await async_ws_connection.select("counter")
    assert isinstance(rows, list)
    assert len(rows) >= 1
