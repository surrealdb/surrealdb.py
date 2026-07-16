from typing import cast

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


def test_select(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    blocking_ws_connection.query("DELETE user;").execute()
    blocking_ws_connection.query("DELETE users;").execute()

    # Create users with required fields
    blocking_ws_connection.query(
        "CREATE user:tobie SET name = 'Tobie', email = 'tobie@example.com', enabled = true, password = 'root';"
    ).execute()
    blocking_ws_connection.query(
        "CREATE user:jaime SET name = 'Jaime', email = 'jaime@example.com', enabled = true, password = 'root';"
    ).execute()

    blocking_ws_connection.query("CREATE users:one SET name = 'one';").execute()
    blocking_ws_connection.query("CREATE users:two SET name = 'two';").execute()

    outcome = blocking_ws_connection.select("user")
    assert outcome[0]["name"] == "Jaime"
    assert outcome[1]["name"] == "Tobie"
    assert 2 == len(cast(list, outcome))


def test_select_record_id_present(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query("DELETE user;").execute()
    blocking_ws_connection.query("CREATE user:tobie SET name = 'Tobie';").execute()

    outcome = blocking_ws_connection.select(RecordID("user", "tobie"))
    assert isinstance(outcome, dict)
    assert outcome["name"] == "Tobie"

    blocking_ws_connection.query("DELETE user;").execute()


def test_select_record_id_absent(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query("DELETE user;").execute()

    outcome = blocking_ws_connection.select(RecordID("user", "missing"))
    assert outcome is None


def test_select_string_record_id_present(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query("DELETE user;").execute()
    blocking_ws_connection.query("CREATE user:tobie SET name = 'Tobie';").execute()

    outcome = blocking_ws_connection.select("user:tobie")
    assert isinstance(outcome, dict)
    assert outcome["name"] == "Tobie"

    blocking_ws_connection.query("DELETE user;").execute()


def test_select_table_returns_list(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query("DELETE user;").execute()
    blocking_ws_connection.query("CREATE user:tobie SET name = 'Tobie';").execute()
    blocking_ws_connection.query("CREATE user:jaime SET name = 'Jaime';").execute()

    outcome = blocking_ws_connection.select(Table("user"))
    assert isinstance(outcome, list)
    assert len(outcome) == 2

    blocking_ws_connection.query("DELETE user;").execute()
