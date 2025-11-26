import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_let(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    blocking_ws_connection.query("DELETE person;")
    outcome = blocking_ws_connection.let(
        "name",
        {
            "first": "Tobie",
            "last": "Morgan Hitchcock",
        },
    )
    assert outcome is None
    blocking_ws_connection.query("CREATE person SET name = $name")
    outcome = blocking_ws_connection.query(
        "SELECT * FROM person WHERE name.first = $name.first"
    )
    assert outcome[0]["name"] == {"first": "Tobie", "last": "Morgan Hitchcock"}

    blocking_ws_connection.query("DELETE person;")
