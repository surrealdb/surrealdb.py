"""What the HTTP transports keep for a session, against a fake server.

HTTP has no server-side session: the namespace, database and ``let()``
variables live on the client and go with each request, as headers and query
parameters. These pin the places that used to behave differently from a
websocket, where the server holds them.
"""

from collections.abc import Iterator

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.errors import InternalError, ValidationError
from surrealdb.types import Value
from tests.unit_tests.fake_surreal import Call, FakeSurrealHttp, RpcFailure


@pytest.fixture
def http() -> Iterator[FakeSurrealHttp]:
    server = FakeSurrealHttp()
    try:
        yield server
    finally:
        server.close()


@pytest.mark.parametrize("name", ["名前空間", "ns_ü", "a\nb"])
def test_blocking_use_refuses_a_name_a_header_cannot_carry(
    http: FakeSurrealHttp, name: str
) -> None:
    db = BlockingHttpSurrealConnection(http.url)
    db.use("ns", "db")
    with pytest.raises(ValueError, match="printable ASCII"):
        db.use(name, "db")
    with pytest.raises(ValueError, match="database"):
        db.use("ns", name)
    assert (db.namespace, db.database) == ("ns", "db")
    assert http.methods().count("use") == 1


async def test_async_use_refuses_a_name_a_header_cannot_carry(
    http: FakeSurrealHttp,
) -> None:
    db = AsyncHttpSurrealConnection(http.url)
    with pytest.raises(ValueError, match="printable ASCII"):
        await db.use("名前空間", "db")
    assert (db.namespace, db.database) == (None, None)
    assert "use" not in http.methods()


def test_use_takes_any_printable_ascii_name(http: FakeSurrealHttp) -> None:
    db = BlockingHttpSurrealConnection(http.url)
    db.use("my ns-1", "db~`x`")
    assert (db.namespace, db.database) == ("my ns-1", "db~`x`")


def test_blocking_let_binds_the_value_it_was_given(http: FakeSurrealHttp) -> None:
    db = BlockingHttpSurrealConnection(http.url)
    document: dict[str, Value] = {"tags": ["a"]}
    db.let("document", document)
    tags = document["tags"]
    assert isinstance(tags, list)
    tags.append("b")
    db.query("RETURN $document").execute()
    assert http.calls_to("query")[-1].params[1]["document"] == {"tags": ["a"]}


async def test_async_let_binds_the_value_it_was_given(http: FakeSurrealHttp) -> None:
    db = AsyncHttpSurrealConnection(http.url)
    document: dict[str, Value] = {"tags": ["a"]}
    await db.let("document", document)
    tags = document["tags"]
    assert isinstance(tags, list)
    tags.append("b")
    await db.query("RETURN $document")
    assert http.calls_to("query")[-1].params[1]["document"] == {"tags": ["a"]}


@pytest.mark.parametrize("name", ["token", "auth", "session", "access"])
def test_blocking_let_refuses_a_protected_name_as_the_server_does(
    http: FakeSurrealHttp, name: str
) -> None:
    db = BlockingHttpSurrealConnection(http.url)
    with pytest.raises(
        ValidationError, match="Cannot set protected variable"
    ) as caught:
        db.let(name, "abc")
    assert caught.value.details == {"kind": "InvalidParams"}
    assert name not in db.vars
    db.let("scope", "fine")
    assert db.vars == {"scope": "fine"}


async def test_async_let_refuses_a_protected_name_as_the_server_does(
    http: FakeSurrealHttp,
) -> None:
    db = AsyncHttpSurrealConnection(http.url)
    with pytest.raises(ValidationError, match="protected variable: token"):
        await db.let("token", "abc")
    assert db.vars == {}


def _unknown_function(call: Call) -> None:
    raise RpcFailure("Unknown function 'string::nope'", kind="Internal")


def test_blocking_run_sends_a_builtin_as_the_rpc_with_variables_bound(
    http: FakeSurrealHttp,
) -> None:
    """Only a custom function can read a let() variable, so only it goes as a query."""
    http.respond("run", _unknown_function)
    db = BlockingHttpSurrealConnection(http.url)
    db.let("factor", 10)
    with pytest.raises(InternalError, match="Unknown function 'string::nope'"):
        db.run("string::nope", ["a"])
    db.run("fn::scaled", [2])
    assert [m for m in http.methods() if m in ("run", "query")] == ["run", "query"]


async def test_async_run_sends_a_builtin_as_the_rpc_with_variables_bound(
    http: FakeSurrealHttp,
) -> None:
    http.respond("run", _unknown_function)
    db = AsyncHttpSurrealConnection(http.url)
    await db.let("factor", 10)
    with pytest.raises(InternalError, match="Unknown function 'string::nope'"):
        await db.run("string::nope", ["a"])
    await db.run("fn::scaled", [2])
    assert [m for m in http.methods() if m in ("run", "query")] == ["run", "query"]
