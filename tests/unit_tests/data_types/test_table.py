from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.table import Table


# Unit tests for Table class
def test_table_init() -> None:
    """Test Table initialization."""
    table = Table("users")
    assert table.table_name == "users"


def test_table_str() -> None:
    """Test Table string representation."""
    table = Table("users")
    assert str(table) == "users"


def test_table_equality() -> None:
    """Test Table equality."""
    table1 = Table("users")
    table2 = Table("users")
    table3 = Table("posts")

    assert table1 == table2
    assert table1 != table3
    assert table1 != "users"


# Unit tests for encoding
def test_table_encode() -> None:
    """Test encoding Table to CBOR bytes."""
    table = Table("users")
    encoded = cbor.encode(table)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_table_with_special_chars_encode() -> None:
    """Test encoding Table with special characters to CBOR bytes."""
    table = Table("user_profiles")
    encoded = cbor.encode(table)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_table_decode() -> None:
    """Test decoding CBOR bytes to Table."""
    table = Table("users")
    encoded = cbor.encode(table)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, Table)
    assert decoded == table


def test_table_with_special_chars_decode() -> None:
    """Test decoding CBOR bytes to Table with special characters."""
    table = Table("user_profiles")
    encoded = cbor.encode(table)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, Table)
    assert decoded.table_name == "user_profiles"


# Encode+decode roundtrip tests
def test_table_roundtrip() -> None:
    """Test encode+decode roundtrip for Table."""
    test_tables = [
        Table("users"),
        Table("posts"),
        Table("comments"),
        Table("user_profiles"),
        Table("blog_posts"),
        Table("events123"),
    ]

    for table in test_tables:
        encoded = cbor.encode(table)
        decoded = cbor.decode(encoded)
        assert decoded == table
        assert isinstance(decoded, Table)
        assert decoded.table_name == table.table_name


def test_table_in_object_roundtrip() -> None:
    """Test encode+decode roundtrip for Table in an object."""
    test_obj = {
        "table1": Table("users"),
        "table2": Table("posts"),
    }
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded["table1"] == test_obj["table1"]
    assert decoded["table2"] == test_obj["table2"]


def test_table_in_array_roundtrip() -> None:
    """Test encode+decode roundtrip for Table in an array."""
    test_array = [
        Table("users"),
        Table("posts"),
        Table("comments"),
    ]
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
    await connection.query("DELETE table_tests;")
    yield connection
    await connection.query("DELETE table_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
@pytest.mark.xfail(reason="Waiting for a fix in SurrealDB")
async def test_table_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending Table to SurrealDB and receiving it back."""
    table = Table("users")
    await surrealdb_connection.query(
        "CREATE table_tests:test1 SET table_ref = $val;",
        vars={"val": table},
    )
    result = await surrealdb_connection.query("SELECT * FROM table_tests;")
    assert result[0]["table_ref"] == table


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Waiting for a fix in SurrealDB")
async def test_multiple_tables_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending multiple Table objects to SurrealDB."""
    tables = {
        "table1": Table("users"),
        "table2": Table("posts"),
        "table3": Table("comments"),
    }
    await surrealdb_connection.query(
        "CREATE table_tests:test2 SET t1 = $table1, t2 = $table2, t3 = $table3;",
        vars=tables,
    )
    result = await surrealdb_connection.query("SELECT * FROM table_tests;")
    assert result[0]["t1"] == tables["table1"]
    assert result[0]["t2"] == tables["table2"]
    assert result[0]["t3"] == tables["table3"]


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Waiting for a fix in SurrealDB")
async def test_table_in_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending array of Table objects to SurrealDB."""
    tables_array = [
        Table("users"),
        Table("posts"),
        Table("comments"),
    ]
    await surrealdb_connection.query(
        "CREATE table_tests:test3 SET tables = $val;",
        vars={"val": tables_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM table_tests;")
    assert result[0]["tables"] == tables_array
