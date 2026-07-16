from typing import cast

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_unset(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    blocking_ws_connection.query("DELETE person;").execute()
    blocking_ws_connection.let(
        "name",
        {
            "first": "Tobie",
            "last": "Morgan Hitchcock",
        },
    )
    blocking_ws_connection.query("CREATE person SET name = $name").execute()
    outcome = blocking_ws_connection.query(
        "SELECT * FROM person WHERE name.first = $name.first"
    ).first()
    assert len(cast(list, outcome)) == 1
    assert outcome[0]["name"] == {"first": "Tobie", "last": "Morgan Hitchcock"}

    blocking_ws_connection.unset(key="name")

    # because the key was unset then $name.first is None returning []
    outcome = blocking_ws_connection.query(
        "SELECT * FROM person WHERE name.first = $name.first"
    ).first()
    assert outcome == []

    blocking_ws_connection.query("DELETE person;").execute()
