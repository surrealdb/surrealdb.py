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


def test_transaction_commit(
    blocking_ws_connection: BlockingWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = blocking_ws_connection.new_session()
    session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    txn = session.begin_transaction()

    txn.create(
        "session_txn_test:committed",
        {"name": "txn-commit", "value": 42},
    )

    before_commit = session.query(
        "SELECT * FROM session_txn_test WHERE id = session_txn_test:committed;",
    )
    assert isinstance(before_commit, list)
    assert len(before_commit) == 0

    txn.commit()

    after_commit = session.query(
        "SELECT * FROM session_txn_test WHERE id = session_txn_test:committed;",
    )
    assert isinstance(after_commit, list)
    assert len(after_commit) == 1
    assert after_commit[0].get("name") == "txn-commit"
    assert after_commit[0].get("value") == 42

    session.close_session()


def test_transaction_cancel(
    blocking_ws_connection: BlockingWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = blocking_ws_connection.new_session()
    session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    txn = session.begin_transaction()

    txn.create(
        "session_txn_test:cancelled",
        {"name": "txn-cancel", "value": 99},
    )

    txn.cancel()

    after_cancel = session.query(
        "SELECT * FROM session_txn_test WHERE id = session_txn_test:cancelled;",
    )
    assert isinstance(after_cancel, list)
    assert len(after_cancel) == 0

    session.close_session()


def test_transaction_query_select(
    blocking_ws_connection: BlockingWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = blocking_ws_connection.new_session()
    session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    txn = session.begin_transaction()

    txn.create(
        "session_txn_test:txn_query",
        {"name": "txn-query", "value": 1},
    )
    result = txn.query("SELECT * FROM session_txn_test:txn_query;")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].get("name") == "txn-query"

    selected = txn.select("session_txn_test:txn_query")
    assert selected is not None
    assert selected.get("name") == "txn-query"

    txn.commit()
    session.close_session()
