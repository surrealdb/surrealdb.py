from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor


# Unit tests for encoding integers
def test_positive_int_encode() -> None:
    """Test encoding positive integer to CBOR bytes."""
    test_int = 42
    encoded = cbor.encode(test_int)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_negative_int_encode() -> None:
    """Test encoding negative integer to CBOR bytes."""
    test_int = -42
    encoded = cbor.encode(test_int)
    assert isinstance(encoded, bytes)


def test_zero_encode() -> None:
    """Test encoding zero to CBOR bytes."""
    encoded = cbor.encode(0)
    assert isinstance(encoded, bytes)


def test_large_int_encode() -> None:
    """Test encoding large integer to CBOR bytes."""
    test_int = 9999999999999999
    encoded = cbor.encode(test_int)
    assert isinstance(encoded, bytes)


# Unit tests for encoding floats
def test_float_encode() -> None:
    """Test encoding float to CBOR bytes."""
    test_float = 3.14159
    encoded = cbor.encode(test_float)
    assert isinstance(encoded, bytes)


def test_negative_float_encode() -> None:
    """Test encoding negative float to CBOR bytes."""
    test_float = -2.71828
    encoded = cbor.encode(test_float)
    assert isinstance(encoded, bytes)


# Unit tests for decoding integers
def test_positive_int_decode() -> None:
    """Test decoding CBOR bytes to positive integer."""
    test_int = 42
    encoded = cbor.encode(test_int)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, int)
    assert decoded == test_int


def test_negative_int_decode() -> None:
    """Test decoding CBOR bytes to negative integer."""
    test_int = -42
    encoded = cbor.encode(test_int)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, int)
    assert decoded == test_int


# Unit tests for decoding floats
def test_float_decode() -> None:
    """Test decoding CBOR bytes to float."""
    test_float = 3.14159
    encoded = cbor.encode(test_float)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, float)
    assert decoded == test_float


# Encode+decode roundtrip tests for integers
def test_int_roundtrip() -> None:
    """Test encode+decode roundtrip for various integers."""
    test_ints = [
        0,
        1,
        -1,
        42,
        -42,
        100,
        -100,
        1000000,
        -1000000,
        2**31 - 1,  # Max 32-bit signed int
        -(2**31),  # Min 32-bit signed int
        2**63 - 1,  # Max 64-bit signed int
        -(2**63),  # Min 64-bit signed int
    ]

    for test_int in test_ints:
        encoded = cbor.encode(test_int)
        decoded = cbor.decode(encoded)
        assert decoded == test_int
        assert isinstance(decoded, int)


# Encode+decode roundtrip tests for floats
def test_float_roundtrip() -> None:
    """Test encode+decode roundtrip for various floats."""
    test_floats = [
        0.0,
        1.0,
        -1.0,
        3.14159,
        -2.71828,
        0.001,
        -0.001,
        1234.5678,
        -9876.5432,
    ]

    for test_float in test_floats:
        encoded = cbor.encode(test_float)
        decoded = cbor.decode(encoded)
        assert decoded == test_float
        assert isinstance(decoded, float)


def test_mixed_numbers_in_list_roundtrip() -> None:
    """Test encode+decode roundtrip for mixed numbers in a list."""
    test_list = [1, 2.5, 3, -4.2, 0, 0.0, -1]
    encoded = cbor.encode(test_list)
    decoded = cbor.decode(encoded)
    assert decoded == test_list


def test_numbers_in_dict_roundtrip() -> None:
    """Test encode+decode roundtrip for numbers in a dict."""
    test_dict = {
        "count": 42,
        "price": 19.99,
        "discount": -5.0,
        "stock": 0,
    }
    encoded = cbor.encode(test_dict)
    decoded = cbor.decode(encoded)
    assert decoded == test_dict


# Database fixture
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
    await connection.query("DELETE number_tests;")
    yield connection
    await connection.query("DELETE number_tests;")
    await connection.close()


# Database send+receive tests for integers
@pytest.mark.asyncio
async def test_positive_int_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending positive integer to SurrealDB and receiving it back."""
    test_int = 42
    await surrealdb_connection.query(
        "CREATE number_tests:test1 SET value = $val;",
        vars={"val": test_int},
    )
    result = await surrealdb_connection.query("SELECT * FROM number_tests;")
    assert result[0]["value"] == test_int


@pytest.mark.asyncio
async def test_negative_int_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending negative integer to SurrealDB and receiving it back."""
    test_int = -42
    await surrealdb_connection.query(
        "CREATE number_tests:test2 SET value = $val;",
        vars={"val": test_int},
    )
    result = await surrealdb_connection.query("SELECT * FROM number_tests;")
    assert result[0]["value"] == test_int


@pytest.mark.asyncio
async def test_zero_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending zero to SurrealDB and receiving it back."""
    await surrealdb_connection.query(
        "CREATE number_tests:test3 SET value = $val;",
        vars={"val": 0},
    )
    result = await surrealdb_connection.query("SELECT * FROM number_tests;")
    assert result[0]["value"] == 0


@pytest.mark.asyncio
async def test_large_int_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending large integer to SurrealDB and receiving it back."""
    test_int = 9999999999999999
    await surrealdb_connection.query(
        "CREATE number_tests:test4 SET value = $val;",
        vars={"val": test_int},
    )
    result = await surrealdb_connection.query("SELECT * FROM number_tests;")
    assert result[0]["value"] == test_int


# Database send+receive tests for floats
@pytest.mark.asyncio
async def test_float_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending float to SurrealDB and receiving it back."""
    test_float = 3.14159
    await surrealdb_connection.query(
        "CREATE number_tests:test5 SET value = $val;",
        vars={"val": test_float},
    )
    result = await surrealdb_connection.query("SELECT * FROM number_tests;")
    assert result[0]["value"] == test_float


@pytest.mark.asyncio
async def test_negative_float_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending negative float to SurrealDB and receiving it back."""
    test_float = -2.71828
    await surrealdb_connection.query(
        "CREATE number_tests:test6 SET value = $val;",
        vars={"val": test_float},
    )
    result = await surrealdb_connection.query("SELECT * FROM number_tests;")
    assert result[0]["value"] == test_float


@pytest.mark.asyncio
async def test_mixed_numbers_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending mixed integer and float fields to SurrealDB."""
    await surrealdb_connection.query(
        "CREATE number_tests:test7 SET int_val = $int_val, float_val = $float_val;",
        vars={"int_val": 100, "float_val": 99.99},
    )
    result = await surrealdb_connection.query("SELECT * FROM number_tests;")
    assert result[0]["int_val"] == 100
    assert result[0]["float_val"] == 99.99
