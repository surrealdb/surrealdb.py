"""Server-independent tests for the ``into=`` row-model mapping.

These exercise the mapping machinery directly through the builders (with stub
executors) and through ``select`` (with a monkeypatched ``query_raw``), so they
run without a SurrealDB server. The live end-to-end coverage lives in
``tests/unit_tests/connections/v3_api/test_into_row_model.py`` (which self-skips
when no server is reachable).

Mapping goes through the single shared helper ``_map_to_class`` for every
supported model kind: dataclasses, pydantic ``BaseModel``, and plain
kwargs-constructible classes.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.builders import (
    AsyncCrudBuilder,
    AsyncQueryBuilder,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
)
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@dataclass
class Person:
    id: Any
    name: str


class PlainPerson:
    """A plain (non-dataclass, non-pydantic) kwargs-constructible class."""

    def __init__(self, id: Any, name: str) -> None:
        self.id = id
        self.name = name


def _ok(payload: Any) -> dict[str, Any]:
    """Build a single-statement OK response wrapping ``payload``."""
    return {"result": [{"status": "OK", "result": payload}]}


# ---------------------------------------------------------------------------
# _map_to_class: row (Mapping) branch
# ---------------------------------------------------------------------------


def test_map_row_to_dataclass() -> None:
    from surrealdb.connections.builders import _map_to_class

    row = {"id": RecordID("person", "tobie"), "name": "Tobie"}
    out = _map_to_class(Person, row)
    assert isinstance(out, Person)
    assert out.name == "Tobie"


def test_map_row_to_plain_class() -> None:
    from surrealdb.connections.builders import _map_to_class

    row = {"id": RecordID("person", "tobie"), "name": "Tobie"}
    out = _map_to_class(PlainPerson, row)
    assert isinstance(out, PlainPerson)
    assert out.name == "Tobie"


def test_map_row_to_pydantic() -> None:
    pytest.importorskip("pydantic")
    import pydantic

    from surrealdb.connections.builders import _map_to_class

    class PydModel(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)
        id: Any
        name: str

    row = {"id": RecordID("person", "tobie"), "name": "Tobie"}
    out = _map_to_class(PydModel, row)
    assert isinstance(out, PydModel)
    assert out.name == "Tobie"


# ---------------------------------------------------------------------------
# Async CRUD builders map through into=
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_create_into_returns_model() -> None:
    record = {"id": RecordID("person", "tobie"), "name": "Tobie"}

    async def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok([record])

    builder: AsyncCrudBuilder[Person] = AsyncCrudBuilder(
        executor=stub,
        operation="CREATE",
        record=RecordID("person", "tobie"),
        op_name="create",
        data={"name": "Tobie"},
        always_unwrap=True,
        into=Person,
    )
    out = await builder
    assert isinstance(out, Person)
    assert out.name == "Tobie"


@pytest.mark.asyncio
async def test_async_update_table_into_returns_list_of_models() -> None:
    rows = [
        {"id": RecordID("person", "a"), "name": "A"},
        {"id": RecordID("person", "b"), "name": "B"},
    ]

    async def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok(rows)

    builder: AsyncCrudBuilder[list[Person]] = AsyncCrudBuilder(
        executor=stub,
        operation="UPDATE",
        record=Table("person"),
        op_name="update",
        data={"name": "X"},
        into=Person,
    )
    out = await builder
    assert isinstance(out, list)
    assert [p.name for p in out] == ["A", "B"]
    assert all(isinstance(p, Person) for p in out)


@pytest.mark.asyncio
async def test_async_delete_absent_into_returns_none() -> None:
    async def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok([])

    builder: AsyncCrudBuilder[Person | None] = AsyncCrudBuilder(
        executor=stub,
        operation="DELETE",
        record=RecordID("person", "missing"),
        op_name="delete",
        into=Person,
    )
    assert await builder is None


# ---------------------------------------------------------------------------
# Sync CRUD builders map through into=
# ---------------------------------------------------------------------------


def test_sync_create_into_returns_model() -> None:
    record = {"id": RecordID("person", "tobie"), "name": "Tobie"}

    def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok([record])

    builder: SyncCrudBuilder[Person] = SyncCrudBuilder(
        executor=stub,
        operation="CREATE",
        record=RecordID("person", "tobie"),
        op_name="create",
        always_unwrap=True,
        into=Person,
    )
    out = builder.content({"name": "Tobie"})
    assert isinstance(out, Person)
    assert out.name == "Tobie"


def test_sync_insert_into_returns_list_of_models() -> None:
    rows = [
        {"id": RecordID("person", "a"), "name": "A"},
        {"id": RecordID("person", "b"), "name": "B"},
    ]

    def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok(rows)

    builder: SyncInsertBuilder[Person] = SyncInsertBuilder(
        executor=stub,
        table=Table("person"),
        into=Person,
    )
    out = builder.content([{"name": "A"}, {"name": "B"}])
    assert [p.name for p in out] == ["A", "B"]
    assert all(isinstance(p, Person) for p in out)


# ---------------------------------------------------------------------------
# query().into(cls, rows=True) maps each row of the single statement result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_query_into_rows_returns_list_of_models() -> None:
    rows = [
        {"id": RecordID("person", "a"), "name": "A"},
        {"id": RecordID("person", "b"), "name": "B"},
    ]

    async def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok(rows)

    builder = AsyncQueryBuilder(executor=stub, query="SELECT * FROM person")
    out = await builder.into(Person, rows=True)
    assert [p.name for p in out] == ["A", "B"]
    assert all(isinstance(p, Person) for p in out)


def test_sync_query_into_rows_returns_list_of_models() -> None:
    rows = [
        {"id": RecordID("person", "a"), "name": "A"},
        {"id": RecordID("person", "b"), "name": "B"},
    ]

    def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok(rows)

    builder = SyncQueryBuilder(executor=stub, query="SELECT * FROM person")
    out = builder.into(Person, rows=True)
    assert [p.name for p in out] == ["A", "B"]
    assert all(isinstance(p, Person) for p in out)


def test_sync_query_into_rows_empty_returns_empty_list() -> None:
    def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok([])

    builder = SyncQueryBuilder(executor=stub, query="SELECT * FROM person")
    assert builder.into(Person, rows=True) == []


# ---------------------------------------------------------------------------
# select(..., into=M) mapping via a monkeypatched query_raw (no server)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_select_record_id_into_returns_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncHttpSurrealConnection("http://localhost:8000")
    record = {"id": RecordID("person", "tobie"), "name": "Tobie"}

    async def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok([record])

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)
    out = await conn.select(RecordID("person", "tobie"), into=Person)
    assert isinstance(out, Person)
    assert out.name == "Tobie"


@pytest.mark.asyncio
async def test_async_select_absent_into_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncHttpSurrealConnection("http://localhost:8000")

    async def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok([])

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)
    assert await conn.select(RecordID("person", "missing"), into=Person) is None


@pytest.mark.asyncio
async def test_async_select_table_into_returns_list_of_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncHttpSurrealConnection("http://localhost:8000")
    rows = [
        {"id": RecordID("person", "a"), "name": "A"},
        {"id": RecordID("person", "b"), "name": "B"},
    ]

    async def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok(rows)

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)
    out = await conn.select(Table("person"), into=Person)
    assert isinstance(out, list)
    assert [p.name for p in out] == ["A", "B"]


def test_sync_select_record_id_into_returns_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingHttpSurrealConnection("http://localhost:8000")
    record = {"id": RecordID("person", "tobie"), "name": "Tobie"}

    def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok([record])

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)
    out = conn.select(RecordID("person", "tobie"), into=Person)
    assert isinstance(out, Person)
    assert out.name == "Tobie"


def test_sync_select_absent_into_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingHttpSurrealConnection("http://localhost:8000")

    def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok([])

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)
    assert conn.select(RecordID("person", "missing"), into=Person) is None


def test_sync_select_table_into_returns_list_of_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingHttpSurrealConnection("http://localhost:8000")
    rows = [
        {"id": RecordID("person", "a"), "name": "A"},
        {"id": RecordID("person", "b"), "name": "B"},
    ]

    def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok(rows)

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)
    out = conn.select(Table("person"), into=Person)
    assert isinstance(out, list)
    assert [p.name for p in out] == ["A", "B"]


# ---------------------------------------------------------------------------
# into omitted: behaviour is byte-for-byte unchanged (raw dict / list / None)
# ---------------------------------------------------------------------------


def test_sync_select_without_into_returns_raw_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = BlockingHttpSurrealConnection("http://localhost:8000")
    record = {"id": RecordID("person", "tobie"), "name": "Tobie"}

    def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok([record])

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)
    out = conn.select(RecordID("person", "tobie"))
    assert out == record
    assert not isinstance(out, Person)


@pytest.mark.parametrize(
    "not_a_class",
    [
        pytest.param(5, id="int"),
        pytest.param("Person", id="str"),
        pytest.param(None, id="none"),
        pytest.param([Person], id="list"),
        pytest.param(lambda **kwargs: kwargs, id="function"),
    ],
)
def test_into_rejects_something_that_is_not_a_class(not_a_class: Any) -> None:
    """A caller mistake reports itself, rather than crashing the formatter.

    Everything downstream renders its complaints with ``cls.__name__``, so a
    non-class raised ``AttributeError: 'int' object has no attribute
    '__name__'`` from inside the SDK's own error message - naming neither
    ``into=`` nor the value - and only after the query had already been sent.

    ``TypeError`` rather than a ``SurrealError``: nothing went wrong with the
    database.
    """
    sent = False

    def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        nonlocal sent
        sent = True
        return _ok([])

    builder = SyncQueryBuilder(executor=stub, query="SELECT * FROM person")

    with pytest.raises(TypeError, match="into="):
        builder.into(not_a_class)

    assert not sent, "the query was sent before the argument was checked"


def test_async_into_rejects_something_that_is_not_a_class() -> None:
    """The async builder validates on the call, not on the await."""

    async def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok([])

    builder = AsyncQueryBuilder(executor=stub, query="SELECT * FROM person")

    with pytest.raises(TypeError, match="into="):
        builder.into(5)


def test_select_into_rejects_something_that_is_not_a_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``into=`` keyword paths land on the same check."""
    conn = BlockingHttpSurrealConnection("http://localhost:8000")

    def fake_query_raw(
        query: str, vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return _ok([{"id": RecordID("person", "tobie"), "name": "Tobie"}])

    monkeypatch.setattr(conn, "query_raw", fake_query_raw)

    with pytest.raises(TypeError, match="into="):
        conn.select(RecordID("person", "tobie"), into=5)


def test_into_still_accepts_every_supported_model_kind() -> None:
    """The guard must not turn away the classes that are meant to work."""
    rows = [{"id": RecordID("person", "a"), "name": "A"}]

    def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        return _ok(rows)

    for model in (Person, PlainPerson):
        builder = SyncQueryBuilder(executor=stub, query="SELECT * FROM person")
        assert isinstance(builder.into(model, rows=True)[0], model)


def test_into_rejects_non_record_rows() -> None:
    """A non-record (scalar) row raises a clear error, not an opaque TypeError."""
    from surrealdb.connections.builders import _map_result
    from surrealdb.errors import UnexpectedResponseError

    assert _map_result(Person, None) is None  # absent single record stays None
    with pytest.raises(UnexpectedResponseError):
        _map_result(Person, [1, 2])
    with pytest.raises(UnexpectedResponseError):
        _map_result(Person, 42)


# --------------------------------------------------------------------------- #
#  A record whose fields do not match the model                                #
# --------------------------------------------------------------------------- #
#
# This surfaced as a bare ``TypeError: Person.__init__() got an unexpected
# keyword argument 'active'``, raised from inside the model and naming neither
# ``into=`` nor the record that failed to map - so the obvious reading was that
# the caller had constructed a ``Person`` wrongly somewhere else. The README's
# own ``into=`` example hit it: it declared a two-field ``Person`` and then
# wrote a third field to the table.


def _extra_field_error(model: type) -> str:
    from surrealdb.connections.builders import _map_result
    from surrealdb.errors import UnexpectedResponseError

    with pytest.raises(UnexpectedResponseError) as caught:
        _map_result(model, {"id": RecordID("person", "a"), "active": True})
    return str(caught.value)


@pytest.mark.parametrize("model", [Person, PlainPerson])
def test_an_unmappable_record_names_both_sides(model: type) -> None:
    message = _extra_field_error(model)

    assert f"into={model.__name__}" in message
    # What arrived, and what the model would have taken.
    assert "'active'" in message and "'id'" in message
    assert "'name'" in message


@pytest.mark.parametrize("model", [Person, PlainPerson])
def test_an_unmappable_record_raises_a_surreal_error(model: type) -> None:
    """Catchable through the SDK's own tree, like every other mapping failure.

    A bare ``TypeError`` escaped ``except SurrealError`` entirely.
    """
    from surrealdb.connections.builders import _map_result
    from surrealdb.errors import SurrealError

    with pytest.raises(SurrealError):
        _map_result(model, {"id": RecordID("person", "a"), "active": True})


def test_a_missing_field_is_reported_too() -> None:
    """The other direction: the model wants more than the record carries."""
    message = _extra_field_error(Person)
    assert "into=Person" in message

    from surrealdb.connections.builders import _map_result
    from surrealdb.errors import UnexpectedResponseError

    with pytest.raises(UnexpectedResponseError) as caught:
        _map_result(Person, {"id": RecordID("person", "a")})
    assert "into=Person" in str(caught.value)


def test_the_original_error_is_kept_as_the_cause() -> None:
    """The model's own message is the specific one; it must not be lost."""
    from surrealdb.connections.builders import _map_result
    from surrealdb.errors import UnexpectedResponseError

    with pytest.raises(UnexpectedResponseError) as caught:
        _map_result(Person, {"id": 1, "active": True})

    assert isinstance(caught.value.__cause__, TypeError)


def test_a_record_that_does_match_is_untouched() -> None:
    """The wrapper must not change the successful path."""
    from surrealdb.connections.builders import _map_result

    mapped = _map_result(Person, {"id": RecordID("person", "a"), "name": "A"})

    assert isinstance(mapped, Person)
    assert mapped.name == "A"


def test_a_model_raising_its_own_type_error_is_still_reported() -> None:
    """A constructor that raises ``TypeError`` for its own reasons is reported
    rather than swallowed - the message keeps the model's own text."""
    from surrealdb.connections.builders import _map_result
    from surrealdb.errors import UnexpectedResponseError

    class Fussy:
        def __init__(self, id: Any, name: str) -> None:
            raise TypeError("name must be capitalised")

    with pytest.raises(UnexpectedResponseError) as caught:
        _map_result(Fussy, {"id": 1, "name": "a"})

    assert "name must be capitalised" in str(caught.value)
