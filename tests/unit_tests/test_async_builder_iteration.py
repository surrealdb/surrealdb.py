"""``async for row in builder`` streams the rows, and stopping early is clean.

The blocking builders are iterable; this is the same terminator for the async
ones, which are otherwise awaited. It is ``rows()`` and nothing more, so what
needs pinning is the part that is easy to get wrong in a way no caller could
catch: leaving the loop early must close exactly one generator.
"""

import asyncio
import gc
import warnings
from dataclasses import dataclass
from typing import Any

import pytest

from surrealdb import AsyncQueryStream
from surrealdb.connections.builders import (
    AsyncCrudBuilder,
    AsyncInsertBuilder,
    AsyncQueryBuilder,
    _Executor,
)
from surrealdb.data.types.table import Table
from surrealdb.errors import SurrealError
from tests.unit_tests.test_query_streaming import (
    _AsyncChannel,
    begin,
    end,
    finished,
    rows,
)


async def _never(query: str, params: dict[str, Any]) -> dict[str, Any]:
    raise AssertionError("the buffered path must not be reached when streaming")


def _executor(channel: _AsyncChannel) -> _Executor:
    return _Executor(_never, lambda q, p, **kw: AsyncQueryStream(channel.ops(), q, p))


def _channel(values: list[Any]) -> _AsyncChannel:
    return _AsyncChannel([begin(1), rows(0, values), finished(0), end(1)])


def _select(channel: _AsyncChannel, **kwargs: Any) -> AsyncCrudBuilder[Any]:
    return AsyncCrudBuilder(
        executor=_executor(channel),
        operation="SELECT",
        record=Table("t"),
        op_name="select",
        **kwargs,
    )


async def test_iterating_a_crud_builder_streams_its_rows() -> None:
    channel = _channel([{"n": 1}, {"n": 2}])

    assert [row async for row in _select(channel)] == [{"n": 1}, {"n": 2}]
    assert channel.cancelled == []


async def test_iterating_an_insert_builder_streams_its_rows() -> None:
    channel = _channel([{"n": 1}])
    builder: AsyncInsertBuilder[Any] = AsyncInsertBuilder(
        executor=_executor(channel), table="t", data={"n": 1}
    )

    assert [row async for row in builder] == [{"n": 1}]


async def test_iterating_a_query_builder_streams_its_rows() -> None:
    channel = _channel([{"n": 1}, {"n": 2}])
    builder = AsyncQueryBuilder(executor=_executor(channel), query="SELECT * FROM t")

    assert [row async for row in builder] == [{"n": 1}, {"n": 2}]


async def test_iteration_maps_rows_onto_the_model_the_builder_was_given() -> None:
    @dataclass
    class Row:
        n: int

    channel = _channel([{"n": 1}, {"n": 2}])

    builder: AsyncCrudBuilder[list[Row]] = _select(channel, into=Row)

    assert [row async for row in builder] == [Row(1), Row(2)]


async def test_a_builder_is_spent_once_iterated() -> None:
    channel = _channel([{"n": 1}])
    builder = _select(channel)
    assert [row async for row in builder] == [{"n": 1}]

    with pytest.raises(SurrealError, match="after it has executed"):
        _ = [row async for row in builder]


async def test_an_iterated_builder_does_not_warn_when_dropped() -> None:
    channel = _channel([{"n": 1}])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert [row async for row in _select(channel)] == [{"n": 1}]
        gc.collect()

    assert [w for w in caught if issubclass(w.category, RuntimeWarning)] == []


async def test_breaking_out_cancels_the_query_and_raises_nothing() -> None:
    """A bare `break` gives the slot back and puts nothing on the loop's handler.

    Async cleanup happens on the event loop's later passes, and a failure there
    surfaces only as an unhandled-error callback no caller can catch - so the
    loop's handler is watched, and the cancel is waited for rather than assumed.
    """
    caught: list[str] = []
    asyncio.get_running_loop().set_exception_handler(
        lambda loop, context: caught.append(str(context.get("exception")))
    )
    try:
        channel = _AsyncChannel([begin(1), rows(0, [1, 2, 3])])
        async for _ in _select(channel):
            break
        for _ in range(20):
            gc.collect()
            await asyncio.sleep(0.01)
            if channel.cancelled and channel.registry == {}:
                break

        assert caught == []
        assert channel.cancelled == [channel.sent[0].id]
        assert channel.registry == {}
    finally:
        asyncio.get_running_loop().set_exception_handler(None)
