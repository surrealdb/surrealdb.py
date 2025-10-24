from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor


# Unit tests for encoding
def test_string_encode() -> None:
    """Test encoding string to CBOR bytes."""
    test_string = "hello world"
    encoded = cbor.encode(test_string)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_empty_string_encode() -> None:
    """Test encoding empty string to CBOR bytes."""
    test_string = ""
    encoded = cbor.encode(test_string)
    assert isinstance(encoded, bytes)


def test_unicode_string_encode() -> None:
    """Test encoding unicode string to CBOR bytes."""
    test_string = "Hello 世界 🌍"
    encoded = cbor.encode(test_string)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_string_decode() -> None:
    """Test decoding CBOR bytes to string."""
    test_string = "hello world"
    encoded = cbor.encode(test_string)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, str)
    assert decoded == test_string


def test_unicode_string_decode() -> None:
    """Test decoding CBOR bytes to unicode string."""
    test_string = "Hello 世界 🌍"
    encoded = cbor.encode(test_string)
    decoded = cbor.decode(encoded)
    assert decoded == test_string


# Encode+decode roundtrip tests
def test_string_roundtrip() -> None:
    """Test encode+decode roundtrip for string."""
    test_strings = [
        "hello world",
        "",
        "a",
        "Unicode: 你好世界",
        "Emoji: 😀🎉🌟",
        "Special chars: \n\t\r\\",
        "Numbers as string: 12345",
        "Mixed: Hello123 世界!",
    ]

    for test_string in test_strings:
        encoded = cbor.encode(test_string)
        decoded = cbor.decode(encoded)
        assert decoded == test_string
        assert isinstance(decoded, str)


def test_long_string_roundtrip() -> None:
    """Test encode+decode roundtrip for long string."""
    test_string = "a" * 10000
    encoded = cbor.encode(test_string)
    decoded = cbor.decode(encoded)
    assert decoded == test_string


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
    await connection.query("DELETE string_tests;")
    yield connection
    await connection.query("DELETE string_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
async def test_string_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending string to SurrealDB and receiving it back."""
    test_string = "hello world"
    await surrealdb_connection.query(
        "CREATE string_tests:test1 SET value = $val;",
        vars={"val": test_string},
    )
    result = await surrealdb_connection.query("SELECT * FROM string_tests;")
    assert result[0]["value"] == test_string


@pytest.mark.asyncio
async def test_empty_string_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending empty string to SurrealDB and receiving it back."""
    test_string = ""
    await surrealdb_connection.query(
        "CREATE string_tests:test2 SET value = $val;",
        vars={"val": test_string},
    )
    result = await surrealdb_connection.query("SELECT * FROM string_tests;")
    assert result[0]["value"] == test_string


@pytest.mark.asyncio
async def test_unicode_string_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending unicode string to SurrealDB and receiving it back."""
    test_string = "Hello 世界 🌍"
    await surrealdb_connection.query(
        "CREATE string_tests:test3 SET value = $val;",
        vars={"val": test_string},
    )
    result = await surrealdb_connection.query("SELECT * FROM string_tests;")
    assert result[0]["value"] == test_string


@pytest.mark.asyncio
async def test_multiline_string_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending multiline string to SurrealDB and receiving it back."""
    test_string = "Line 1\nLine 2\nLine 3"
    await surrealdb_connection.query(
        "CREATE string_tests:test4 SET value = $val;",
        vars={"val": test_string},
    )
    result = await surrealdb_connection.query("SELECT * FROM string_tests;")
    assert result[0]["value"] == test_string
