from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.range import BoundExcluded, BoundIncluded, Range


# Unit tests for Bound classes
def test_bound_included_init() -> None:
    """Test BoundIncluded initialization."""
    bound = BoundIncluded(5)
    assert bound.value == 5


def test_bound_excluded_init() -> None:
    """Test BoundExcluded initialization."""
    bound = BoundExcluded(10)
    assert bound.value == 10


def test_bound_included_equality() -> None:
    """Test BoundIncluded equality."""
    bound1 = BoundIncluded(5)
    bound2 = BoundIncluded(5)
    bound3 = BoundIncluded(10)

    assert bound1 == bound2
    assert bound1 != bound3
    assert bound1 != 5


def test_bound_excluded_equality() -> None:
    """Test BoundExcluded equality."""
    bound1 = BoundExcluded(5)
    bound2 = BoundExcluded(5)
    bound3 = BoundExcluded(10)

    assert bound1 == bound2
    assert bound1 != bound3
    assert bound1 != 5


def test_bound_types_not_equal() -> None:
    """Test that BoundIncluded and BoundExcluded with same value are not equal."""
    bound_inc = BoundIncluded(5)
    bound_exc = BoundExcluded(5)

    assert bound_inc != bound_exc


# Unit tests for Range class
def test_range_init() -> None:
    """Test Range initialization."""
    range_obj = Range(BoundIncluded(1), BoundIncluded(10))
    assert isinstance(range_obj.begin, BoundIncluded)
    assert isinstance(range_obj.end, BoundIncluded)
    assert range_obj.begin.value == 1
    assert range_obj.end.value == 10


def test_range_with_excluded_bounds() -> None:
    """Test Range with excluded bounds."""
    range_obj = Range(BoundExcluded(0), BoundExcluded(100))
    assert isinstance(range_obj.begin, BoundExcluded)
    assert isinstance(range_obj.end, BoundExcluded)


def test_range_with_mixed_bounds() -> None:
    """Test Range with mixed bound types."""
    range_obj = Range(BoundIncluded(1), BoundExcluded(10))
    assert isinstance(range_obj.begin, BoundIncluded)
    assert isinstance(range_obj.end, BoundExcluded)


def test_range_equality() -> None:
    """Test Range equality."""
    range1 = Range(BoundIncluded(1), BoundIncluded(10))
    range2 = Range(BoundIncluded(1), BoundIncluded(10))
    range3 = Range(BoundIncluded(1), BoundExcluded(10))
    range4 = Range(BoundIncluded(2), BoundIncluded(10))

    assert range1 == range2
    assert range1 != range3
    assert range1 != range4


# Unit tests for encoding
def test_bound_included_encode() -> None:
    """Test encoding BoundIncluded to CBOR bytes."""
    bound = BoundIncluded(5)
    encoded = cbor.encode(bound)
    assert isinstance(encoded, bytes)


def test_bound_excluded_encode() -> None:
    """Test encoding BoundExcluded to CBOR bytes."""
    bound = BoundExcluded(10)
    encoded = cbor.encode(bound)
    assert isinstance(encoded, bytes)


def test_range_encode() -> None:
    """Test encoding Range to CBOR bytes."""
    range_obj = Range(BoundIncluded(1), BoundIncluded(10))
    encoded = cbor.encode(range_obj)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


# Unit tests for decoding
def test_bound_included_decode() -> None:
    """Test decoding CBOR bytes to BoundIncluded."""
    bound = BoundIncluded(5)
    encoded = cbor.encode(bound)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, BoundIncluded)
    assert decoded == bound


def test_bound_excluded_decode() -> None:
    """Test decoding CBOR bytes to BoundExcluded."""
    bound = BoundExcluded(10)
    encoded = cbor.encode(bound)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, BoundExcluded)
    assert decoded == bound


def test_range_decode() -> None:
    """Test decoding CBOR bytes to Range."""
    range_obj = Range(BoundIncluded(1), BoundIncluded(10))
    encoded = cbor.encode(range_obj)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, Range)
    assert decoded == range_obj


# Encode+decode roundtrip tests
def test_bound_included_roundtrip() -> None:
    """Test encode+decode roundtrip for BoundIncluded."""
    test_bounds = [
        BoundIncluded(0),
        BoundIncluded(5),
        BoundIncluded(100),
        BoundIncluded(-10),
        BoundIncluded("a"),
        BoundIncluded("z"),
    ]

    for bound in test_bounds:
        encoded = cbor.encode(bound)
        decoded = cbor.decode(encoded)
        assert decoded == bound
        assert isinstance(decoded, BoundIncluded)


def test_bound_excluded_roundtrip() -> None:
    """Test encode+decode roundtrip for BoundExcluded."""
    test_bounds = [
        BoundExcluded(0),
        BoundExcluded(5),
        BoundExcluded(100),
        BoundExcluded(-10),
        BoundExcluded("a"),
        BoundExcluded("z"),
    ]

    for bound in test_bounds:
        encoded = cbor.encode(bound)
        decoded = cbor.decode(encoded)
        assert decoded == bound
        assert isinstance(decoded, BoundExcluded)


def test_range_roundtrip() -> None:
    """Test encode+decode roundtrip for Range."""
    test_ranges = [
        Range(BoundIncluded(1), BoundIncluded(10)),
        Range(BoundExcluded(0), BoundExcluded(100)),
        Range(BoundIncluded(1), BoundExcluded(10)),
        Range(BoundExcluded(0), BoundIncluded(100)),
        Range(BoundIncluded("a"), BoundIncluded("z")),
        Range(BoundIncluded(-100), BoundIncluded(100)),
    ]

    for range_obj in test_ranges:
        encoded = cbor.encode(range_obj)
        decoded = cbor.decode(encoded)
        assert decoded == range_obj
        assert isinstance(decoded, Range)
        assert isinstance(decoded.begin, type(range_obj.begin))
        assert isinstance(decoded.end, type(range_obj.end))


def test_range_in_object_roundtrip() -> None:
    """Test encode+decode roundtrip for Range in an object."""
    test_obj = {
        "range1": Range(BoundIncluded(1), BoundIncluded(10)),
        "range2": Range(BoundExcluded(0), BoundExcluded(100)),
    }
    encoded = cbor.encode(test_obj)
    decoded = cbor.decode(encoded)
    assert decoded["range1"] == test_obj["range1"]
    assert decoded["range2"] == test_obj["range2"]


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
    await connection.query("DELETE range_tests;")
    yield connection
    await connection.query("DELETE range_tests;")
    await connection.close()


# Database send+receive tests
@pytest.mark.asyncio
async def test_range_inclusive_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending Range with inclusive bounds to SurrealDB."""
    range_obj = Range(BoundIncluded(1), BoundIncluded(10))
    await surrealdb_connection.query(
        "CREATE range_tests:test1 SET range_val = $val;",
        vars={"val": range_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM range_tests;")
    assert result[0]["range_val"] == range_obj


@pytest.mark.asyncio
async def test_range_exclusive_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending Range with exclusive bounds to SurrealDB."""
    range_obj = Range(BoundExcluded(0), BoundExcluded(100))
    await surrealdb_connection.query(
        "CREATE range_tests:test2 SET range_val = $val;",
        vars={"val": range_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM range_tests;")
    assert result[0]["range_val"] == range_obj


@pytest.mark.asyncio
async def test_range_mixed_bounds_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending Range with mixed bounds to SurrealDB."""
    range_obj = Range(BoundIncluded(1), BoundExcluded(10))
    await surrealdb_connection.query(
        "CREATE range_tests:test3 SET range_val = $val;",
        vars={"val": range_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM range_tests;")
    assert result[0]["range_val"] == range_obj


@pytest.mark.asyncio
async def test_string_range_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending Range with string bounds to SurrealDB."""
    range_obj = Range(BoundIncluded("a"), BoundIncluded("z"))
    await surrealdb_connection.query(
        "CREATE range_tests:test4 SET range_val = $val;",
        vars={"val": range_obj},
    )
    result = await surrealdb_connection.query("SELECT * FROM range_tests;")
    assert result[0]["range_val"] == range_obj


@pytest.mark.asyncio
async def test_multiple_ranges_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending multiple Range objects to SurrealDB."""
    ranges = {
        "range1": Range(BoundIncluded(1), BoundIncluded(10)),
        "range2": Range(BoundExcluded(0), BoundExcluded(100)),
    }
    await surrealdb_connection.query(
        "CREATE range_tests:test5 SET r1 = $range1, r2 = $range2;",
        vars=ranges,
    )
    result = await surrealdb_connection.query("SELECT * FROM range_tests;")
    assert result[0]["r1"] == ranges["range1"]
    assert result[0]["r2"] == ranges["range2"]


@pytest.mark.asyncio
async def test_range_in_array_db_roundtrip(surrealdb_connection: Any) -> None:
    """Test sending array of Range objects to SurrealDB."""
    ranges_array = [
        Range(BoundIncluded(1), BoundIncluded(10)),
        Range(BoundExcluded(0), BoundExcluded(100)),
        Range(BoundIncluded("a"), BoundIncluded("z")),
    ]
    await surrealdb_connection.query(
        "CREATE range_tests:test6 SET ranges = $val;",
        vars={"val": ranges_array},
    )
    result = await surrealdb_connection.query("SELECT * FROM range_tests;")
    assert result[0]["ranges"] == ranges_array
