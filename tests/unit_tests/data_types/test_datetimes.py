import datetime
import sys

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.datetime import IsoDateTimeWrapper


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
    await connection.query("DELETE datetime_tests;")
    yield connection
    await connection.query("DELETE datetime_tests;")
    await connection.close()


@pytest.mark.asyncio
async def test_native_datetime(surrealdb_connection):
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
async def test_datetime_iso_format(surrealdb_connection):
    iso_datetime = "2025-02-03T12:30:45.123456Z"  # ISO 8601 datetime
    if sys.version_info < (3, 11):
        iso_datetime = iso_datetime.replace("Z", "+00:00")
    date = IsoDateTimeWrapper(iso_datetime)
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
