from typing import Any

import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@pytest.fixture
def insert_bulk_data() -> dict[str, Any]:
    return [
        {
            "name": "Tobie",
            "email": "tobie@example.com",
            "enabled": True,
            "password": "root",
        },
        {
            "name": "Jaime",
            "email": "jaime@example.com",
            "enabled": True,
            "password": "root",
        },
    ]


@pytest.fixture
def insert_data() -> dict[str, Any]:
    return [
        {
            "name": "Tobie",
            "email": "tobie@example.com",
            "enabled": True,
            "password": "root",
        },
    ]


def test_insert_string_with_data(
    blocking_http_connection: BlockingHttpSurrealConnection, insert_bulk_data
) -> None:
    blocking_http_connection.query("DELETE user;")
    outcome = blocking_http_connection.insert("user", insert_bulk_data)
    assert 2 == len(outcome)
    assert len(blocking_http_connection.query("SELECT * FROM user;")) == 2
    blocking_http_connection.query("DELETE user;")


def test_insert_record_id_result_error(
    blocking_http_connection: BlockingHttpSurrealConnection, insert_data
) -> None:
    blocking_http_connection.query("DELETE user;")
    record_id = RecordID("user", "tobie")
    with pytest.raises(Exception) as context:
        _ = blocking_http_connection.insert(record_id, insert_data)
    e = str(context.value)
    assert (
        "There was a problem with the database: Can not execute INSERT statement using value"
        in e
        and "user:tobie" in e
    )
    blocking_http_connection.query("DELETE user;")
