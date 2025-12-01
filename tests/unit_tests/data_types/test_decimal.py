import decimal
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor


# Unit tests for encoding
def test_decimal_encode() -> None:
    """Test encoding Decimal to CBOR bytes."""
    test_decimal = decimal.Decimal("99.99")
    encoded = cbor.encode(test_decimal)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_decimal_with_precision_encode() -> None:
    """Test encoding Decimal with high precision to CBOR bytes."""
    test_decimal = decimal.Decimal("3.141592653589793")
    encoded = cbor.encode(test_decimal)
    assert isinstance(encoded, bytes)


def test_negative_decimal_encode() -> None:
    """Test encoding negative Decimal to CBOR bytes."""
    test_decimal = decimal.Decimal("-42.5")
    encoded = cbor.encode(test_decimal)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_decimal_decode() -> None:
    """Test decoding CBOR bytes to Decimal."""
    test_decimal = decimal.Decimal("99.99")
    encoded = cbor.encode(test_decimal)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, decimal.Decimal)
    assert decoded == test_decimal


def test_decimal_with_precision_decode() -> None:
    """Test decoding CBOR bytes to Decimal with high precision."""
    test_decimal = decimal.Decimal("3.141592653589793")
    encoded = cbor.encode(test_decimal)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, decimal.Decimal)
    assert decoded == test_decimal


# Encode+decode roundtrip tests
def test_decimal_roundtrip() -> None:
    """Test encode+decode roundtrip for various Decimal values."""
    test_decimals = [
        decimal.Decimal("0"),
        decimal.Decimal("1"),
        decimal.Decimal("-1"),
        decimal.Decimal("99.99"),
        decimal.Decimal("3.141592653589793"),
        decimal.Decimal("0.01"),
        decimal.Decimal("100"),
        decimal.Decimal("-42.5"),
        decimal.Decimal("0.0000001"),
        decimal.Decimal("-0.01"),
        decimal.Decimal("999999.99"),
    ]

    for test_decimal in test_decimals:
        encoded = cbor.encode(test_decimal)
        decoded = cbor.decode(encoded)
        assert isinstance(decoded, decimal.Decimal)
        assert decoded == test_decimal


def test_decimal_in_list_roundtrip() -> None:
    """Test encode+decode roundtrip for Decimal in a list."""
    test_list = [
        decimal.Decimal("1.5"),
        decimal.Decimal("2.5"),
        decimal.Decimal("3.5"),
    ]
    encoded = cbor.encode(test_list)
    decoded = cbor.decode(encoded)
    assert decoded == test_list


def test_decimal_in_dict_roundtrip() -> None:
    """Test encode+decode roundtrip for Decimal in a dict."""
    test_dict = {
        "price": decimal.Decimal("99.99"),
        "discount": decimal.Decimal("10.00"),
        "total": decimal.Decimal("89.99"),
    }
    encoded = cbor.encode(test_dict)
    decoded = cbor.decode(encoded)
    assert decoded == test_dict


@pytest.fixture
async def surrealdb_connection():  # type: ignore[misc]
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
async def test_dec_literal(surrealdb_connection: Any) -> None:
    await surrealdb_connection.query(
        "CREATE numeric_tests:literal_test SET value = 99.99dec;"
    )
    result = await surrealdb_connection.query("SELECT * FROM numeric_tests;")
    stored_value = result[0]["value"]
    assert str(stored_value) == "99.99"
    assert isinstance(stored_value, decimal.Decimal)


@pytest.mark.asyncio
async def test_float_parameter(surrealdb_connection: Any) -> None:
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
async def test_decimal_parameter(surrealdb_connection: Any) -> None:
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
