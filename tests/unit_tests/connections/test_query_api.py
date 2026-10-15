"""Builder modifiers, `relate()`, `api()`, `gql()` and
`graphql()`, on every transport, against a real server."""

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from surrealdb import AsyncSurreal, Datetime, RecordID, Surreal, Table
from surrealdb.connections.api import ApiResponse, build_api_query, graphql_params
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import (
    NotFoundError,
    ServerError,
    SurrealError,
    UnavailableFeatureError,
    UnexpectedResponseError,
)
from surrealdb.features import Features

Blocking = BlockingWsSurrealConnection | BlockingHttpSurrealConnection
Async = AsyncWsSurrealConnection | AsyncHttpSurrealConnection


@pytest.fixture(params=["ws", "http"])
def db(
    request: pytest.FixtureRequest, connection_params: dict[str, Any]
) -> Iterator[Blocking]:
    url = connection_params["ws_url" if request.param == "ws" else "url"]
    connection = Surreal(url)
    connection.signin(connection_params["vars_params"])
    database = f"qa_{uuid.uuid4().hex[:8]}"
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
    database = f"qa_{uuid.uuid4().hex[:8]}"
    await connection.use(connection_params["namespace"], database)
    try:
        yield connection
    finally:
        await connection.query(f"REMOVE DATABASE IF EXISTS {database};")
        await connection.close()


def _people(db: Blocking) -> None:
    db.query(
        " ".join(f"CREATE person:{n} SET age = {n};" for n in range(1, 6))
    ).execute()


def test_where_limit_and_start_narrow_a_select(db: Blocking) -> None:
    _people(db)
    rows: Any = (
        db.select("person")
        .where("age >= $min", {"min": 2})
        .limit(2)
        .start(1)
        .timeout("5s")
        .execute()
    )
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert all(row["age"] >= 2 for row in rows)


def test_fetch_replaces_links_with_the_records(db: Blocking) -> None:
    db.query(
        "CREATE author:ada SET name = 'Ada'; CREATE book:one SET author = author:ada;"
    ).execute()
    books: Any = db.select("book").fetch("author").execute()
    assert books[0]["author"]["name"] == "Ada"


def test_update_where_returns_the_chosen_fields(db: Blocking) -> None:
    _people(db)
    changed: Any = (
        db.update("person")
        .where("age > $over", {"over": 3})
        .output(["age"])
        .merge({"old": True})
    )
    assert sorted(row["age"] for row in changed) == [4, 5]
    assert all(set(row) == {"age"} for row in changed)
    assert db.query("RETURN count(SELECT * FROM person WHERE old);").first() == 2


def test_delete_returns_what_was_deleted_unless_told_otherwise(db: Blocking) -> None:
    _people(db)
    gone: Any = db.delete("person").where("age = 1").execute()
    assert [row["age"] for row in gone] == [1]
    assert db.delete("person").where("age = 2").output("none").execute() == []
    assert db.query("RETURN count(SELECT * FROM person);").first() == 3


def test_a_modifier_the_statement_does_not_take_is_refused(db: Blocking) -> None:
    db.query("DEFINE TABLE nobody;").execute()
    builder = db.update("nobody")
    with pytest.raises(SurrealError, match="UPDATE does not take limit"):
        builder.limit(1)
    select = db.select("nobody")
    with pytest.raises(TypeError, match="version"):
        select.version("yesterday")  # type: ignore[arg-type,unused-ignore]
    assert select.execute() == []
    with pytest.raises(ValueError):
        builder.output("everything")
    builder.timeout(timedelta(seconds=2)).execute()


def test_relate_creates_edges(db: Blocking) -> None:
    ada, bob, cy = (
        RecordID("person", "ada"),
        RecordID("person", "bob"),
        RecordID("person", "cy"),
    )
    db.query("CREATE person:ada; CREATE person:bob; CREATE person:cy;").execute()

    edge: Any = db.relate(ada, "knows", bob, {"since": 2020})
    assert edge["in"] == ada and edge["out"] == bob and edge["since"] == 2020

    chosen: Any = db.relate(bob, RecordID("knows", "chosen"), cy, {})
    assert chosen["id"] == RecordID("knows", "chosen")

    many: Any = db.relate([ada, bob], Table("likes"), cy, {"stars": 5})
    assert sorted(str(row["in"]) for row in many) == ["person:ada", "person:bob"]

    assert db.relate(cy, "knows", ada).output("none").execute() in (None, [])
    assert db.query("SELECT VALUE ->knows->person FROM ONLY person:cy;").first() == [
        ada
    ]


def test_insert_takes_output_and_timeout(db: Blocking) -> None:
    rows: Any = (
        db.insert("person")
        .output(["name"])
        .timeout("5s")
        .content([{"name": "a"}, {"name": "b"}])
    )
    assert sorted(row["name"] for row in rows) == ["a", "b"]
    assert all(set(row) == {"name"} for row in rows)


def test_run_calls_functions(db: Blocking) -> None:
    assert db.run("string::uppercase", ["abc"]) == "ABC"
    db.query("DEFINE FUNCTION fn::double($n: int) { RETURN $n * 2 };").execute()
    assert db.run("fn::double", [21]) == 42


def test_api_calls_a_defined_endpoint(db: Blocking) -> None:
    if not db.is_feature_supported(Features.API):
        with pytest.raises(UnavailableFeatureError):
            db.api("/greet")
        return
    try:
        db.query(
            "DEFINE API OVERWRITE '/greet' FOR get, post THEN "
            "{ RETURN { status: 201, body: { hello: $request.query.name, "
            "got: $request.body } } };"
        ).execute()
    except ServerError as exc:
        if "capability" not in str(exc):
            raise
        pytest.skip("the server was started without the define_api capability")

    response = db.api("/greet", query={"name": "ada"})
    assert response.status == 201 and response.ok
    assert response.body == {"hello": "ada", "got": None}

    posted = db.api("/greet", method="POST", body={"n": 1}, query={"name": "b"})
    assert posted.body == {"hello": "b", "got": {"n": 1}}

    missing = db.api("/nowhere")
    assert missing.status == 404 and not missing.ok


def test_gql_and_graphql(db: Blocking) -> None:
    db.query("CREATE person:ada SET name = 'Ada';").execute()
    try:
        assert db.gql("MATCH (p:person) RETURN p.name") == [[{"p.name": "Ada"}]]
    except NotFoundError:
        pytest.skip("this server has no gql method")

    db.query("CREATE person:bob SET name = 'Bob';").execute()
    db.let("who", "Bob")
    assert db.gql("MATCH (p:person) WHERE p.name = $who RETURN p.name") == [
        [{"p.name": "Bob"}]
    ]

    db.query("DEFINE CONFIG OVERWRITE GRAPHQL AUTO;").execute()
    assert db.graphql("{ __typename }") == {"data": {"__typename": "Query"}}
    answer = db.graphql("query Q { __typename }", {}, "Q")
    assert answer["data"] == {"__typename": "Query"}


async def test_async_builders_relate_and_api(adb: Async) -> None:
    await adb.query("CREATE person:ada SET age = 3; CREATE person:bob SET age = 9;")
    rows: Any = await adb.select("person").where("age > 5")
    assert [row["age"] for row in rows] == [9]

    edge: Any = await adb.relate(
        RecordID("person", "ada"), "knows", RecordID("person", "bob")
    ).content({"since": 1})
    assert edge["since"] == 1

    assert await adb.run("math::max", [[1, 7, 3]]) == 7
    if adb.is_feature_supported(Features.API):
        assert (await adb.api("/nowhere")).status == 404


def test_compiled_queries() -> None:
    sql, variables = build_api_query("/a", "PATCH", {"x": 1}, {"h": "v"}, None)
    assert sql == "RETURN api::invoke($_path, $_request);"
    assert variables == {
        "_path": "/a",
        "_request": {"method": "patch", "body": {"x": 1}, "headers": {"h": "v"}},
    }
    with pytest.raises(ValueError, match="starting with '/'"):
        build_api_query("a", "get", None, None, None)
    with pytest.raises(ValueError, match="method"):
        build_api_query("/a", "fetch", None, None, None)

    assert graphql_params("q", None, None) == ["q"]
    assert graphql_params("q", None, "Op") == ["q", {}, "Op"]

    assert ApiResponse.from_result({"status": 204}) == ApiResponse(204)
    with pytest.raises(UnexpectedResponseError):
        ApiResponse.from_result("nope")


def test_relate_refuses_ends_that_are_not_records(db: Blocking) -> None:
    ada, bob = RecordID("person", "ada"), RecordID("person", "bob")
    with pytest.raises(ValueError, match="one edge id"):
        db.relate([ada, bob], RecordID("knows", "one"), ada)
    with pytest.raises(ValueError, match="one edge id"):
        db.relate(ada, RecordID("knows", "one"), [bob])
    with pytest.raises(TypeError, match="relates records"):
        db.relate(Table("person"), "knows", bob)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="relates records"):
        db.relate(ada, "knows", "person")


def test_version_is_sent_as_a_literal_every_server_parses(db: Blocking) -> None:
    builder = db.select("person").version(datetime(2024, 1, 2, 3, 4, 5))
    sql, variables = builder._build()
    assert sql.endswith(' VERSION d"2024-01-02T03:04:05+00:00"')
    assert "_version" not in variables
    sql, _ = db.select("person").version(Datetime('2024-01-02T03:04:05Z"'))._build()
    assert sql.endswith(' VERSION d"2024-01-02T03:04:05Z\\""')
    try:
        db.select("person").version(datetime(2024, 1, 2, tzinfo=timezone.utc)).execute()
    except SurrealError as exc:
        # A datastore without versions refuses the read, but it parsed.
        assert "parse" not in str(exc).lower()
