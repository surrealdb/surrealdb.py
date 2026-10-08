"""``QueryError.timeout`` reports the timeout the statement exceeded.

It was annotated ``dict[str, Any] | None`` and documented as
``{"secs": ..., "nanos": ...}``, and its body only accepted a ``dict`` - but the
server sends a ``Duration``, so the property returned ``None`` for every timeout
on every transport. The attribute existed, was documented, and could not report
anything.

``is_timed_out`` was always correct, which is part of why this went unnoticed:
the branch a caller is most likely to write worked, and only the detail inside
it was empty.

The server-backed tests below need a server that reports a *structured* timeout.
2.x does not: the same query comes back as an ``InternalError`` with no details,
so there is no duration to read and nothing for these to assert. They gate on
that capability rather than on a version number, so they begin running by
themselves if 2.x ever gains the detail, and skip rather than fail on a 3.x
build that somehow lacks it. The unit-level tests at the bottom need no server
and never skip.
"""

from typing import Any

import pytest

from surrealdb import Duration
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import QueryError

# Sleeps far longer than the timeout it is given, so the server has to cut it
# off rather than the statement happening to be slow.
TIMES_OUT = "SELECT sleep(2s) FROM 1 TIMEOUT 10ms"

# Resolved once: it cannot change while the suite runs, and the probe costs a
# connection plus a deliberate timeout.
_STRUCTURED: bool | None = None


def _probe_structured_timeout(connection_params: dict[str, Any]) -> bool:
    connection = BlockingWsSurrealConnection(connection_params["ws_url"])
    try:
        connection.signin(connection_params["vars_params"])
        connection.use(
            namespace=connection_params["namespace"],
            database=connection_params["database_name"],
        )
        try:
            connection.query(TIMES_OUT).execute()
        except QueryError as error:
            return error.is_timed_out
        except Exception:
            return False
        return False
    finally:
        connection.close()


@pytest.fixture
def needs_structured_timeout(connection_params: dict[str, Any]) -> None:
    """Skip unless the server reports a timeout as a structured ``QueryError``."""
    global _STRUCTURED
    if _STRUCTURED is None:
        _STRUCTURED = _probe_structured_timeout(connection_params)
    if not _STRUCTURED:
        pytest.skip(
            "server reports timeouts without structured details (2.x); "
            "there is no duration to read"
        )


def _timed_out(connection: object) -> QueryError:
    with pytest.raises(QueryError) as caught:
        connection.query(TIMES_OUT).execute()  # type: ignore[attr-defined]
    assert caught.value.is_timed_out
    return caught.value


def test_the_timeout_is_a_duration_not_none(
    blocking_ws_connection: BlockingWsSurrealConnection,
    needs_structured_timeout: None,
) -> None:
    error = _timed_out(blocking_ws_connection)

    assert isinstance(error.timeout, Duration)


def test_the_duration_is_the_one_the_statement_asked_for(
    blocking_ws_connection: BlockingWsSurrealConnection,
    needs_structured_timeout: None,
) -> None:
    """10ms in the statement, 10ms back - not merely "some Duration"."""
    error = _timed_out(blocking_ws_connection)

    assert error.timeout is not None
    assert error.timeout.elapsed == 10_000_000
    assert error.timeout.to_string() == "10ms"


def test_the_blocking_http_transport_agrees(
    blocking_http_connection: BlockingHttpSurrealConnection,
    needs_structured_timeout: None,
) -> None:
    error = _timed_out(blocking_http_connection)

    assert isinstance(error.timeout, Duration)
    assert error.timeout.elapsed == 10_000_000


async def test_the_async_transports_agree(
    async_ws_connection: AsyncWsSurrealConnection,
    async_http_connection: AsyncHttpSurrealConnection,
    needs_structured_timeout: None,
) -> None:
    for connection in (async_ws_connection, async_http_connection):
        with pytest.raises(QueryError) as caught:
            await connection.query(TIMES_OUT).execute()

        assert caught.value.is_timed_out
        assert isinstance(caught.value.timeout, Duration)
        assert caught.value.timeout.elapsed == 10_000_000


@pytest.mark.parametrize(
    "kind", ("NotExecuted", "Cancelled", "TransactionConflict", "Unknown")
)
def test_it_is_none_for_the_kinds_it_does_not_describe(kind: str) -> None:
    """``timeout`` must not report a duration for a non-timeout failure.

    Unit level because the server does not offer a convenient non-timeout
    ``QueryError``: a failing statement inside a transaction surfaces as the
    first error raised - a ``ThrownError`` for ``THROW`` - rather than as the
    ``NotExecuted`` detail on the statements that followed it.
    """
    error = QueryError(
        "Query",
        "something else went wrong",
        details={"kind": kind, "details": {"duration": Duration(5)}},
    )

    assert error.timeout is None


def test_a_secs_nanos_mapping_is_accepted_and_converted() -> None:
    """No supported version sends this shape - the old annotation promised it.

    Converted rather than refused so that a server which ever did send it would
    be read correctly, and unit-level because nothing produces it to test
    against.
    """
    error = QueryError(
        "Query",
        "timed out",
        details={
            "kind": "TimedOut",
            "details": {"duration": {"secs": 1, "nanos": 500_000_000}},
        },
    )

    assert error.timeout == Duration(1_500_000_000)


def test_an_unrecognised_duration_shape_is_none_rather_than_a_crash() -> None:
    """A decode surprise must not turn an error into a different error."""
    error = QueryError(
        "Query",
        "timed out",
        details={"kind": "TimedOut", "details": {"duration": "10ms"}},
    )

    assert error.timeout is None
