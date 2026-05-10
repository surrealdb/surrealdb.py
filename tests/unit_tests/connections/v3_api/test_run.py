"""
Tests for the new ``run()`` method (RPC ``run``).
"""

from collections.abc import AsyncGenerator, Generator

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection


@pytest.fixture(autouse=True)
async def _async_setup(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query(
        "DEFINE FUNCTION OVERWRITE fn::add($a: int, $b: int) {"
        "    RETURN $a + $b;"
        "}"
    )
    yield
    await async_ws_connection.query("REMOVE FUNCTION fn::add;")


@pytest.fixture(autouse=True)
def _sync_setup(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query(
        "DEFINE FUNCTION OVERWRITE fn::greet($name: string) {"
        "    RETURN 'hello ' + $name;"
        "}"
    ).execute()
    yield
    blocking_ws_connection.query("REMOVE FUNCTION fn::greet;").execute()


@pytest.mark.asyncio
async def test_async_run_with_args(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    out = await async_ws_connection.run("fn::add", [2, 3])
    assert out == 5


def test_sync_run_with_args(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    out = blocking_ws_connection.run("fn::greet", ["world"])
    assert out == "hello world"
