from collections.abc import Generator
from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID


@pytest.fixture(autouse=True)
def setup_data(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> Generator[None, None, None]:
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query("DELETE likes;")
    blocking_http_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password123', enabled = true;"
    )
    blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password456', enabled = true;"
    )
    yield
    blocking_http_connection.query("DELETE user;")
    blocking_http_connection.query("DELETE likes;")


def check_outcome(outcome: list[Any]) -> None:
    assert RecordID("user", "tobie") == outcome[0]["in"]
    assert RecordID("likes", 123) == outcome[0]["out"]
    assert RecordID("user", "jaime") == outcome[1]["in"]
    assert RecordID("likes", 400) == outcome[1]["out"]


def test_insert_relation_record_ids(
    blocking_http_connection: BlockingHttpSurrealConnection, setup_data: None
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
    outcome = blocking_http_connection.insert_relation("likes", data)
    assert RecordID("user", "tobie") == outcome[0]["in"]
    assert RecordID("likes", 123) == outcome[0]["out"]
    assert RecordID("user", "jaime") == outcome[1]["in"]
    assert RecordID("likes", 400) == outcome[1]["out"]


def test_insert_relation_record_id(
    blocking_http_connection: BlockingHttpSurrealConnection, setup_data: None
) -> None:
    data = {
        "in": RecordID("user", "tobie"),
        "out": RecordID("likes", 123),
    }
    outcome = blocking_http_connection.insert_relation("likes", data)
    assert RecordID("user", "tobie") == outcome[0]["in"]
    assert RecordID("likes", 123) == outcome[0]["out"]
