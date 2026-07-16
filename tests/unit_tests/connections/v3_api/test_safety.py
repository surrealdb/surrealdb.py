"""
Tests for the v3.0 builder safety properties:

- idempotent execution (no duplicate server round-trips on repeated awaits
  or `.into()` after `.execute()`)
- safe ``__repr__`` / ``__str__`` (no auto-execute on debugger inspection)
- string injection rejection in resource targets
"""

import asyncio
import threading
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from typing import Any

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.builders import (
    AsyncCrudBuilder,
    AsyncQueryBuilder,
)
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import SurrealError
from surrealdb.request_message.message import RequestMessage


@pytest.fixture(autouse=True)
async def _async_setup(
    async_ws_connection: AsyncWsSurrealConnection,
) -> AsyncGenerator[None, None]:
    await async_ws_connection.query(
        "REMOVE TABLE IF EXISTS counter;"
        "DEFINE TABLE counter SCHEMALESS;"
        "DEFINE FIELD n ON counter TYPE int DEFAULT 0;"
    )
    yield
    await async_ws_connection.query("REMOVE TABLE IF EXISTS counter;")


@pytest.fixture(autouse=True)
def _sync_setup(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    blocking_ws_connection.query(
        "REMOVE TABLE IF EXISTS counter;"
        "DEFINE TABLE counter SCHEMALESS;"
        "DEFINE FIELD n ON counter TYPE int DEFAULT 0;"
    ).execute()
    yield
    blocking_ws_connection.query("REMOVE TABLE IF EXISTS counter;").execute()


# ---------------------------------------------------------------------------
# Idempotency: async builders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_query_awaited_twice_runs_once(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """Awaiting the same async query builder twice must reuse the cache."""
    await async_ws_connection.query("CREATE counter:trace SET n = 1")
    builder = async_ws_connection.query(
        "UPDATE counter:trace SET n = n + 1 RETURN AFTER"
    )
    first = await builder
    second = await builder
    # Both await results are identical (same cached fetch)
    assert first == second
    # Server-side, the UPDATE only ran once - n is 2, not 3
    after = await async_ws_connection.query("SELECT n FROM counter:trace").first()
    assert after[0]["n"] == 2


@pytest.mark.asyncio
async def test_async_query_concurrent_awaits_run_once(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.query("CREATE counter:concurrent SET n = 0")
    builder = async_ws_connection.query(
        "UPDATE counter:concurrent SET n = n + 1 RETURN AFTER"
    )
    a, b, c = await asyncio.gather(builder, builder, builder)
    assert a == b == c
    after = await async_ws_connection.query("SELECT n FROM counter:concurrent").first()
    assert after[0]["n"] == 1


@pytest.mark.asyncio
async def test_async_crud_awaited_twice_runs_once(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    builder = async_ws_connection.create("counter:once", {"n": 1})
    first = await builder
    second = await builder
    assert first == second
    # If the CREATE had run twice the second await would have raised on
    # the duplicate record - reaching this point proves it ran once.


# ---------------------------------------------------------------------------
# Idempotency: query().into() shares parent's fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_into_shares_parent_fetch(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    @dataclass
    class Pair:
        a: int
        b: int

    await async_ws_connection.query("CREATE counter:share SET n = 7")
    builder = async_ws_connection.query(
        "UPDATE counter:share SET n = n + 1 RETURN AFTER;RETURN 99;"
    )
    direct = await builder
    mapped = await builder.into(Pair)
    # `direct` is a list [update_list, 99]; `mapped` repacks the same
    # values into Pair. They reference the same cached fetch.
    assert direct[0] == mapped.a
    assert direct[1] == mapped.b
    # Server-side, the UPDATE ran only once - the n value is 8 (was 7, +1).
    after = await async_ws_connection.query("SELECT n FROM counter:share").first()
    assert after[0]["n"] == 8


def test_sync_into_shares_parent_fetch(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    @dataclass
    class Pair:
        a: int
        b: int

    blocking_ws_connection.query("CREATE counter:sync_share SET n = 5").execute()
    builder = blocking_ws_connection.query(
        "UPDATE counter:sync_share SET n = n + 1 RETURN AFTER;RETURN 11;"
    )
    direct = builder.execute()
    mapped = builder.into(Pair)
    assert direct[0] == mapped.a
    assert direct[1] == mapped.b
    after = blocking_ws_connection.query("SELECT n FROM counter:sync_share").first()
    assert after[0]["n"] == 6


# ---------------------------------------------------------------------------
# No-data builders are inert until run
# ---------------------------------------------------------------------------


def test_sync_builder_repr_does_not_execute(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """A no-data builder must not run until a clause / execute() is called.

    Sync builders carry no magic dunders, so ``repr()``/``str()`` (and any
    other incidental inspection) can never fire the pending operation.
    """
    blocking_ws_connection.query("CREATE counter:repr_safe SET n = 1").execute()
    blocking_ws_connection.update("counter:repr_safe").merge({"n": 999})
    # Fresh no-data builder - just inspecting must not execute it.
    pending = blocking_ws_connection.update("counter:repr_safe")
    repr(pending)
    str(pending)
    after = blocking_ws_connection.query("SELECT n FROM counter:repr_safe").first()
    # n is whatever the previous terminal merge set - the pending builder
    # above never ran, so it did not clobber the value.
    assert after[0]["n"] == 999


# ---------------------------------------------------------------------------
# String-target injection rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_unsafe_string_record_rejected(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """A semicolon in a str target must be rejected up-front."""
    with pytest.raises(SurrealError):
        # Range-syntax fallback path - ".." present so we don't parse as
        # record-id - then the unsafe-character check fires.
        await async_ws_connection.delete("counter:1..10; REMOVE TABLE counter;")


def test_sync_unsafe_string_record_rejected(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    with pytest.raises(SurrealError):
        blocking_ws_connection.delete("counter:1..10; REMOVE TABLE counter;")


@pytest.mark.asyncio
async def test_string_record_id_bound_safely(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """A normal `"table:id"` string is bound as a parameterised RecordID.

    select() of a single record-id string unwraps to the record dict.
    """
    await async_ws_connection.create("counter:abc", {"n": 42})
    out = await async_ws_connection.select("counter:abc")
    assert isinstance(out, dict)
    assert out["n"] == 42


@pytest.mark.asyncio
async def test_table_string_with_safe_chars_works(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    await async_ws_connection.create("counter").content({"n": 1})
    rows = await async_ws_connection.select("counter")
    assert isinstance(rows, list)
    assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Reconfiguration after execution must raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_crud_reconfigure_after_execute_raises(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """Calling another clause method after `await` must raise.

    Without this check a re-awaited builder would silently return the
    *first* cached result, ignoring the new clause, which is one of the
    most insidious shapes of a stale-cache bug.
    """
    builder = async_ws_connection.create("counter:reconfig", {"n": 1})
    await builder
    with pytest.raises(SurrealError, match="Cannot reconfigure"):
        builder.merge({"n": 2})
    with pytest.raises(SurrealError, match="Cannot reconfigure"):
        builder.content({"n": 3})


@pytest.mark.asyncio
async def test_async_insert_reconfigure_after_execute_raises(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    builder = async_ws_connection.insert("counter", {"n": 1})
    await builder
    with pytest.raises(SurrealError, match="Cannot reconfigure"):
        builder.relation()
    with pytest.raises(SurrealError, match="Cannot reconfigure"):
        builder.content({"n": 2})


def test_sync_crud_reconfigure_after_execute_raises(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    # No-data create returns a builder; run it, then reconfiguring raises.
    builder = blocking_ws_connection.create("counter:sync_reconfig")
    builder.execute()  # explicit consumption
    with pytest.raises(SurrealError, match="Cannot reconfigure"):
        builder.merge({"n": 2})


def test_sync_insert_reconfigure_after_execute_raises(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    # No-data insert returns a builder; .content() runs it, then
    # reconfiguring raises.
    builder = blocking_ws_connection.insert("counter")
    builder.content({"n": 1})
    with pytest.raises(SurrealError, match="Cannot reconfigure"):
        builder.relation()


# ---------------------------------------------------------------------------
# Sync `query().into()` and `.execute()` share one cached fetch
# ---------------------------------------------------------------------------


def test_sync_query_into_and_execute_share_fetch(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """`.into(cls)` and `.execute()` on one builder share a single fetch."""

    @dataclass
    class Pair:
        a: int
        b: int

    blocking_ws_connection.query("CREATE counter:into_repr SET n = 1").execute()
    builder = blocking_ws_connection.query("RETURN 10; RETURN 20;")
    mapped = builder.into(Pair)
    assert mapped == Pair(a=10, b=20)
    # Re-executing returns the same cached list without re-fetching.
    assert builder.execute() == [10, 20]


# ---------------------------------------------------------------------------
# Compound record-id strings are rejected
# ---------------------------------------------------------------------------


def test_string_record_id_with_extra_colons_rejected(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """`"table:part:rest"` is ambiguous - require an explicit RecordID.

    Single-colon partition can't reliably round-trip with the server's
    literal-parsing rules for compound IDs, so we refuse to guess.
    """
    with pytest.raises(SurrealError, match="Ambiguous record-id"):
        blocking_ws_connection.delete("counter:part:rest")


# ---------------------------------------------------------------------------
# No magic auto-execute: inspecting a builder never runs it
# ---------------------------------------------------------------------------


def test_sync_builder_has_no_magic_auto_execute(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """Sync builders carry no auto-executing dunders.

    ``bool()`` on a builder is plain object truthiness (always True) and
    must NOT run the operation; only ``.execute()`` / a clause method does.
    Pins the eager-model contract so a future refactor that re-introduces
    magic consumption breaks here and forces an explicit decision.
    """
    blocking_ws_connection.query("CREATE counter:bool_check SET n = 5").execute()
    builder = blocking_ws_connection.query(
        "UPDATE counter:bool_check SET n = n + 1 RETURN AFTER"
    )
    assert bool(builder) is True  # object truthiness - does NOT execute
    for magic in ("__bool__", "__eq__", "__getitem__", "__iter__", "__len__"):
        assert magic not in type(builder).__dict__
    # The UPDATE never ran: n is still 5.
    after = blocking_ws_connection.query("SELECT n FROM counter:bool_check").first()
    assert after[0]["n"] == 5
    # Explicit execution runs it exactly once.
    builder.execute()
    after = blocking_ws_connection.query("SELECT n FROM counter:bool_check").first()
    assert after[0]["n"] == 6


# ---------------------------------------------------------------------------
# Sync builders are thread-safe for cache reads
# ---------------------------------------------------------------------------


def test_sync_builder_thread_safe_run_once(
    blocking_ws_connection: BlockingWsSurrealConnection,
    _sync_setup: None,
) -> None:
    """Consuming the same builder from N threads must issue exactly 1 RPC.

    Without the per-builder lock, multiple threads racing through
    ``_run_once`` would each see ``_executed=False`` and fire the
    operation independently - corrupting the cache and (for mutations)
    duplicating side effects.
    """
    blocking_ws_connection.query("CREATE counter:thread_safe SET n = 0").execute()
    builder = blocking_ws_connection.query(
        "UPDATE counter:thread_safe SET n = n + 1 RETURN AFTER"
    )

    results: list[object] = []
    barrier = threading.Barrier(8)

    def consume() -> None:
        barrier.wait()  # release all threads simultaneously
        results.append(builder.execute())

    threads = [threading.Thread(target=consume) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every thread sees the *same* cached result.
    assert all(r == results[0] for r in results)
    # And the UPDATE ran exactly once - n is 1, not 8.
    after = blocking_ws_connection.query("SELECT n FROM counter:thread_safe").first()
    assert after[0]["n"] == 1


# ---------------------------------------------------------------------------
# Async cancellation does not leak CancelledError to peer awaiters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_cancellation_does_not_poison_peer_awaiters() -> None:
    """Cancelling the initiating awaiter must not cancel concurrent peers.

    Stub-executor variant: holds the RPC blocked on an ``asyncio.Event``
    so the cancellation point is deterministic - no event-loop ordering
    races. This actually exercises ``_AsyncCachedRunner.run``'s
    ``except CancelledError`` branch every run, instead of relying on
    timing to catch the initiator mid-flight.

    Peer tasks awaiting the same builder must see a ``SurrealError``
    describing the cancellation, never a phantom ``CancelledError`` from
    a cancellation they did not request.
    """
    started = asyncio.Event()
    release = asyncio.Event()

    async def stub_executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
        started.set()
        await release.wait()
        return {"result": [{"status": "OK", "result": 42}]}

    builder = AsyncQueryBuilder(executor=stub_executor, query="RETURN 42")
    initiator = asyncio.create_task(builder.execute())
    peer = asyncio.create_task(builder.execute())

    # Wait until the executor is actually running, then yield once more
    # so the peer task has had a chance to attach to the shared future.
    await started.wait()
    await asyncio.sleep(0)

    initiator.cancel()
    with pytest.raises(asyncio.CancelledError):
        await initiator

    # Peer must see SurrealError, never CancelledError.
    with pytest.raises(SurrealError, match="cancel"):
        await peer

    # Defensive cleanup; the stub coroutine was abandoned at cancel time
    # but `release.set()` keeps the test free of "coroutine was never
    # awaited" warnings on some asyncio implementations.
    release.set()


# ---------------------------------------------------------------------------
# Reconfigure-after-cancellation IS allowed (cache was reset)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_reconfigure_after_cancellation_is_allowed() -> None:
    """Cancelled builders reset their runner cache - reconfigure IS permitted.

    Pin the behaviour: a cancelled-and-retried builder accepts a fresh
    clause method without raising. This is the deliberate flip-side of
    the after-execute reconfigure ban
    (test_async_crud_reconfigure_after_execute_raises). If we ever
    change the policy, this test forces an explicit decision and a docs
    update.
    """
    started = asyncio.Event()
    release = asyncio.Event()

    async def stub(query: str, params: dict[str, Any]) -> dict[str, Any]:
        started.set()
        await release.wait()
        return {"result": [{"status": "OK", "result": [{"id": "t:1"}]}]}

    builder: AsyncCrudBuilder[Any] = AsyncCrudBuilder(
        executor=stub,
        operation="UPDATE",
        record=RecordID("t", 1),
        op_name="update",
        data={"x": 1},
    )
    task = asyncio.create_task(builder.execute())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Cache was reset on cancellation → reconfigure must NOT raise.
    builder.merge({"y": 2})

    release.set()


# ---------------------------------------------------------------------------
# Reverse-order .into() then await also shares the cached fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_into_then_await_shares_fetch(
    async_ws_connection: AsyncWsSurrealConnection,
    _async_setup: None,
    _sync_setup: None,
) -> None:
    """``.into()`` first, then ``await`` - must share the cached fetch.

    The companion ``test_async_into_shares_parent_fetch`` test covers
    ``await q`` first then ``await q.into(T)``; this pins the reverse
    direction so the cache contract is symmetric in both orderings.
    """

    @dataclass
    class Pair:
        a: int
        b: int

    await async_ws_connection.query("CREATE counter:reverse SET n = 3")
    builder = async_ws_connection.query(
        "UPDATE counter:reverse SET n = n + 1 RETURN AFTER;RETURN 77;"
    )
    mapped = await builder.into(Pair)
    direct = await builder
    assert isinstance(direct, list)
    assert direct[0] == mapped.a
    assert direct[1] == mapped.b
    after = await async_ws_connection.query("SELECT n FROM counter:reverse").first()
    assert isinstance(after, list)
    assert after[0]["n"] == 4  # update ran exactly once


# ---------------------------------------------------------------------------
# Negative-int record-id strings are NOT silently coerced to int
# ---------------------------------------------------------------------------


def test_string_record_id_negative_int_kept_as_string() -> None:
    """``"user:-5"`` becomes a string-id ``RecordID``, not an int.

    The numeric-coercion path only fires for non-negative digit ids;
    negative-int literal semantics in SurrealQL are version-dependent
    so we don't guess. Users who genuinely want an int id pass
    ``RecordID("user", -5)`` explicitly.
    """
    from surrealdb.connections.builders import _string_to_record_id

    rec = _string_to_record_id("counter:-5", "_resource")
    assert rec.table_name == "counter"
    assert rec.id == "-5"
    assert isinstance(rec.id, str)

    # Sanity: non-negative numeric ids still coerce to int.
    rec_pos = _string_to_record_id("counter:42", "_resource")
    assert rec_pos.id == 42
    assert isinstance(rec_pos.id, int)


def test_string_record_id_unicode_digits_kept_as_string() -> None:
    """``"counter:²"`` (unicode digit) is NOT coerced to int.

    ``str.isdigit()`` returns True for unicode digits like ``²`` but
    ``int()`` rejects most of them. The previous coercion path used
    just ``isdigit()``; the new ``isascii() and isdigit()`` check keeps
    pathological unicode-digit strings as string ids without crashing.
    """
    from surrealdb.connections.builders import _string_to_record_id

    rec = _string_to_record_id("counter:²", "_resource")
    assert rec.table_name == "counter"
    assert rec.id == "²"
    assert isinstance(rec.id, str)


# ---------------------------------------------------------------------------
# info() record-auth fallback regression guard
# ---------------------------------------------------------------------------


def test_blocking_http_info_record_auth_fallback(
    blocking_http_connection: BlockingHttpSurrealConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``info()`` must fall back to ``SELECT * FROM $auth`` when ``INFO``
    returns ``"No result found"`` (record-auth scenario).

    Pin the regression: the v3 builder migration broke this once because
    ``self.query(...)`` returns a lazy ``SyncQueryBuilder``, not a list,
    so the ``isinstance(auth_response, list)`` guard always evaluated
    False and the fallback became dead code. Without ``.execute()`` on
    the builder, record-auth users see ``parse_rpc_error`` instead of
    their ``$auth`` record.
    """
    auth_record = {"id": "user:tobie", "name": "Tobie"}
    seen: list[str] = []

    def fake_send(
        message: RequestMessage,
        operation: str,
        bypass: bool = False,
    ) -> dict[str, Any]:
        seen.append(operation)
        if operation == "getting database information":
            # Reproduce the record-auth signal SurrealDB sends when INFO
            # has nothing to return: error code -32000, "No result found".
            return {
                "id": message.id,
                "error": {"code": -32000, "message": "No result found"},
            }
        if operation == "query":
            # The fallback ``SELECT * FROM $auth`` lands here via
            # ``query_raw`` -> ``_send``.
            return {
                "id": message.id,
                "result": [{"status": "OK", "result": [auth_record]}],
            }
        raise AssertionError(f"unexpected _send operation: {operation!r}")

    monkeypatch.setattr(blocking_http_connection, "_send", fake_send)

    result = blocking_http_connection.info()
    assert result == auth_record
    # Both calls happened, in the right order: INFO first, then the
    # fallback SELECT.
    assert seen == ["getting database information", "query"]
