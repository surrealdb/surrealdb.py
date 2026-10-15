"""`export()` and `import_()` over the server's /export and /import endpoints,
on every transport, against a real server."""

import io
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest

from surrealdb import AsyncSurreal, ExportOptions, ImportFailedError, Surreal
from surrealdb.connections import server_version
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import (
    AlreadyExistsError,
    SurrealError,
    ThrownError,
    UnsupportedFeatureError,
    UnsupportedVersionError,
)
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

    assert ExportOptions(tables="person").body() == {"tables": ["person"]}
    assert ExportOptions(tables={"exclude": "a"}).body() == {
        "tables": {"exclude": ["a"]}
    }


def test_versions_is_refused_where_the_server_dropped_it() -> None:
    with pytest.raises(UnsupportedFeatureError, match="versions"):
        ExportOptions(versions=True).check("3.3.1")
    ExportOptions(versions=True).check("3.3.0")
    ExportOptions(versions=True).check(None)
    ExportOptions(versions=False).check("3.4.0")


def test_export_to_writes_a_file_and_a_stream(db: Blocking, tmp_path: Path) -> None:
    db.query("CREATE person:one SET name = 'One';").execute()
    path = tmp_path / "export.surql"
    db.export_to(path)
    assert "person:one" in path.read_text()
    stream = io.BytesIO()
    db.export_to(stream)
    assert stream.getvalue().decode() == path.read_text()

    db.query("REMOVE TABLE person;").execute()
    db.import_(path)
    assert db.query("SELECT VALUE name FROM person:one;").first() == ["One"]


async def test_async_export_to_a_file_and_import_it(adb: Async, tmp_path: Path) -> None:
    await adb.query("CREATE person:one;")
    path = tmp_path / "export.surql"
    await adb.export_to(str(path))
    assert "person:one" in path.read_text()
    stream = io.BytesIO()
    await adb.export_to(stream)
    assert stream.getvalue().decode() == path.read_text()

    await adb.query("REMOVE TABLE person;")
    await adb.import_(path)
    assert await adb.query("RETURN count(SELECT * FROM person);").first() == 1


def test_blocking_ws_export_renews_a_due_token_first(
    connection_params: dict[str, Any],
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.query(
        "DEFINE USER OVERWRITE ie_short ON ROOT PASSWORD 'ie-short' "
        "ROLES OWNER DURATION FOR TOKEN 2s, FOR SESSION 1h;"
    ).execute()
    db = BlockingWsSurrealConnection(
        connection_params["ws_url"],
        auth={"username": "ie_short", "password": "ie-short"},
    )
    try:
        db.connect()
        db.use(connection_params["namespace"], connection_params["database_name"])
        first = db.token
        time.sleep(2.1)
        assert isinstance(db.export(), str)
        assert db.token not in (None, first)
    finally:
        db.close()
        blocking_ws_connection.query(
            "REMOVE USER IF EXISTS ie_short ON ROOT;"
        ).execute()


async def test_a_failed_async_export_leaves_the_file_alone(
    adb: Async, tmp_path: Path
) -> None:
    path = tmp_path / "backup.surql"
    path.write_text("the last good backup")
    good = adb.token
    adb.token = "not.a.token"
    try:
        with pytest.raises(SurrealError):
            await adb.export_to(path)
    finally:
        adb.token = good
    assert path.read_text() == "the last good backup"


@pytest.mark.parametrize("blocking", [True, False])
async def test_http_import_checks_the_server_version_first(
    connection_params: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    blocking: bool,
) -> None:
    monkeypatch.setattr(
        server_version, "is_version_supported", lambda *_args, **_kw: False
    )
    with pytest.raises(UnsupportedVersionError):
        if blocking:
            BlockingHttpSurrealConnection(connection_params["url"]).import_(
                "OPTION IMPORT;"
            )
        else:
            await AsyncHttpSurrealConnection(connection_params["url"]).import_(
                "OPTION IMPORT;"
            )
