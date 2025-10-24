import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


def test_select(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query("DELETE users;")

    # Create users with required fields
    blocking_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    )
    blocking_ws_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', enabled = true, password = 'root';"
    )

    blocking_ws_connection.query("CREATE users:one SET name = 'one';")
    blocking_ws_connection.query("CREATE users:two SET name = 'two';")

    outcome = blocking_ws_connection.select("user")
    assert outcome[0]["name"] == "Jaime"
    assert outcome[1]["name"] == "Tobie"
    assert 2 == len(outcome)
