import datetime
import sys
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data import cbor
from surrealdb.data.types.datetime import Datetime


# Unit tests for encoding
def test_datetime_encode() -> None:
    """Test encoding datetime to CBOR bytes."""
    now = datetime.datetime.now(datetime.timezone.utc)
    encoded = cbor.encode(now)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0


def test_datetime_custom_encode() -> None:
    """Test encoding Datetime wrapper to CBOR bytes."""
    iso_datetime = "2025-02-03T12:30:45.123456Z"
    if sys.version_info < (3, 11):
        iso_datetime = iso_datetime.replace("Z", "+00:00")
    dt = Datetime(iso_datetime)
    encoded = cbor.encode(dt)
    assert isinstance(encoded, bytes)


def test_datetime_with_microseconds_encode() -> None:
    """Test encoding datetime with microseconds to CBOR bytes."""
    dt = datetime.datetime(2025, 1, 1, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc)
    encoded = cbor.encode(dt)
    assert isinstance(encoded, bytes)


# Unit tests for decoding
def test_datetime_decode() -> None:
    """Test decoding CBOR bytes to datetime."""
    now = datetime.datetime.now(datetime.timezone.utc)
    encoded = cbor.encode(now)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, datetime.datetime)
    # Compare timestamps as they might differ slightly in representation
    assert abs((decoded - now).total_seconds()) < 0.001


def test_datetime_with_microseconds_decode() -> None:
    """Test decoding CBOR bytes to datetime with microseconds."""
    dt = datetime.datetime(2025, 1, 1, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc)
    encoded = cbor.encode(dt)
    decoded = cbor.decode(encoded)
    assert isinstance(decoded, datetime.datetime)
    assert decoded == dt


# Encode+decode roundtrip tests
def test_datetime_roundtrip() -> None:
    """Test encode+decode roundtrip for datetime."""
    test_datetimes = [
        datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
        datetime.datetime(2025, 6, 15, 12, 30, 45, tzinfo=datetime.timezone.utc),
        datetime.datetime(2025, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc),
        datetime.datetime(2025, 1, 1, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc),
    ]

    for dt in test_datetimes:
        encoded = cbor.encode(dt)
        decoded = cbor.decode(encoded)
        assert isinstance(decoded, datetime.datetime)
        assert decoded == dt


def test_datetime_in_dict_roundtrip() -> None:
    """Test encode+decode roundtrip for datetime in a dict."""
    now = datetime.datetime.now(datetime.timezone.utc)
    test_dict = {
        "created_at": now,
        "name": "test",
    }
    encoded = cbor.encode(test_dict)
    decoded = cbor.decode(encoded)
    assert decoded["created_at"] == now
    assert decoded["name"] == "test"


def test_datetime_in_list_roundtrip() -> None:
    """Test encode+decode roundtrip for datetime in a list."""
    dt1 = datetime.datetime(2025, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    dt2 = datetime.datetime(2025, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    test_list = [dt1, dt2]
    encoded = cbor.encode(test_list)
    decoded = cbor.decode(encoded)
    assert decoded == test_list


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
    await connection.query("DELETE datetime_tests;")
    yield connection
    await connection.query("DELETE datetime_tests;")
    await connection.close()


@pytest.mark.asyncio
async def test_native_datetime(surrealdb_connection: Any) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    await surrealdb_connection.query(
        "CREATE datetime_tests:compact_test SET datetime = $compact_datetime;",
        vars={"compact_datetime": now},
    )
    compact_test_outcome = await surrealdb_connection.query(
        "SELECT * FROM datetime_tests;"
    )
    assert compact_test_outcome[0]["datetime"] == now
    outcome = compact_test_outcome[0]["datetime"]
    assert now.isoformat() == outcome.isoformat()


@pytest.mark.asyncio
async def test_datetime_iso_format(surrealdb_connection: Any) -> None:
    iso_datetime = "2025-02-03T12:30:45.123456Z"  # ISO 8601 datetime
    if sys.version_info < (3, 11):
        iso_datetime = iso_datetime.replace("Z", "+00:00")
    date = Datetime(iso_datetime)
    iso_datetime_obj = datetime.datetime.fromisoformat(iso_datetime)
    await surrealdb_connection.query(
        "CREATE datetime_tests:iso_tests SET datetime = $iso_datetime;",
        vars={"iso_datetime": date},
    )
    compact_test_outcome = await surrealdb_connection.query(
        "SELECT * FROM datetime_tests;"
    )
    assert str(compact_test_outcome[0]["datetime"]) == str(iso_datetime_obj)
    date_str = compact_test_outcome[0]["datetime"].isoformat()
    if sys.version_info >= (3, 11):
        date_str = date_str.replace("+00:00", "Z")
    assert date_str == iso_datetime
