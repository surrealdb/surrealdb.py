from collections.abc import AsyncGenerator

import pytest

from surrealdb import UnexpectedResponseError
from surrealdb.connections.async_ws import AsyncWsSurrealConnection


@pytest.fixture
async def setup_table(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query("REMOVE TABLE IF EXISTS session_txn_test;")
    await async_ws_connection.query("DEFINE TABLE session_txn_test SCHEMALESS;")
    yield
    await async_ws_connection.query("REMOVE TABLE IF EXISTS session_txn_test;")


@pytest.mark.asyncio
async def test_transaction_commit(
    async_ws_connection: AsyncWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = await async_ws_connection.new_session()
    await session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    txn = await session.begin_transaction()

    await txn.create(
        "session_txn_test:committed",
        {"name": "txn-commit", "value": 42},
    )

    before_commit = await session.query(
        "SELECT * FROM session_txn_test WHERE id = session_txn_test:committed;"
    )
    assert isinstance(before_commit, list)
    assert len(before_commit) == 0

    await txn.commit()

    after_commit = await session.query(
        "SELECT * FROM session_txn_test WHERE id = session_txn_test:committed;"
    )
    assert isinstance(after_commit, list)
    assert len(after_commit) == 1
    assert after_commit[0].get("name") == "txn-commit"
    assert after_commit[0].get("value") == 42

    await session.close_session()


@pytest.mark.asyncio
async def test_transaction_cancel(
    async_ws_connection: AsyncWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = await async_ws_connection.new_session()
    await session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    txn = await session.begin_transaction()

    await txn.create(
        "session_txn_test:cancelled",
        {"name": "txn-cancel", "value": 99},
    )

    await txn.cancel()

    after_cancel = await session.query(
        "SELECT * FROM session_txn_test WHERE id = session_txn_test:cancelled;"
    )
    assert isinstance(after_cancel, list)
    assert len(after_cancel) == 0

    await session.close_session()


@pytest.mark.asyncio
async def test_transaction_query_select(
    async_ws_connection: AsyncWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = await async_ws_connection.new_session()
    await session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    txn = await session.begin_transaction()

    await txn.create(
        "session_txn_test:txn_query",
        {"name": "txn-query", "value": 1},
    )
    result = await txn.query("SELECT * FROM session_txn_test:txn_query;")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].get("name") == "txn-query"

    selected = await txn.select("session_txn_test:txn_query")
    assert selected is not None
    assert selected.get("name") == "txn-query"

    await txn.commit()
    await session.close_session()

@pytest.mark.asyncio
async def test_transaction_begin_uuid_v3(
        async_ws_connection: AsyncWsSurrealConnection,
        connection_params: dict,
        setup_table: None,
) -> None:
    session = await async_ws_connection.new_session()
    await session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    try:
        txn = await session.begin_transaction()
        await txn.commit()
    except UnexpectedResponseError:
        pytest.fail("UnexpectedResponseError on transaction start")
    await session.close_session()