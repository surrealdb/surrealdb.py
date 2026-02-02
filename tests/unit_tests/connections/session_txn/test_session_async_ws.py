from collections.abc import AsyncGenerator

import pytest

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
async def test_attach_returns_uuid(
    async_ws_connection: AsyncWsSurrealConnection,
    setup_table: None,
) -> None:
    session_id = await async_ws_connection.attach()
    assert session_id is not None
    assert str(session_id) != ""


@pytest.mark.asyncio
async def test_new_session_use_query_create_select(
    async_ws_connection: AsyncWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session = await async_ws_connection.new_session()
    await session.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    result = await session.query("SELECT * FROM session_txn_test;")
    assert isinstance(result, list)
    assert len(result) == 0

    await session.create(
        "session_txn_test:one",
        {"name": "session-created", "value": 1},
    )

    selected = await session.select("session_txn_test:one")
    assert selected is not None
    if isinstance(selected, list) and len(selected) >= 1:
        rec = selected[0] if isinstance(selected[0], dict) else selected
    else:
        rec = selected if isinstance(selected, dict) else []
    assert isinstance(rec, dict)
    assert rec.get("name") == "session-created"
    assert rec.get("value") == 1

    await session.close_session()


@pytest.mark.asyncio
async def test_two_sessions_isolated(
    async_ws_connection: AsyncWsSurrealConnection,
    connection_params: dict,
    setup_table: None,
) -> None:
    session_a = await async_ws_connection.new_session()
    await session_a.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )
    session_b = await async_ws_connection.new_session()
    await session_b.use(
        connection_params["namespace"],
        connection_params["database_name"],
    )

    await session_a.let(
        "var",
        123,
    )
    await session_b.let(
        "var",
        456,
    )

    res_a = await session_a.query("RETURN $var;")
    res_b = await session_b.query("RETURN $var;")
    assert isinstance(res_a, int)
    assert isinstance(res_b, int)
    assert res_a == [123]
    assert res_b == [456]

    await session_a.close_session()
    await session_b.close_session()
