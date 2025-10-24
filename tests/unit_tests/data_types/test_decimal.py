import decimal

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


@pytest.fixture
async def surrealdb_connection():
    url = "ws://localhost:8000/rpc"
    password = "root"
    username = "root"
    vars_params = {"username": username, "password": password}
    database_name = "test_db"
    namespace = "test_ns"
    connection = AsyncWsSurrealConnection(url)
    await connection.signin(vars_params)
    await connection.use(namespace=namespace, database=database_name)
    await connection.query("DELETE numeric_tests;")
    yield connection
    await connection.query("DELETE numeric_tests;")
    await connection.close()


@pytest.mark.asyncio
async def test_dec_literal(surrealdb_connection):
    await surrealdb_connection.query(
        "CREATE numeric_tests:literal_test SET value = 99.99dec;"
    )
    result = await surrealdb_connection.query("SELECT * FROM numeric_tests;")
    stored_value = result[0]["value"]
    assert str(stored_value) == "99.99"
    assert isinstance(stored_value, decimal.Decimal)

@pytest.mark.asyncio
async def test_float_parameter(surrealdb_connection):
    float_value = 3.141592653589793
    initial_result = await surrealdb_connection.query(
        "CREATE numeric_tests:float_test SET value = $float_val;",
        vars={"float_val": float_value},
    )
    assert isinstance(initial_result[0]["value"], float)
    assert initial_result[0]["value"] == 3.141592653589793
    second_result = await surrealdb_connection.query("SELECT * FROM numeric_tests;")
    assert isinstance(second_result[0]["value"], float)
    assert second_result[0]["value"] == 3.141592653589793

@pytest.mark.asyncio
async def test_decimal_parameter(surrealdb_connection):
    decimal_value = decimal.Decimal("3.141592653589793")
    initial_result = await surrealdb_connection.query(
        "CREATE numeric_tests:decimal_test SET value = $decimal_val;",
        vars={"decimal_val": decimal_value},
    )
    assert isinstance(initial_result[0]["value"], decimal.Decimal)
    assert initial_result[0]["value"] == decimal.Decimal("3.141592653589793")
    second_result = await surrealdb_connection.query("SELECT * FROM numeric_tests;")
    assert isinstance(second_result[0]["value"], decimal.Decimal)
    assert second_result[0]["value"] == decimal.Decimal("3.141592653589793")
