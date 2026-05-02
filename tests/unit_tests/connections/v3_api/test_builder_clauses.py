"""
Tests for the v3.0 awaitable / lazy CRUD builder pattern.

Each test verifies that ``.content/.replace/.merge/.patch`` chained on the
returned builder issue the right SurrealQL clause and return the expected
shape (dict for record-id targets, list for table-level targets).
"""

from collections.abc import AsyncGenerator, Generator

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture(autouse=True)
async def _async_setup(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query(
        "REMOVE TABLE IF EXISTS bld; DEFINE TABLE bld SCHEMALESS;"
        "REMOVE TABLE IF EXISTS rel_x; DEFINE TABLE rel_x SCHEMALESS;"
        "REMOVE TABLE IF EXISTS rel_y; DEFINE TABLE rel_y SCHEMALESS;"
    )
    yield
    await async_ws_connection.query(
        "REMOVE TABLE IF EXISTS bld;"
        "REMOVE TABLE IF EXISTS rel_x;"
        "REMOVE TABLE IF EXISTS rel_y;"
    )


@pytest.fixture(autouse=True)
def _sync_setup(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query(
        "REMOVE TABLE IF EXISTS bld; DEFINE TABLE bld SCHEMALESS;"
        "REMOVE TABLE IF EXISTS rel_z; DEFINE TABLE rel_z SCHEMALESS;"
    ).execute()
    yield
    blocking_ws_connection.query(
        "REMOVE TABLE IF EXISTS bld;"
        "REMOVE TABLE IF EXISTS rel_z;"
    ).execute()


# ---------------------------------------------------------------------------
# Async: clause methods on RecordID/Table targets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_create_content_record_id(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    out = await async_ws_connection.create(RecordID("bld", "a")).content(
        {"name": "alice"}
    )
    assert isinstance(out, dict)
    assert out["name"] == "alice"


@pytest.mark.asyncio
async def test_async_update_replace_record_id(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create(RecordID("bld", "b"), {"name": "bob", "age": 30})
    out = await async_ws_connection.update(RecordID("bld", "b")).replace(
        {"name": "bobby"}
    )
    assert isinstance(out, dict)
    assert out["name"] == "bobby"
    assert "age" not in out


@pytest.mark.asyncio
async def test_async_update_merge_table(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create(RecordID("bld", "c"), {"name": "carol"})
    out = await async_ws_connection.update(Table("bld")).merge({"flag": True})
    assert isinstance(out, list)
    assert out[0]["flag"] is True


@pytest.mark.asyncio
async def test_async_update_patch_record_id(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create(
        RecordID("bld", "d"), {"name": "dora", "score": 1}
    )
    out = await async_ws_connection.update(RecordID("bld", "d")).patch(
        [{"op": "replace", "path": "/score", "value": 99}]
    )
    assert out["score"] == 99


@pytest.mark.asyncio
async def test_async_delete_no_clause_works(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create(RecordID("bld", "e"))
    out = await async_ws_connection.delete(RecordID("bld", "e"))
    assert out is not None


@pytest.mark.asyncio
async def test_async_insert_relation_kwarg(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create(RecordID("bld", "u1"))
    await async_ws_connection.create(RecordID("bld", "u2"))
    out = await async_ws_connection.insert(
        Table("rel_x"),
        {"in": RecordID("bld", "u1"), "out": RecordID("bld", "u2")},
        relation=True,
    )
    assert isinstance(out, list)


@pytest.mark.asyncio
async def test_async_insert_relation_chained(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create(RecordID("bld", "u3"))
    await async_ws_connection.create(RecordID("bld", "u4"))
    out = await async_ws_connection.insert(Table("rel_y")).relation().content(
        {"in": RecordID("bld", "u3"), "out": RecordID("bld", "u4")}
    )
    assert isinstance(out, list)


# ---------------------------------------------------------------------------
# Sync: lazy builder + magic auto-execute
# ---------------------------------------------------------------------------


def test_sync_create_content(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    out = blocking_ws_connection.create(RecordID("bld", "s1")).content({"x": 1})
    assert out["x"] == 1


def test_sync_update_merge_table(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    blocking_ws_connection.create(RecordID("bld", "s2"), {"y": 1}).execute()
    out = blocking_ws_connection.update(Table("bld")).merge({"flag": True})
    assert isinstance(out, list)


def test_sync_builder_auto_execute_on_index(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """Indexing into a sync builder triggers execution."""
    blocking_ws_connection.create(RecordID("bld", "s3"), {"name": "x"}).execute()
    builder = blocking_ws_connection.update(RecordID("bld", "s3"))
    # accessing a key triggers __getitem__ -> _run_once()
    assert builder["name"] == "x"


def test_sync_builder_explicit_execute(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """`.execute()` explicitly runs the operation."""
    out = blocking_ws_connection.create(RecordID("bld", "s4")).execute()
    assert out["id"] == RecordID("bld", "s4")


def test_sync_insert_relation_kwarg(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    blocking_ws_connection.create(RecordID("bld", "i1")).execute()
    blocking_ws_connection.create(RecordID("bld", "i2")).execute()
    out = blocking_ws_connection.insert(
        Table("rel_z"),
        {"in": RecordID("bld", "i1"), "out": RecordID("bld", "i2")},
        relation=True,
    )
    assert len(out) == 1
