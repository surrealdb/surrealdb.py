import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor


# Unit tests for encoding
def test_true_encode():
    """Test encoding True to CBOR bytes."""
    encoded = cbor.encode(True)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_false_encode():
    """Test encoding False to CBOR bytes."""
    encoded = cbor.encode(False)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


# Unit tests for decoding
def test_true_decode():
    """Test decoding CBOR bytes to True."""
    encoded = cbor.encode(True)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, bool)
    assert decoded is True


def test_false_decode():
    """Test decoding CBOR bytes to False."""
    encoded = cbor.encode(False)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, bool)
    assert decoded is False


# Encode+decode roundtrip tests
def test_boolean_roundtrip():
    """Test encode+decode roundtrip for boolean values."""
    for value in [True, False]:
        encoded = cbor.encode(value)
        decoded = cbor.decode(encoded)
        assert decoded is value
        assert isinstance(decoded, bool)


def test_boolean_in_list_roundtrip():
    """Test encode+decode roundtrip for booleans in a list."""
    test_list = [True, False, True, True, False]
    encoded = cbor.encode(test_list)
    decoded = cbor.decode(encoded)
    assert decoded == test_list


def test_boolean_in_dict_roundtrip():
    """Test encode+decode roundtrip for booleans in a dict."""
    test_dict = {
        "is_active": True,
        "is_deleted": False,
        "has_permission": True,
    }
    encoded = cbor.encode(test_dict)
    decoded = cbor.decode(encoded)
    assert decoded == test_dict


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
    await connection.query("DELETE boolean_tests;")
    yield connection
    await connection.query("DELETE boolean_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
async def test_true_db_roundtrip(surrealdb_connection):
    """Test sending True to SurrealDB and receiving it back."""
    await surrealdb_connection.query(
        "CREATE boolean_tests:test1 SET value = $val;",
        vars={"val": True},
    )
    result = await surrealdb_connection.query("SELECT * FROM boolean_tests;")
    assert result[0]["value"] is True


@pytest.mark.asyncio
async def test_false_db_roundtrip(surrealdb_connection):
    """Test sending False to SurrealDB and receiving it back."""
    await surrealdb_connection.query(
        "CREATE boolean_tests:test2 SET value = $val;",
        vars={"val": False},
    )
    result = await surrealdb_connection.query("SELECT * FROM boolean_tests;")
    assert result[0]["value"] is False


@pytest.mark.asyncio
async def test_boolean_fields_db_roundtrip(surrealdb_connection):
    """Test sending multiple boolean fields to SurrealDB and receiving them back."""
    await surrealdb_connection.query(
        "CREATE boolean_tests:test3 SET is_active = $active, is_admin = $admin, is_verified = $verified;",
        vars={"active": True, "admin": False, "verified": True},
    )
    result = await surrealdb_connection.query("SELECT * FROM boolean_tests;")
    assert result[0]["is_active"] is True
    assert result[0]["is_admin"] is False
    assert result[0]["is_verified"] is True
