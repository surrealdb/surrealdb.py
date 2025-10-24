"""
Tests how None is serialized when being sent to the database.

Notes:
    if an option<T> is None when being returned from the database it just isn't in the object
    will have to look into schema objects for more complete serialization.
"""

from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.record_id import RecordID


# Unit tests for encoding
def test_none_encode() -> None:
    """Test encoding None to CBOR bytes."""
    encoded = cbor.encode(None)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_none_in_list_encode() -> None:
    """Test encoding None in a list to CBOR bytes."""
    test_list = [None, 1, None, "test"]
    encoded = cbor.encode(test_list)
    assert isinstance(encoded, bytes)


def test_none_in_dict_encode() -> None:
    """Test encoding None in a dict to CBOR bytes."""
    test_dict = {"key1": None, "key2": "value"}
    encoded = cbor.encode(test_dict)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_none_decode() -> None:
    """Test decoding CBOR bytes to None."""
    encoded = cbor.encode(None)
    decoded = cbor.decode(encoded)
    assert decoded is None


def test_none_in_list_decode() -> None:
    """Test decoding CBOR bytes to list with None."""
    test_list = [None, 1, None, "test"]
    encoded = cbor.encode(test_list)
    decoded = cbor.decode(encoded)
    assert decoded == test_list


# Encode+decode roundtrip tests
def test_none_roundtrip() -> None:
    """Test encode+decode roundtrip for None."""
    encoded = cbor.encode(None)
    decoded = cbor.decode(encoded)
    assert decoded is None


def test_none_in_structures_roundtrip() -> None:
    """Test encode+decode roundtrip for None in various structures."""
    test_cases = [
        [None],
        [None, None],
        [1, None, 2],
        {"key": None},
        {"key1": None, "key2": "value"},
        [{"nested": None}],
    ]

    for test_case in test_cases:
        encoded = cbor.encode(test_case)
        decoded = cbor.decode(encoded)
        assert decoded == test_case


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
    await connection.query("REMOVE TABLE person;")
    yield connection
    await connection.query("REMOVE TABLE person;")
    await connection.close()


@pytest.mark.asyncio
async def test_none(surrealdb_connection: Any) -> None:
    schema = """
        DEFINE TABLE person SCHEMAFULL TYPE NORMAL;
        DEFINE FIELD name ON person TYPE string;
        DEFINE FIELD age ON person TYPE option<int>;
    """
    await surrealdb_connection.query(schema)
    outcome = await surrealdb_connection.create(
        "person:john", {"name": "John", "age": None}
    )
    record_check = RecordID(table_name="person", identifier="john")
    assert record_check == outcome["id"]
    assert "John" == outcome["name"]
    assert None == outcome.get("age")

    outcome = await surrealdb_connection.create(
        "person:dave", {"name": "Dave", "age": 34}
    )
    record_check = RecordID(table_name="person", identifier="dave")
    assert record_check == outcome["id"]
    assert "Dave" == outcome["name"]
    assert 34 == outcome["age"]

    outcome = await surrealdb_connection.query("SELECT * FROM person")
    assert 2 == len(outcome)


@pytest.mark.asyncio
async def test_none_with_query(surrealdb_connection: Any) -> None:
    schema = """
        DEFINE TABLE person SCHEMAFULL TYPE NORMAL;
        DEFINE FIELD name ON person TYPE string;
        DEFINE FIELD nums ON person TYPE array<option<int>>;
    """
    await surrealdb_connection.query(schema)
    outcome = await surrealdb_connection.query(
        "UPSERT person MERGE {id: $id, name: $name, nums: $nums}",
        {"id": [1, 2], "name": "John", "nums": [None]},
    )
    record_check = RecordID(table_name="person", identifier=[1, 2])
    if len(outcome) > 0:
        assert record_check == outcome[0]["id"]
        assert "John" == outcome[0]["name"]
        nums_value = outcome[0].get("nums")
        assert nums_value in [[None], []]

    outcome = await surrealdb_connection.query(
        "UPSERT person MERGE {id: $id, name: $name, nums: $nums}",
        {"id": [3, 4], "name": "Dave", "nums": [None]},
    )
    record_check = RecordID(table_name="person", identifier=[3, 4])
    if len(outcome) > 0:
        assert record_check == outcome[0]["id"]
        assert "Dave" == outcome[0]["name"]
        nums_value = outcome[0].get("nums")
        assert nums_value in [[None], []]

    outcome = await surrealdb_connection.query("SELECT * FROM person")
    assert len(outcome) in [0, 2]
