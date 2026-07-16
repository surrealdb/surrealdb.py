"""End-to-end tests for the ``into=`` row-model API against a live server.

These use the connection fixtures, so they self-skip when no SurrealDB server
is reachable (see ``tests/unit_tests/connections/conftest.py``). They prove the
required round-trips for both the async and sync WebSocket connections:

- ``select(RecordID, into=M) -> M`` / ``select(absent, into=M) -> None``
- ``select(Table, into=M) -> list[M]``
- ``create``/``update`` round-trip with ``into=M`` -> ``M``
- ``query(sql).into(M, rows=True) -> list[M]``
"""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@dataclass
class Person:
    id: Any
    name: str


@pytest.fixture(autouse=True)
async def _async_setup(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query("DELETE person;")
    yield
    await async_ws_connection.query("DELETE person;")


@pytest.fixture(autouse=True)
def _sync_setup(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query("DELETE person;").execute()
    yield
    blocking_ws_connection.query("DELETE person;").execute()


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_select_record_id_into(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.query("CREATE person:tobie SET name = 'Tobie';")
    out = await async_ws_connection.select(RecordID("person", "tobie"), into=Person)
    assert isinstance(out, Person)
    assert out.name == "Tobie"


@pytest.mark.asyncio
async def test_async_select_absent_into(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    out = await async_ws_connection.select(RecordID("person", "missing"), into=Person)
    assert out is None


@pytest.mark.asyncio
async def test_async_select_table_into(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.query("CREATE person:tobie SET name = 'Tobie';")
    await async_ws_connection.query("CREATE person:jaime SET name = 'Jaime';")
    out = await async_ws_connection.select(Table("person"), into=Person)
    assert isinstance(out, list)
    assert len(out) == 2
    assert all(isinstance(p, Person) for p in out)
    assert {p.name for p in out} == {"Tobie", "Jaime"}


@pytest.mark.asyncio
async def test_async_create_into_round_trip(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    out = await async_ws_connection.create(
        RecordID("person", "tobie"), {"name": "Tobie"}, into=Person
    )
    assert isinstance(out, Person)
    assert out.name == "Tobie"


@pytest.mark.asyncio
async def test_async_update_into_round_trip(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.query("CREATE person:tobie SET name = 'Tobie';")
    out = await async_ws_connection.update(
        RecordID("person", "tobie"), {"name": "Updated"}, into=Person
    )
    assert isinstance(out, Person)
    assert out.name == "Updated"


@pytest.mark.asyncio
async def test_async_query_into_rows(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.query("CREATE person:tobie SET name = 'Tobie';")
    await async_ws_connection.query("CREATE person:jaime SET name = 'Jaime';")
    out = await async_ws_connection.query("SELECT * FROM person").into(
        Person, rows=True
    )
    assert isinstance(out, list)
    assert len(out) == 2
    assert all(isinstance(p, Person) for p in out)


@pytest.mark.asyncio
async def test_async_no_data_builder_carries_into(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """The no-data builder form carries M so ``.merge(...)`` returns ``M``."""
    out = await async_ws_connection.create(
        RecordID("person", "tobie"), into=Person
    ).merge({"name": "Tobie"})
    assert isinstance(out, Person)
    assert out.name == "Tobie"


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def test_sync_select_record_id_into(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    blocking_ws_connection.query("CREATE person:tobie SET name = 'Tobie';").execute()
    out = blocking_ws_connection.select(RecordID("person", "tobie"), into=Person)
    assert isinstance(out, Person)
    assert out.name == "Tobie"


def test_sync_select_absent_into(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    out = blocking_ws_connection.select(RecordID("person", "missing"), into=Person)
    assert out is None


def test_sync_select_table_into(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    blocking_ws_connection.query("CREATE person:tobie SET name = 'Tobie';").execute()
    blocking_ws_connection.query("CREATE person:jaime SET name = 'Jaime';").execute()
    out = blocking_ws_connection.select(Table("person"), into=Person)
    assert isinstance(out, list)
    assert len(out) == 2
    assert all(isinstance(p, Person) for p in out)


def test_sync_create_into_round_trip(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    out = blocking_ws_connection.create(
        RecordID("person", "tobie"), {"name": "Tobie"}, into=Person
    )
    assert isinstance(out, Person)
    assert out.name == "Tobie"


def test_sync_update_into_round_trip(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    blocking_ws_connection.query("CREATE person:tobie SET name = 'Tobie';").execute()
    out = blocking_ws_connection.update(
        RecordID("person", "tobie"), {"name": "Updated"}, into=Person
    )
    assert isinstance(out, Person)
    assert out.name == "Updated"


def test_sync_no_data_builder_carries_into(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """The no-data (eager) builder form carries M so ``.merge(...)`` returns ``M``."""
    out = blocking_ws_connection.create(RecordID("person", "tobie"), into=Person).merge(
        {"name": "Tobie"}
    )
    assert isinstance(out, Person)
    assert out.name == "Tobie"


def test_sync_query_into_rows(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    blocking_ws_connection.query("CREATE person:tobie SET name = 'Tobie';").execute()
    blocking_ws_connection.query("CREATE person:jaime SET name = 'Jaime';").execute()
    out = blocking_ws_connection.query("SELECT * FROM person").into(Person, rows=True)
    assert isinstance(out, list)
    assert len(out) == 2
    assert all(isinstance(p, Person) for p in out)
