import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


def test_query(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    blocking_ws_connection.query("DELETE user;")
    result = blocking_ws_connection.query(
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

    result = blocking_ws_connection.query(
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

    result = blocking_ws_connection.query("SELECT * FROM user;")
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
    blocking_ws_connection.query("DELETE user;")
