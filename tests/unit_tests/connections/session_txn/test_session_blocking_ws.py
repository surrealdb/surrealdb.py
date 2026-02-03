from collections.abc import Generator

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


@pytest.fixture
def setup_table(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query("REMOVE TABLE IF EXISTS session_txn_test;")
    blocking_ws_connection.query("DEFINE TABLE session_txn_test SCHEMALESS;")
    yield
    blocking_ws_connection.query("REMOVE TABLE IF EXISTS session_txn_test;")


def test_attach_returns_uuid(
    blocking_ws_connection: BlockingWsSurrealConnection,
    setup_table: None,
) -> None:
    session_id = blocking_ws_connection.attach()
    assert session_id is not None
    assert str(session_id) != ""


def test_new_session_use_query_create_select(
    blocking_ws_connection: BlockingWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = blocking_ws_connection.new_session()
    session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    result = session.query("SELECT * FROM session_txn_test;")
    assert isinstance(result, list)
    assert len(result) == 0

    session.create(
        "session_txn_test:one",
        {"name": "session-created", "value": 1},
    )

    selected = session.select("session_txn_test:one")
    assert selected is not None
    if isinstance(selected, list) and len(selected) >= 1:
        rec = selected[0] if isinstance(selected[0], dict) else selected
    else:
        rec = selected if isinstance(selected, dict) else []
    assert isinstance(rec, dict)
    assert rec.get("name") == "session-created"
    assert rec.get("value") == 1

    session.close_session()


def test_two_sessions_isolated(
    blocking_ws_connection: BlockingWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session_a = blocking_ws_connection.new_session()
    session_a.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    session_b = blocking_ws_connection.new_session()
    session_b.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )

    session_a.create(
        "session_txn_test:from_a",
        {"name": "from-session-a"},
    )
    session_b.create(
        "session_txn_test:from_b",
        {"name": "from-session-b"},
    )

    session_a.let(
        "var",
        123,
    )
    session_b.let(
        "var",
        456,
    )

    res_a = session_a.query("RETURN $var;")
    res_b = session_b.query("RETURN $var;")
    assert isinstance(res_a, int)
    assert isinstance(res_b, int)
    assert res_a == [123]
    assert res_b == [456]

    session_a.close_session()
    session_b.close_session()
