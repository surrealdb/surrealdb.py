from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor


# Unit tests for encoding
def test_empty_object_encode() -> None:
    """Test encoding empty object to CBOR bytes."""
    test_obj = {}
    encoded = cbor.encode(test_obj)
    assert isinstance(encoded, bytes)


def test_simple_object_encode() -> None:
    """Test encoding simple object to CBOR bytes."""
    test_obj = {"name": "John", "age": 30}
    encoded = cbor.encode(test_obj)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_nested_object_encode() -> None:
    """Test encoding nested object to CBOR bytes."""
    test_obj = {
        "user": {"name": "John", "address": {"city": "New York", "zip": "10001"}}
    }
    encoded = cbor.encode(test_obj)
    assert isinstance(encoded, bytes)


def test_object_with_mixed_types_encode() -> None:
    """Test encoding object with mixed value types to CBOR bytes."""
    test_obj = {
        "string": "hello",
        "number": 42,
        "float": 3.14,
        "boolean": True,
        "null": None,
        "array": [1, 2, 3],
    }
    encoded = cbor.encode(test_obj)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_empty_object_decode() -> None:
    """Test decoding CBOR bytes to empty object."""
    test_obj = {}
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, dict)
    assert decoded == test_obj


def test_simple_object_decode() -> None:
    """Test decoding CBOR bytes to simple object."""
    test_obj = {"name": "John", "age": 30}
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, dict)
    assert decoded == test_obj


def test_nested_object_decode() -> None:
    """Test decoding CBOR bytes to nested object."""
    test_obj = {"user": {"name": "John", "address": {"city": "New York"}}}
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded == test_obj


# Encode+decode roundtrip tests
def test_object_roundtrip() -> None:
    """Test encode+decode roundtrip for various objects."""
    test_objects = [
        {},
        {"a": 1},
        {"name": "Alice", "age": 25},
        {"x": 1, "y": 2, "z": 3},
        {"string": "hello", "number": 42, "boolean": True},
    ]

    for test_obj in test_objects:
        encoded = cbor.encode(test_obj)
        decoded = cbor.decode(encoded)
        assert decoded == test_obj
        assert isinstance(decoded, dict)


def test_nested_object_roundtrip() -> None:
    """Test encode+decode roundtrip for nested objects."""
    test_objects = [
        {"a": {"b": 1}},
        {"user": {"name": "John", "age": 30}},
        {"level1": {"level2": {"level3": "deep"}}},
        {
            "user": {
                "name": "Alice",
                "contact": {"email": "alice@example.com", "phone": "123-456-7890"},
            }
        },
    ]

    for test_obj in test_objects:
        encoded = cbor.encode(test_obj)
        decoded = cbor.decode(encoded)
        assert decoded == test_obj


def test_object_with_array_values_roundtrip() -> None:
    """Test encode+decode roundtrip for object with array values."""
    test_obj = {
        "numbers": [1, 2, 3],
        "strings": ["a", "b", "c"],
        "mixed": [1, "hello", True],
    }
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded == test_obj


def test_complex_nested_structure_roundtrip() -> None:
    """Test encode+decode roundtrip for complex nested structure."""
    test_obj = {
        "users": [
            {
                "id": 1,
                "name": "Alice",
                "tags": ["admin", "active"],
                "metadata": {"role": "admin", "permissions": ["read", "write"]},
            },
            {
                "id": 2,
                "name": "Bob",
                "tags": ["user"],
                "metadata": {"role": "user", "permissions": ["read"]},
            },
        ],
        "settings": {"theme": "dark", "notifications": {"email": True, "push": False}},
    }
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded == test_obj


def test_object_with_special_characters_in_keys_roundtrip() -> None:
    """Test encode+decode roundtrip for object with special characters in keys."""
    test_obj = {
        "key-with-dash": 1,
        "key_with_underscore": 2,
        "key.with.dot": 3,
        "key with space": 4,
    }
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded == test_obj


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
    await connection.query("DELETE object_tests;")
    yield connection
    await connection.query("DELETE object_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
async def test_empty_object_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending empty object to SurrealDB and receiving it back."""
    test_obj = {}
    await surrealdb_connection.query(
        "CREATE object_tests:test1 SET value = $val;",
        vars={"val": test_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM object_tests;")
    assert result[0]["value"] == test_obj


@pytest.mark.asyncio
async def test_simple_object_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending simple object to SurrealDB and receiving it back."""
    test_obj = {"name": "John", "age": 30}
    await surrealdb_connection.query(
        "CREATE object_tests:test2 SET value = $val;",
        vars={"val": test_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM object_tests;")
    assert result[0]["value"] == test_obj


@pytest.mark.asyncio
async def test_nested_object_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending nested object to SurrealDB and receiving it back."""
    test_obj = {"user": {"name": "Alice", "contact": {"email": "alice@example.com"}}}
    await surrealdb_connection.query(
        "CREATE object_tests:test3 SET value = $val;",
        vars={"val": test_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM object_tests;")
    assert result[0]["value"] == test_obj


@pytest.mark.asyncio
async def test_object_with_mixed_types_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending object with mixed types to SurrealDB and receiving it back."""
    test_obj = {
        "string": "hello",
        "number": 42,
        "float": 3.14,
        "boolean": True,
        "array": [1, 2, 3],
    }
    await surrealdb_connection.query(
        "CREATE object_tests:test4 SET value = $val;",
        vars={"val": test_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM object_tests;")
    assert result[0]["value"] == test_obj


@pytest.mark.asyncio
async def test_object_with_arrays_and_nested_objects_db_roundtrip(
    surrealdb_connection: Any,
) -> None:
    """Test sending complex nested structure to SurrealDB and receiving it back."""
    test_obj = {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ],
        "settings": {"theme": "dark", "notifications": True},
    }
    await surrealdb_connection.query(
        "CREATE object_tests:test5 SET value = $val;",
        vars={"val": test_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM object_tests;")
    assert result[0]["value"] == test_obj


@pytest.mark.asyncio
async def test_top_level_object_fields_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending object fields at top level to SurrealDB."""
    await surrealdb_connection.query(
        "CREATE object_tests:test6 SET name = $name, age = $age, active = $active;",
        vars={"name": "Charlie", "age": 35, "active": True},
    )
    result = await surrealdb_connection.query("SELECT * FROM object_tests;")
    assert result[0]["name"] == "Charlie"
    assert result[0]["age"] == 35
    assert result[0]["active"] is True
