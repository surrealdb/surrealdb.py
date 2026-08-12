"""Two operations that answered differently depending on the transport.

``run()`` over HTTP could not see a variable bound with ``let()``. HTTP has no
server-side session for the server to resolve one from, and the ``run`` RPC
carries no parameters - so a function reading ``$v`` saw nothing and the call
returned ``None``, where the same call over a websocket returned the value.
Query *parameters* do reach a function body, so HTTP now sends the call as a
query when there are bindings to replay.

``update()`` on a record that does not exist returned ``[]``. The overloads
promise a ``dict`` for a single-record target, and ``select()`` answers ``None``
for an absent record - so this was a third answer, shared with nothing.
``if db.update(rec, data):`` was False for a missing record and truthy
otherwise, which reads as working, but ``db.update(rec, data)["field"]`` raised
``TypeError: list indices must be integers``. With ``into=Model`` a bare list
came back where a model was declared.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.utils_mixin import build_run_query
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import UnsupportedFeatureError

TABLE = "transport_agreement"

READS_SESSION_VAR = (
    "DEFINE FUNCTION OVERWRITE fn::reads_session_var() { RETURN $probe; };"
)
TAKES_ARGS = (
    "DEFINE FUNCTION OVERWRITE fn::takes_args($a: int, $b: int) { RETURN $a + $b; };"
)


@dataclass
class Model:
    id: Any
    name: str


@pytest.fixture(autouse=True)
def _clean(blocking_ws_connection: BlockingWsSurrealConnection) -> None:
    blocking_ws_connection.query(f"REMOVE TABLE IF EXISTS {TABLE};").execute()


# ------------------------------------------------- run() sees let() bindings


def _functions_see_outer_variables(version: str) -> bool:
    """Whether this server lets a function body read a variable from outside.

    A 3.x function body resolves ``$v`` from the session, and from the query's
    own parameters. A 2.x one resolves nothing from outside itself - not a
    session binding, not a query parameter - so there is nothing for either
    transport to return there and no divergence between them to fix.
    """
    text = (version or "").strip().lower()
    for prefix in ("surrealdb-", "v"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    try:
        return int(text.split(".")[0]) >= 3
    except (ValueError, IndexError):
        return False


def test_blocking_http_run_sees_let_bindings(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    blocking_http_connection.query(READS_SESSION_VAR).execute()
    blocking_http_connection.let("probe", 42)

    supported = _functions_see_outer_variables(blocking_http_connection.version())
    assert blocking_http_connection.run("fn::reads_session_var") == (
        42 if supported else None
    )


def test_blocking_ws_run_sees_let_bindings(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The transport HTTP has to agree with, pinned alongside it."""
    blocking_ws_connection.query(READS_SESSION_VAR).execute()
    blocking_ws_connection.let("probe", 42)

    supported = _functions_see_outer_variables(blocking_ws_connection.version())
    assert blocking_ws_connection.run("fn::reads_session_var") == (
        42 if supported else None
    )


async def test_async_http_run_sees_let_bindings(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.query(READS_SESSION_VAR).execute()
    await async_http_connection.let("probe", 42)

    supported = _functions_see_outer_variables(await async_http_connection.version())
    assert await async_http_connection.run("fn::reads_session_var") == (
        42 if supported else None
    )


async def test_async_ws_run_sees_let_bindings(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await async_ws_connection.query(READS_SESSION_VAR).execute()
    await async_ws_connection.let("probe", 42)

    supported = _functions_see_outer_variables(await async_ws_connection.version())
    assert await async_ws_connection.run("fn::reads_session_var") == (
        42 if supported else None
    )


def test_both_transports_answer_the_same(
    blocking_ws_connection: BlockingWsSurrealConnection,
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    """The point of the fix, stated without naming a server version.

    Whatever this server does with a function reading a session binding, the
    two transports have to do the same thing. That is what was broken: HTTP
    answered ``None`` where the websocket answered ``42``.
    """
    blocking_ws_connection.query(READS_SESSION_VAR).execute()
    blocking_ws_connection.let("probe", 42)
    blocking_http_connection.let("probe", 42)

    assert blocking_http_connection.run("fn::reads_session_var") == (
        blocking_ws_connection.run("fn::reads_session_var")
    )


def test_run_with_arguments_still_works_alongside_bindings(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    """Arguments are bound as parameters, so they must survive the new path."""
    blocking_http_connection.query(TAKES_ARGS).execute()
    blocking_http_connection.let("probe", 42)

    assert blocking_http_connection.run("fn::takes_args", [1, 2]) == 3


def test_run_without_bindings_is_unchanged(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    """No bindings means the plain RPC path, exactly as before."""
    blocking_http_connection.query(TAKES_ARGS).execute()

    assert blocking_http_connection.run("fn::takes_args", [4, 5]) == 9


def test_a_version_cannot_be_combined_with_bindings_over_http(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    """The one combination HTTP cannot express, reported rather than fudged.

    A version needs the ``run`` RPC, which carries no parameters; the bindings
    need a query, and SurrealQL has no syntax for calling a specific version.
    """
    blocking_http_connection.query(TAKES_ARGS).execute()
    blocking_http_connection.let("probe", 42)

    with pytest.raises(UnsupportedFeatureError, match="version"):
        blocking_http_connection.run("fn::takes_args", [1, 2], version="1.0.0")


@pytest.mark.parametrize(
    "name",
    [
        "fn::x(); DROP TABLE users; --",
        "fn::x) OR true --",
        "1fn::x",
        "fn::x y",
        "⟨injected⟩",
    ],
)
def test_a_hostile_function_name_is_quoted_not_executed(name: str) -> None:
    """The name is the one part that cannot be parameter-bound.

    It is rendered as a *quoted identifier* rather than refused, because
    SurrealDB accepts backtick-quoted identifiers in a function name and
    refusing them broke legal calls (``fn::`my-fn```). What matters is that
    nothing in the name can escape the quoting and become SurrealQL: the
    rendered call is one identifier and one pair of parentheses, whatever the
    name contained.
    """
    query, arguments = build_run_query(name, None)

    assert arguments == {}
    # Everything after `RETURN ` up to `()` is the rendered name, and every
    # segment of it is either a plain identifier or backtick-quoted.
    rendered = query.removeprefix("RETURN ").removesuffix("();")
    for segment in rendered.split("::"):
        plain = segment.replace("_", "a").isalnum() and not segment[0].isdigit()
        assert plain or (segment.startswith("`") and segment.endswith("`")), (
            f"segment {segment!r} is neither a plain identifier nor quoted"
        )
    # A quoted segment contains no backtick of its own, so it cannot end early.
    assert rendered.count("`") % 2 == 0


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty"),
        pytest.param("fn::", id="empty-segment"),
        pytest.param("fn::x`; DROP", id="contains-backtick"),
        pytest.param("fn::x\nDROP", id="contains-newline"),
    ],
)
def test_a_function_name_that_cannot_be_quoted_is_refused(name: str) -> None:
    """A backtick or newline would end the quoting, so those are refused."""
    with pytest.raises(ValueError):
        build_run_query(name, None)


def test_a_legal_quoted_function_name_is_accepted() -> None:
    """``fn::`my-fn``` is definable and callable, so ``run()`` must allow it.

    Rejecting it meant an unrelated ``let()`` elsewhere in the program broke a
    ``run()`` call that had always worked, because only the bindings path
    validated the name.
    """
    query, _ = build_run_query("fn::my-fn", None)

    assert query == "RETURN fn::`my-fn`();"


@pytest.mark.parametrize(
    "args", [pytest.param("xy", id="str"), pytest.param({"a": 1}, id="dict")]
)
def test_run_args_must_be_a_sequence(args: object) -> None:
    """``enumerate`` accepts any iterable, which silently spread a string.

    ``run("fn::f", "ab")`` called ``f("a", "b")`` - two arguments from one
    value. The server rejects a non-array ``args`` too, so this refuses the
    same input, earlier and by name.
    """
    with pytest.raises(TypeError, match="list or tuple"):
        build_run_query("fn::f", args)  # type: ignore[arg-type]


def test_the_generated_query_binds_every_argument() -> None:
    """No argument is ever inlined into the query text."""
    query, arguments = build_run_query("fn::takes_args", [1, "two'; DROP", {"k": "v"}])

    assert "DROP" not in query
    assert query.count("$") == 3
    assert list(arguments.values()) == [1, "two'; DROP", {"k": "v"}]


# --------------------------------------- update() on a record that is absent


def test_blocking_ws_update_on_an_absent_record(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.create(RecordID(TABLE, "exists"), {"name": "here"})

    assert blocking_ws_connection.update(RecordID(TABLE, "gone"), {"name": "n"}) is None


def test_blocking_http_update_on_an_absent_record(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    blocking_http_connection.create(RecordID(TABLE, "exists"), {"name": "here"})

    assert (
        blocking_http_connection.update(RecordID(TABLE, "gone"), {"name": "n"}) is None
    )


async def test_async_ws_update_on_an_absent_record(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await async_ws_connection.create(RecordID(TABLE, "exists"), {"name": "here"})

    assert (
        await async_ws_connection.update(RecordID(TABLE, "gone"), {"name": "n"}) is None
    )


async def test_async_http_update_on_an_absent_record(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.create(RecordID(TABLE, "exists"), {"name": "here"})

    assert (
        await async_http_connection.update(RecordID(TABLE, "gone"), {"name": "n"})
        is None
    )


def test_update_on_an_absent_record_with_into_is_none_not_a_list(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """``into=Model`` declared a model; a raw ``[]`` is not one."""
    blocking_ws_connection.create(RecordID(TABLE, "exists"), {"name": "here"})

    outcome = blocking_ws_connection.update(
        RecordID(TABLE, "gone"), {"name": "n"}, into=Model
    )

    assert outcome is None


def test_an_absent_record_answers_the_same_everywhere(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """select / update / delete agree on what "no such record" looks like."""
    blocking_ws_connection.create(RecordID(TABLE, "exists"), {"name": "here"})
    missing = RecordID(TABLE, "gone")

    assert blocking_ws_connection.select(missing) is None
    assert blocking_ws_connection.update(missing, {"name": "n"}) is None
    assert blocking_ws_connection.delete(missing) is None


def test_a_present_record_still_comes_back_as_a_record(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The unwrapping must not start swallowing real results."""
    record = RecordID(TABLE, "exists")
    blocking_ws_connection.create(record, {"name": "here"})

    updated = blocking_ws_connection.update(record, {"name": "changed"})
    assert isinstance(updated, dict)
    assert updated["name"] == "changed"

    as_model = blocking_ws_connection.update(record, {"name": "again"}, into=Model)
    assert isinstance(as_model, Model)
    assert as_model.name == "again"


def test_a_table_target_still_returns_a_list(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """Only single-record targets unwrap; a table target keeps its list.

    Includes the empty case, which must stay ``[]`` rather than becoming None.
    """
    from surrealdb.data.types.table import Table

    blocking_ws_connection.query(f"DEFINE TABLE OVERWRITE {TABLE};").execute()
    assert blocking_ws_connection.update(Table(TABLE), {"name": "n"}) == []

    blocking_ws_connection.create(RecordID(TABLE, "one"), {"name": "a"})
    rows = blocking_ws_connection.update(Table(TABLE), {"name": "b"})
    assert isinstance(rows, list)
    assert len(rows) == 1
