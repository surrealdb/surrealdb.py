from collections.abc import AsyncGenerator
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


@pytest.fixture(autouse=True)
async def setup_data(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query("DELETE user;")
    await async_ws_connection.query("DELETE likes;")
    await async_ws_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password123', enabled = true;"
    )
    await async_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password456', enabled = true;"
    )
    yield
    await async_ws_connection.query("DELETE user;")
    await async_ws_connection.query("DELETE likes;")


def check_outcome(outcome: list[Any]) -> None:
    assert RecordID("user", "tobie") == outcome[0]["in"]
    assert RecordID("likes", 123) == outcome[0]["out"]
    assert RecordID("user", "jaime") == outcome[1]["in"]
    assert RecordID("likes", 400) == outcome[1]["out"]


async def test_insert_relation_record_ids(
    async_ws_connection: AsyncWsSurrealConnection, setup_data: None
) -> None:
    data = [
        {
            "in": RecordID("user", "tobie"),
            "out": RecordID("likes", 123),
        },
        {
            "in": RecordID("user", "jaime"),
            "out": RecordID("likes", 400),
        },
    ]
    outcome = await async_ws_connection.insert_relation("likes", data)
    assert RecordID("user", "tobie") == outcome[0]["in"]
    assert RecordID("likes", 123) == outcome[0]["out"]
    assert RecordID("user", "jaime") == outcome[1]["in"]
    assert RecordID("likes", 400) == outcome[1]["out"]


async def test_insert_relation_record_id(
    async_ws_connection: AsyncWsSurrealConnection, setup_data: None
) -> None:
    data = {
        "in": RecordID("user", "tobie"),
        "out": RecordID("likes", 123),
    }
    outcome = await async_ws_connection.insert_relation("likes", data)
    assert RecordID("user", "tobie") == outcome[0]["in"]
    assert RecordID("likes", 123) == outcome[0]["out"]
