"""`export()` and `import_()` over the server's /export and /import endpoints,
on every transport, against a real server."""

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest

from surrealdb import AsyncSurreal, ExportOptions, ImportFailedError, Surreal
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import AlreadyExistsError, ThrownError, UnsupportedFeatureError
from surrealdb.features import Features, parse_version

Blocking = BlockingWsSurrealConnection | BlockingHttpSurrealConnection
Async = AsyncWsSurrealConnection | AsyncHttpSurrealConnection


@pytest.fixture(params=["ws", "http"])
def db(
    request: pytest.FixtureRequest, connection_params: dict[str, Any]
) -> Iterator[Blocking]:
    url = connection_params["ws_url" if request.param == "ws" else "url"]
    connection = Surreal(url)
    connection.signin(connection_params["vars_params"])
    database = f"ie_{uuid.uuid4().hex[:8]}"
    connection.use(connection_params["namespace"], database)
    try:
        yield connection
    finally:
        connection.query(f"REMOVE DATABASE IF EXISTS {database};").execute()
        connection.close()


@pytest.fixture(params=["ws", "http"])
async def adb(
    request: pytest.FixtureRequest, connection_params: dict[str, Any]
) -> AsyncIterator[Async]:
    url = connection_params["ws_url" if request.param == "ws" else "url"]
    connection = AsyncSurreal(url)
    await connection.signin(connection_params["vars_params"])
    database = f"ie_{uuid.uuid4().hex[:8]}"
    await connection.use(connection_params["namespace"], database)
    try:
        yield connection
    finally:
        await connection.query(f"REMOVE DATABASE IF EXISTS {database};")
        await connection.close()


def _accepts_export_options(db: Blocking | Async) -> bool:
    version = parse_version(db.server_version or "")
    return version is None or version >= (2, 1, 0)


def test_export_then_import_round_trips(db: Blocking, tmp_path: Path) -> None:
    db.query("CREATE person:one SET name = 'One'; CREATE person:two;").execute()
    sql = db.export()
    assert "person:one" in sql
    assert sql.lstrip("- \n").startswith("OPTION IMPORT") or "OPTION IMPORT;" in sql

    db.query("REMOVE TABLE person;").execute()
    path = tmp_path / "export.surql"
    path.write_text(sql)
    db.import_(path)

    assert db.query("SELECT VALUE name FROM person:one;").first() == ["One"]
    assert db.query("RETURN count(SELECT * FROM person);").first() == 2


def test_export_options_choose_what_is_included(db: Blocking) -> None:
    if not _accepts_export_options(db):
        with pytest.raises(UnsupportedFeatureError, match="POST /export"):
            db.export(ExportOptions(records=False))
        return
    db.query("CREATE person:one; CREATE other:one;").execute()

    only_person = db.export(ExportOptions(tables=["person"]))
    assert "person:one" in only_person
    assert "other:one" not in only_person

    no_records = db.export(ExportOptions(records=False))
    assert "DEFINE TABLE person" in no_records
    assert "person:one" not in no_records


def test_import_reports_every_failed_statement(db: Blocking) -> None:
    db.query("CREATE person:one;").execute()
    with pytest.raises(ImportFailedError) as caught:
        db.import_("OPTION IMPORT; CREATE person:one; THROW 'boom'; CREATE person:two;")
    failures = caught.value.failures
    assert len(failures) == 2
    assert "already exists" in str(failures[0])
    assert "boom" in str(failures[1])
    if db.is_feature_supported(Features.IMPORT_FAILURE_REPORTING):
        # Older servers name no error kinds, so these come out as plain
        # server errors there.
        assert isinstance(failures[0], AlreadyExistsError)
        assert isinstance(failures[1], ThrownError)
    # The statements that could run, did.
    assert db.query("RETURN count(SELECT * FROM person);").first() == 2


def test_import_accepts_bytes(db: Blocking) -> None:
    db.import_(b"OPTION IMPORT; CREATE person:bytes;")
    assert db.query("RETURN count(SELECT * FROM person:bytes);").first() == 1


async def test_async_round_trip_and_failures(adb: Async) -> None:
    await adb.query("CREATE person:one;")
    sql = await adb.export()
    await adb.query("REMOVE TABLE person;")
    await adb.import_(sql)
    assert await adb.query("RETURN count(SELECT * FROM person);").first() == 1

    with pytest.raises(ImportFailedError) as caught:
        await adb.import_("OPTION IMPORT; CREATE person:one;")
    assert len(caught.value.failures) == 1

    if _accepts_export_options(adb):
        assert "person:one" not in await adb.export(ExportOptions(records=False))


def test_export_options_body() -> None:
    assert ExportOptions().body() is None
    assert ExportOptions(tables=("a", "b"), users=False).body() == {
        "users": False,
        "tables": ["a", "b"],
    }
    assert ExportOptions(tables={"exclude": ("a",)}).body() == {
        "tables": {"exclude": ["a"]}
    }
