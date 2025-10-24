import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.record_id import RecordID


# Unit tests for RecordID class
def test_record_id_init():
    """Test RecordID initialization."""
    record_id = RecordID("users", "john")
    assert record_id.table_name == "users"
    assert record_id.id == "john"


def test_record_id_with_int_identifier():
    """Test RecordID with integer identifier."""
    record_id = RecordID("users", 123)
    assert record_id.table_name == "users"
    assert record_id.id == 123


def test_record_id_with_array_identifier():
    """Test RecordID with array identifier."""
    record_id = RecordID("users", [1, 2, 3])
    assert record_id.table_name == "users"
    assert record_id.id == [1, 2, 3]


def test_record_id_parse():
    """Test RecordID.parse method."""
    record_id = RecordID.parse("users:john")
    assert record_id.table_name == "users"
    assert record_id.id == "john"


def test_record_id_parse_invalid():
    """Test RecordID.parse with invalid string."""
    with pytest.raises(ValueError, match="invalid string provided for parse"):
        RecordID.parse("invalid_string")


def test_record_id_str():
    """Test RecordID string representation."""
    record_id = RecordID("users", "john")
    assert str(record_id) == "users:john"


def test_record_id_equality():
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
def test_record_id_encode():
    """Test encoding RecordID to CBOR bytes."""
    record_id = RecordID("users", "john")
    encoded = cbor.encode(record_id)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_record_id_with_int_encode():
    """Test encoding RecordID with integer identifier to CBOR bytes."""
    record_id = RecordID("users", 123)
    encoded = cbor.encode(record_id)
    assert isinstance(encoded, bytes)


def test_record_id_with_array_encode():
    """Test encoding RecordID with array identifier to CBOR bytes."""
    record_id = RecordID("users", [1, 2])
    encoded = cbor.encode(record_id)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_record_id_decode():
    """Test decoding CBOR bytes to RecordID."""
    record_id = RecordID("users", "john")
    encoded = cbor.encode(record_id)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, RecordID)
    assert decoded == record_id


def test_record_id_with_int_decode():
    """Test decoding CBOR bytes to RecordID with integer identifier."""
    record_id = RecordID("users", 123)
    encoded = cbor.encode(record_id)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, RecordID)
    assert decoded.table_name == "users"
    assert decoded.id == 123


# Encode+decode roundtrip tests
def test_record_id_roundtrip():
    """Test encode+decode roundtrip for RecordID."""
    test_record_ids = [
        RecordID("users", "john"),
        RecordID("users", "jane_doe"),
        RecordID("posts", "123"),
        RecordID("comments", 456),
        RecordID("events", [1, 2]),
        RecordID("events", [3, 4, 5]),
        RecordID("complex", ["a", "b"]),
    ]

    for record_id in test_record_ids:
        encoded = cbor.encode(record_id)
        decoded = cbor.decode(encoded)
        assert decoded == record_id
        assert isinstance(decoded, RecordID)
        assert decoded.table_name == record_id.table_name
        assert decoded.id == record_id.id


def test_record_id_in_object_roundtrip():
    """Test encode+decode roundtrip for RecordID in an object."""
    test_obj = {
        "user_id": RecordID("users", "john"),
        "post_id": RecordID("posts", 123),
    }
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded["user_id"] == test_obj["user_id"]
    assert decoded["post_id"] == test_obj["post_id"]


def test_record_id_in_array_roundtrip():
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
    await connection.query("DELETE record_id_tests;")
    yield connection
    await connection.query("DELETE record_id_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
async def test_record_id_db_roundtrip(surrealdb_connection):
    """Test sending RecordID to SurrealDB and receiving it back."""
    record_id = RecordID("users", "john")
    await surrealdb_connection.query(
        "CREATE record_id_tests:test1 SET user_ref = $val;",
        vars={"val": record_id},
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["user_ref"] == record_id


@pytest.mark.asyncio
async def test_record_id_with_int_db_roundtrip(surrealdb_connection):
    """Test sending RecordID with integer identifier to SurrealDB."""
    record_id = RecordID("users", 123)
    await surrealdb_connection.query(
        "CREATE record_id_tests:test2 SET user_ref = $val;",
        vars={"val": record_id},
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["user_ref"] == record_id


@pytest.mark.asyncio
async def test_record_id_with_array_db_roundtrip(surrealdb_connection):
    """Test sending RecordID with array identifier to SurrealDB."""
    record_id = RecordID("events", [1, 2])
    await surrealdb_connection.query(
        "CREATE record_id_tests:test3 SET event_ref = $val;",
        vars={"val": record_id},
    )
    result = await surrealdb_connection.query("SELECT * FROM record_id_tests;")
    assert result[0]["event_ref"] == record_id


@pytest.mark.asyncio
async def test_create_with_record_id(surrealdb_connection):
    """Test creating a record using RecordID."""
    record_id = RecordID("record_id_tests", "custom_id")
    result = await surrealdb_connection.create(record_id, {"name": "Test"})
    assert result["id"] == record_id
    assert result["name"] == "Test"


@pytest.mark.asyncio
async def test_multiple_record_ids_db_roundtrip(surrealdb_connection):
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
