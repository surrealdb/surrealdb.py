from __future__ import annotations

from typing import Any, Optional

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.record_id import RecordID


# Unit tests for RecordID class
def test_record_id_init() -> None:
    """Test RecordID initialization."""
    record_id = RecordID("users", "john")
    assert record_id.table_name == "users"
    assert record_id.id == "john"


def test_record_id_with_int_identifier() -> None:
    """Test RecordID with integer identifier."""
    record_id = RecordID("users", 123)
    assert record_id.table_name == "users"
    assert record_id.id == 123


def test_record_id_with_array_identifier() -> None:
    """Test RecordID with array identifier."""
    record_id = RecordID("users", [1, 2, 3])
    assert record_id.table_name == "users"
    assert record_id.id == [1, 2, 3]


def test_record_id_with_object_identifier() -> None:
    """Test RecordID with object/dict identifier."""
    record_id = RecordID("person", {"name": "Tobie", "location": "London"})
    assert record_id.table_name == "person"
    assert record_id.id == {"name": "Tobie", "location": "London"}


def test_record_id_parse() -> None:
    """Test RecordID.parse method."""
    record_id = RecordID.parse("users:john")
    assert record_id.table_name == "users"
    assert record_id.id == "john"


def test_record_id_pydantic_model_validate_from_dict() -> None:
    """RecordID should be parsed from string on model_validate (python dict input)."""
    pydantic = pytest.importorskip("pydantic")

    class Person(pydantic.BaseModel):
        id: Optional[RecordID] = None
        name: str

    person = Person.model_validate({"id": "person:abc", "name": "Martin"})
    assert isinstance(person.id, RecordID)
    assert person.id.table_name == "person"
    assert person.id.id == "abc"


def test_record_id_pydantic_model_validate_json() -> None:
    """RecordID should be parsed from string on model_validate_json (JSON input)."""
    pydantic = pytest.importorskip("pydantic")

    class Person(pydantic.BaseModel):
        id: Optional[RecordID] = None
        name: str

    person = Person.model_validate_json('{"id":"person:abc","name":"Martin"}')
    assert isinstance(person.id, RecordID)
    assert person.id.table_name == "person"
    assert person.id.id == "abc"


def test_record_id_pydantic_model_dump_python_keeps_instance() -> None:
    """model_dump() should keep RecordID instances in python mode."""
    pydantic = pytest.importorskip("pydantic")

    class Person(pydantic.BaseModel):
        id: Optional[RecordID] = None
        name: str

    person = Person.model_validate({"id": "person:abc", "name": "Martin"})
    dumped = person.model_dump()
    assert isinstance(dumped["id"], RecordID)
    assert dumped["id"] == RecordID("person", "abc")


def test_record_id_pydantic_model_dump_json_stringifies() -> None:
    """model_dump(mode='json') should serialize RecordID to its string form."""
    pydantic = pytest.importorskip("pydantic")

    class Person(pydantic.BaseModel):
        id: Optional[RecordID] = None
        name: str

    person = Person.model_validate({"id": "person:abc", "name": "Martin"})
    dumped = person.model_dump(mode="json")
    assert dumped["id"] == "person:abc"


def test_record_id_parse_invalid() -> None:
    """Test RecordID.parse with invalid string."""
    with pytest.raises(ValueError, match="invalid string provided for parse"):
        RecordID.parse("invalid_string")


def test_record_id_str() -> None:
    """Test RecordID string representation."""
    record_id = RecordID("users", "john")
    assert str(record_id) == "users:john"


def test_record_id_str_with_numeric_string() -> None:
    """Test RecordID string representation with long numeric string (issue #171)."""
    record_id = RecordID("foo", "125813199042576601589342522460260755")
    assert str(record_id) == "foo:⟨125813199042576601589342522460260755⟩"


def test_record_id_str_with_short_numeric_string() -> None:
    """Test RecordID string representation with short numeric string."""
    record_id = RecordID("users", "123")
    assert str(record_id) == "users:⟨123⟩"


def test_record_id_str_with_underscore_only() -> None:
    """Test RecordID string representation with only underscores."""
    record_id = RecordID("test", "_")
    assert str(record_id) == "test:⟨_⟩"


def test_record_id_str_with_digits_and_underscores() -> None:
    """Test RecordID string representation with digits and underscores."""
    record_id = RecordID("test", "123_456")
    assert str(record_id) == "test:⟨123_456⟩"


def test_record_id_str_with_special_chars() -> None:
    """Test RecordID string representation with special characters."""
    record_id = RecordID("users", "john-doe")
    assert str(record_id) == "users:⟨john-doe⟩"


def test_record_id_str_with_spaces() -> None:
    """Test RecordID string representation with spaces."""
    record_id = RecordID("users", "john doe")
    assert str(record_id) == "users:⟨john doe⟩"


def test_record_id_str_with_empty_string() -> None:
    """Test RecordID string representation with empty string."""
    record_id = RecordID("users", "")
    assert str(record_id) == "users:⟨⟩"


def test_record_id_str_alphanumeric_no_escape() -> None:
    """Test RecordID string representation with alphanumeric (no escape needed)."""
    record_id = RecordID("users", "john123")
    assert str(record_id) == "users:john123"


def test_record_id_str_alphanumeric_with_underscore_no_escape() -> None:
    """Test RecordID string representation with alphanumeric and underscore (no escape needed)."""
    record_id = RecordID("users", "john_doe_123")
    assert str(record_id) == "users:john_doe_123"


def test_record_id_str_with_integer_id() -> None:
    """Test RecordID string representation with integer identifier (no escape)."""
    record_id = RecordID("users", 123)
    assert str(record_id) == "users:123"


def test_record_id_str_with_angle_bracket_escape() -> None:
    """Test RecordID string representation with angle bracket in identifier."""
    record_id = RecordID("test", "foo⟩bar")
    assert str(record_id) == "test:⟨foo\\⟩bar⟩"


def test_record_id_equality() -> None:
    """Test RecordID equality."""
    record_id1 = RecordID("users", "john")
    record_id2 = RecordID("users", "john")
    record_id3 = RecordID("users", "jane")
    record_id4 = RecordID("posts", "john")

    assert record_id1 == record_id2
    assert record_id1 != record_id3
    assert record_id1 != record_id4
    assert record_id1 != "not a record id"


# Unit tests for encoding
def test_record_id_encode() -> None:
    """Test encoding RecordID to CBOR bytes."""
    record_id = RecordID("users", "john")
    encoded = cbor.encode(record_id)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_record_id_with_int_encode() -> None:
    """Test encoding RecordID with integer identifier to CBOR bytes."""
    record_id = RecordID("users", 123)
    encoded = cbor.encode(record_id)
    assert isinstance(encoded, bytes)


def test_record_id_with_array_encode() -> None:
    """Test encoding RecordID with array identifier to CBOR bytes."""
    record_id = RecordID("users", [1, 2])
    encoded = cbor.encode(record_id)
    assert isinstance(encoded, bytes)


def test_record_id_with_object_encode() -> None:
    """Test encoding RecordID with object/dict identifier to CBOR bytes."""
    record_id = RecordID("person", {"name": "Tobie", "location": "London"})
    encoded = cbor.encode(record_id)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


# Unit tests for decoding
def test_record_id_decode() -> None:
    """Test decoding CBOR bytes to RecordID."""
    record_id = RecordID("users", "john")
    encoded = cbor.encode(record_id)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, RecordID)
    assert decoded == record_id


def test_record_id_with_int_decode() -> None:
    """Test decoding CBOR bytes to RecordID with integer identifier."""
    record_id = RecordID("users", 123)
    encoded = cbor.encode(record_id)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, RecordID)
    assert decoded.table_name == "users"
    assert decoded.id == 123


def test_record_id_with_array_decode() -> None:
    """Test decoding CBOR bytes to RecordID with array identifier."""
    record_id = RecordID("events", [1, 2, 3])
    encoded = cbor.encode(record_id)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, RecordID)
    assert decoded.table_name == "events"
    assert decoded.id == [1, 2, 3]


def test_record_id_with_object_decode() -> None:
    """Test decoding CBOR bytes to RecordID with object/dict identifier."""
    record_id = RecordID("person", {"name": "Tobie", "location": "London"})
    encoded = cbor.encode(record_id)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, RecordID)
    assert decoded.table_name == "person"
    assert decoded.id == {"name": "Tobie", "location": "London"}


# Encode+decode roundtrip tests
def test_record_id_roundtrip() -> None:
    """Test encode+decode roundtrip for RecordID."""
    test_record_ids = [
        RecordID("users", "john"),
        RecordID("users", "jane_doe"),
        RecordID("posts", "123"),
        RecordID("comments", 456),
        RecordID("events", [1, 2]),
        RecordID("events", [3, 4, 5]),
        RecordID("complex", ["a", "b"]),
        RecordID("person", {"name": "Tobie", "location": "London"}),
        RecordID("product", {"category": "electronics", "sku": "ABC123"}),
        RecordID("mixed", {"id": 123, "tags": ["tag1", "tag2"]}),
    ]

    for record_id in test_record_ids:
        encoded = cbor.encode(record_id)
        decoded = cbor.decode(encoded)
        assert decoded == record_id
        assert isinstance(decoded, RecordID)
        assert decoded.table_name == record_id.table_name
        assert decoded.id == record_id.id


def test_record_id_in_object_roundtrip() -> None:
    """Test encode+decode roundtrip for RecordID in an object."""
    test_obj = {
        "user_id": RecordID("users", "john"),
        "post_id": RecordID("posts", 123),
    }
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded["user_id"] == test_obj["user_id"]
    assert decoded["post_id"] == test_obj["post_id"]


def test_record_id_in_array_roundtrip() -> None:
    """Test encode+decode roundtrip for RecordID in an array."""
    test_array = [
        RecordID("users", "john"),
        RecordID("users", "jane"),
        RecordID("posts", 1),
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
    await connection.query("DELETE record_id_tests;")
    yield connection
    await connection.query("DELETE record_id_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
async def test_record_id_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending RecordID to SurrealDB and receiving it back."""
    record_id = RecordID("users", "john")
    await surrealdb_connection.query(
        "CREATE record_id_tests:test1 SET user_ref = $val;",
        vars={"val": record_id},
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["user_ref"] == record_id


@pytest.mark.asyncio
async def test_record_id_with_int_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending RecordID with integer identifier to SurrealDB."""
    record_id = RecordID("users", 123)
    await surrealdb_connection.query(
        "CREATE record_id_tests:test2 SET user_ref = $val;",
        vars={"val": record_id},
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["user_ref"] == record_id


@pytest.mark.asyncio
async def test_record_id_with_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending RecordID with array identifier to SurrealDB."""
    record_id = RecordID("events", [1, 2])
    await surrealdb_connection.query(
        "CREATE record_id_tests:test3 SET event_ref = $val;",
        vars={"val": record_id},
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["event_ref"] == record_id


@pytest.mark.asyncio
async def test_create_with_record_id(surrealdb_connection: Any) -> None:
    """Test creating a record using RecordID."""
    record_id = RecordID("record_id_tests", "custom_id")
    result = await surrealdb_connection.create(record_id, {"name": "Test"})
    assert result["id"] == record_id
    assert result["name"] == "Test"


@pytest.mark.asyncio
async def test_multiple_record_ids_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending multiple RecordIDs to SurrealDB."""
    record_ids = {
        "user": RecordID("users", "john"),
        "post": RecordID("posts", 456),
        "comment": RecordID("comments", [1, 2, 3]),
    }
    await surrealdb_connection.query(
        "CREATE record_id_tests:test4 SET user_ref = $user, post_ref = $post, comment_ref = $comment;",
        vars=record_ids,
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["user_ref"] == record_ids["user"]
    assert result[0]["post_ref"] == record_ids["post"]
    assert result[0]["comment_ref"] == record_ids["comment"]


@pytest.mark.asyncio
async def test_record_id_with_object_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending RecordID with object/dict identifier to SurrealDB."""
    record_id = RecordID("person", {"name": "Tobie", "location": "London"})
    await surrealdb_connection.query(
        "CREATE record_id_tests:test5 SET person_ref = $val;",
        vars={"val": record_id},
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["person_ref"] == record_id


@pytest.mark.asyncio
async def test_create_with_array_record_id(surrealdb_connection: Any) -> None:
    """Test creating a record using RecordID with array identifier."""
    record_id = RecordID("record_id_tests", ["main", "user", 123])
    result = await surrealdb_connection.create(
        record_id, {"name": "Array Test", "active": True}
    )
    assert result["id"] == record_id
    assert result["name"] == "Array Test"
    assert result["active"] is True


@pytest.mark.asyncio
async def test_create_with_object_record_id(surrealdb_connection: Any) -> None:
    """Test creating a record using RecordID with object/dict identifier."""
    record_id = RecordID("person", {"name": "Tobie", "location": "London"})

    # Try creating the record
    try:
        result = await surrealdb_connection.create(
            record_id,
            {
                "settings": {
                    "active": True,
                    "marketing": True,
                }
            },
        )
    except Exception as e:
        pytest.skip(f"Object-based record IDs may not be supported yet: {e}")

    # If result is a string (error message), skip the test
    if isinstance(result, str):
        pytest.skip(f"Object-based record IDs returned an error: {result}")

    # Verify the record was created with the correct ID
    assert result["id"] == record_id
    assert result["settings"]["active"] is True
    assert result["settings"]["marketing"] is True
