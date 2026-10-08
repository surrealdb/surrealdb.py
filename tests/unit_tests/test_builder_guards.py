"""A builder that is dropped unrun says so, and misuse of one names the fix.

A builder sends nothing until it is terminated, so ``db.delete(Table("t"))`` on
its own deleted nothing and raised nothing. Blocking callers meet that after the
change that made ``select()`` and ``delete()`` return builders; async callers
have always been able to forget the ``await``. These tests pin the three things
that make the mistake visible: the warning on a dropped builder, the clear
``TypeError`` when one is used as if it were its result, and iteration as a
terminator that streams.
"""

import gc
import warnings
from typing import Any

import pytest

from surrealdb.connections.builders import (
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryBuilder,
    SyncCrudBuilder,
    SyncInsertBuilder,
    SyncQueryBuilder,
    _Executor,
)
from surrealdb.data.types.table import Table
from surrealdb.streaming import QueryStream
from tests.unit_tests.test_query_streaming import (
    _SyncChannel,
    begin,
    end,
    finished,
    rows,
)

OK: dict[str, Any] = {"result": [{"status": "OK", "time": "0ns", "result": []}]}


def _run(query: str, params: dict[str, Any]) -> dict[str, Any]:
    return OK


async def _arun(query: str, params: dict[str, Any]) -> dict[str, Any]:
    return OK


def _streaming(channel: _SyncChannel) -> _Executor:
    return _Executor(_run, lambda q, p, **kw: QueryStream(channel.ops(), q, p))


def _crud(executor: Any = _run) -> SyncCrudBuilder[Any]:
    return SyncCrudBuilder(
        executor=executor, operation="SELECT", record=Table("t"), op_name="select"
    )


def _dropped(make: Any) -> list[warnings.WarningMessage]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        builder = make()
        del builder
        gc.collect()
    return [w for w in caught if issubclass(w.category, RuntimeWarning)]


# ------------------------------------------------------------ dropped builders


def test_a_dropped_blocking_crud_builder_warns_where_it_was_made() -> None:
    caught = _dropped(_crud)

    assert len(caught) == 1
    message = str(caught[0].message)
    assert "select()" in message
    assert "never executed" in message
    assert "nothing was sent" in message
    assert __file__ in message, "the warning should point at the caller's line"


@pytest.mark.parametrize(
    "make",
    [
        lambda: SyncInsertBuilder(executor=_run, table="t"),
        lambda: SyncQueryBuilder(executor=_run, query="DELETE t"),
        lambda: AsyncCrudBuilder(
            executor=_arun, operation="DELETE", record=Table("t"), op_name="delete"
        ),
        lambda: AsyncInsertBuilder(executor=_arun, table="t"),
        lambda: AsyncQueryBuilder(executor=_arun, query="DELETE t"),
    ],
    ids=["sync-insert", "sync-query", "async-crud", "async-insert", "async-query"],
)
def test_every_builder_kind_warns_when_dropped(make: Any) -> None:
    assert len(_dropped(make)) == 1


def test_an_async_builder_says_to_await_it() -> None:
    caught = _dropped(
        lambda: AsyncCrudBuilder(
            executor=_arun, operation="DELETE", record=Table("t"), op_name="delete"
        )
    )

    assert "never awaited" in str(caught[0].message)


def test_a_builder_that_ran_does_not_warn() -> None:
    def run() -> None:
        _crud().execute()
        SyncQueryBuilder(executor=_run, query="RETURN 1").execute()
        SyncInsertBuilder(executor=_run, table="t").content({"a": 1})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run()
        gc.collect()

    assert [w for w in caught if issubclass(w.category, RuntimeWarning)] == []


def test_a_builder_whose_execution_failed_does_not_warn() -> None:
    """It was run: the caller got an error, not a silent no-op."""

    def failing(query: str, params: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("down")

    def run() -> None:
        with pytest.raises(ConnectionError):
            _crud(failing).execute()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run()
        gc.collect()

    assert [w for w in caught if issubclass(w.category, RuntimeWarning)] == []


def test_a_builder_that_failed_to_construct_does_not_warn() -> None:
    """`insert()` on a RecordID raises before there is a builder to forget."""
    from surrealdb.data.types.record_id import RecordID
    from surrealdb.errors import SurrealError

    def attempt() -> None:
        with pytest.raises(SurrealError):
            SyncInsertBuilder(executor=_run, table=RecordID("t", 1))  # type: ignore[arg-type]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        attempt()
        gc.collect()

    assert [w for w in caught if issubclass(w.category, RuntimeWarning)] == []


async def test_an_awaited_async_builder_does_not_warn() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await AsyncCrudBuilder(
            executor=_arun, operation="DELETE", record=Table("t"), op_name="delete"
        )
        await AsyncQueryBuilder(executor=_arun, query="RETURN 1")
        gc.collect()

    assert [w for w in caught if issubclass(w.category, RuntimeWarning)] == []


def test_a_streamed_builder_does_not_warn() -> None:
    channel = _SyncChannel([begin(1), rows(0, [{"n": 1}]), finished(0), end(1)])

    def run() -> None:
        assert list(_crud(_streaming(channel)).rows()) == [{"n": 1}]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run()
        gc.collect()

    assert [w for w in caught if issubclass(w.category, RuntimeWarning)] == []


# ------------------------------------------------------------------ misuse


def test_using_a_builder_as_its_result_names_the_fix() -> None:
    builder = _crud()
    builder.execute()

    with pytest.raises(TypeError, match=r"select\(\) returns a builder.*\.execute\(\)"):
        len(builder)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"select\(\) returns a builder.*\.execute\(\)"):
        builder[0]


def test_a_builder_is_still_truthy() -> None:
    """Refusing `len()` must not turn `if builder:` into an error."""
    builder = _crud()
    builder.execute()

    assert bool(builder) is True


# --------------------------------------------------------------- iteration


def test_iterating_a_builder_streams_its_rows() -> None:
    channel = _SyncChannel(
        [begin(1), rows(0, [{"n": 1}, {"n": 2}]), finished(0), end(1)]
    )

    assert list(_crud(_streaming(channel))) == [{"n": 1}, {"n": 2}]
    assert channel.cancelled == []


def test_leaving_the_loop_early_abandons_the_server_side_query() -> None:
    channel = _SyncChannel(
        [begin(1), rows(0, [{"n": i} for i in range(5)]), finished(0), end(1)]
    )

    for row in _crud(_streaming(channel)):
        assert row == {"n": 0}
        break
    gc.collect()

    assert channel.cancelled, "breaking out should have cancelled the query"


def test_closing_the_iterator_closes_the_stream_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not left to the collector: a runtime without refcounting would hold a slot."""
    closed: list[bool] = []
    real_close = QueryStream.close

    def spy(self: QueryStream) -> None:
        closed.append(True)
        real_close(self)

    monkeypatch.setattr(QueryStream, "close", spy)
    channel = _SyncChannel(
        [begin(1), rows(0, [{"n": i} for i in range(5)]), finished(0), end(1)]
    )

    iterator = iter(_crud(_streaming(channel)))
    next(iterator)
    assert closed == []
    iterator.close()  # type: ignore[attr-defined]

    assert closed == [True]


def test_iterating_a_builder_uses_the_rows_it_was_given_a_model_for() -> None:
    from dataclasses import dataclass

    @dataclass
    class Row:
        n: int

    channel = _SyncChannel([begin(1), rows(0, [{"n": 1}]), finished(0), end(1)])
    builder: SyncCrudBuilder[Any] = SyncCrudBuilder(
        executor=_streaming(channel),
        operation="SELECT",
        record=Table("t"),
        op_name="select",
        into=Row,
    )

    assert list(builder) == [Row(n=1)]


def test_a_blocking_insert_builder_streams_like_the_async_one() -> None:
    channel = _SyncChannel([begin(1), rows(0, [{"n": 1}]), finished(0), end(1)])
    builder: SyncInsertBuilder[Any] = SyncInsertBuilder(
        executor=_streaming(channel), table="t", data={"n": 1}
    )

    assert list(builder.rows()) == [{"n": 1}]
