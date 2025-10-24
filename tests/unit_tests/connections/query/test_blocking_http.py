import pytest

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.data.types.record_id import RecordID


def test_query(blocking_http_connection: BlockingHttpSurrealConnection) -> None:
    blocking_http_connection.query("DELETE user;")
    result = blocking_http_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', password = 'password123', enabled = true;"
    )
    assert result == [
        {
            "id": RecordID(table_name="user", identifier="tobie"),
            "name": "Tobie",
            "email": "tobie@example.com",
            "password": "password123",
            "enabled": True,
        }
    ]

    result = blocking_http_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', password = 'password456', enabled = true;"
    )
    assert result == [
        {
            "id": RecordID(table_name="user", identifier="jaime"),
            "name": "Jaime",
            "email": "jaime@example.com",
            "password": "password456",
            "enabled": True,
        }
    ]

    result = blocking_http_connection.query("SELECT * FROM user;")
    assert result == [
        {
            "id": RecordID(table_name="user", identifier="jaime"),
            "name": "Jaime",
            "email": "jaime@example.com",
            "password": "password456",
            "enabled": True,
        },
        {
            "id": RecordID(table_name="user", identifier="tobie"),
            "name": "Tobie",
            "email": "tobie@example.com",
            "password": "password123",
            "enabled": True,
        },
    ]
    blocking_http_connection.query("DELETE user;")
