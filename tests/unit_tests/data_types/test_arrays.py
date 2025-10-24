from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor


# Unit tests for encoding
def test_empty_array_encode() -> None:
    """Test encoding empty array to CBOR bytes."""
    test_array = []
    encoded = cbor.encode(test_array)
    assert isinstance(encoded, bytes)


def test_simple_array_encode() -> None:
    """Test encoding simple array to CBOR bytes."""
    test_array = [1, 2, 3, 4, 5]
    encoded = cbor.encode(test_array)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_mixed_type_array_encode() -> None:
    """Test encoding array with mixed types to CBOR bytes."""
    test_array = [1, "hello", True, 3.14, None]
    encoded = cbor.encode(test_array)
    assert isinstance(encoded, bytes)


def test_nested_array_encode() -> None:
    """Test encoding nested array to CBOR bytes."""
    test_array = [[1, 2], [3, 4], [5, 6]]
    encoded = cbor.encode(test_array)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_empty_array_decode() -> None:
    """Test decoding CBOR bytes to empty array."""
    test_array = []
    encoded = cbor.encode(test_array)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, list)
    assert decoded == test_array


def test_simple_array_decode() -> None:
    """Test decoding CBOR bytes to simple array."""
    test_array = [1, 2, 3, 4, 5]
    encoded = cbor.encode(test_array)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, list)
    assert decoded == test_array


def test_nested_array_decode() -> None:
    """Test decoding CBOR bytes to nested array."""
    test_array = [[1, 2], [3, 4]]
    encoded = cbor.encode(test_array)
    decoded = cbor.decode(encoded)
    assert decoded == test_array


# Encode+decode roundtrip tests
def test_array_roundtrip() -> None:
    """Test encode+decode roundtrip for various arrays."""
    test_arrays = [
        [],
        [1],
        [1, 2, 3, 4, 5],
        ["a", "b", "c"],
        [True, False, True],
        [1.1, 2.2, 3.3],
        [1, "hello", True, 3.14, None],
    ]

    for test_array in test_arrays:
        encoded = cbor.encode(test_array)
        decoded = cbor.decode(encoded)
        assert decoded == test_array
        assert isinstance(decoded, list)


def test_nested_array_roundtrip() -> None:
    """Test encode+decode roundtrip for nested arrays."""
    test_arrays = [
        [[1, 2], [3, 4]],
        [["a"], ["b", "c"], ["d", "e", "f"]],
        [[[1]], [[2]], [[3]]],
        [[1, 2], ["a", "b"], [True, False]],
    ]

    for test_array in test_arrays:
        encoded = cbor.encode(test_array)
        decoded = cbor.decode(encoded)
        assert decoded == test_array


def test_deeply_nested_array_roundtrip() -> None:
    """Test encode+decode roundtrip for deeply nested arrays."""
    test_array = [[[[[1, 2, 3]]]]]
    encoded = cbor.encode(test_array)
    decoded = cbor.decode(encoded)
    assert decoded == test_array


def test_array_of_dicts_roundtrip() -> None:
    """Test encode+decode roundtrip for array of dictionaries."""
    test_array = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
    ]
    encoded = cbor.encode(test_array)
    decoded = cbor.decode(encoded)
    assert decoded == test_array


def test_large_array_roundtrip() -> None:
    """Test encode+decode roundtrip for large array."""
    test_array = list(range(1000))
    encoded = cbor.encode(test_array)
    decoded = cbor.decode(encoded)
    assert decoded == test_array


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
    await connection.query("DELETE array_tests;")
    yield connection
    await connection.query("DELETE array_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
async def test_empty_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending empty array to SurrealDB and receiving it back."""
    test_array = []
    await surrealdb_connection.query(
        "CREATE array_tests:test1 SET value = $val;",
        vars={"val": test_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM array_tests;")
    assert result[0]["value"] == test_array


@pytest.mark.asyncio
async def test_simple_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending simple array to SurrealDB and receiving it back."""
    test_array = [1, 2, 3, 4, 5]
    await surrealdb_connection.query(
        "CREATE array_tests:test2 SET value = $val;",
        vars={"val": test_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM array_tests;")
    assert result[0]["value"] == test_array


@pytest.mark.asyncio
async def test_string_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending string array to SurrealDB and receiving it back."""
    test_array = ["apple", "banana", "cherry"]
    await surrealdb_connection.query(
        "CREATE array_tests:test3 SET value = $val;",
        vars={"val": test_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM array_tests;")
    assert result[0]["value"] == test_array


@pytest.mark.asyncio
async def test_mixed_type_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending mixed type array to SurrealDB and receiving it back."""
    test_array = [1, "hello", True, 3.14]
    await surrealdb_connection.query(
        "CREATE array_tests:test4 SET value = $val;",
        vars={"val": test_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM array_tests;")
    assert result[0]["value"] == test_array


@pytest.mark.asyncio
async def test_nested_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending nested array to SurrealDB and receiving it back."""
    test_array = [[1, 2], [3, 4], [5, 6]]
    await surrealdb_connection.query(
        "CREATE array_tests:test5 SET value = $val;",
        vars={"val": test_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM array_tests;")
    assert result[0]["value"] == test_array


@pytest.mark.asyncio
async def test_array_of_objects_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending array of objects to SurrealDB and receiving it back."""
    test_array = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    await surrealdb_connection.query(
        "CREATE array_tests:test6 SET value = $val;",
        vars={"val": test_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM array_tests;")
    assert result[0]["value"] == test_array
