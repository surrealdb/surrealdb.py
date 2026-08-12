"""A protocol error the server could not correlate reaches only its own request.

When SurrealDB cannot parse a frame it answers with an error carrying no ``id``,
because it never read one. Exactly one request is affected - the one whose frame
was rejected, which is the one that will never be answered - and the SDK cannot
tell from the wire which it is.

Failing every pending future turned one bad request into N failures. Holding the
error until *whoever times out next* collects it fixed that and introduced a
subtler version of the same bug: a caller that abandons its request before the
deadline (an application-level timeout, a cancelled task) never collects the
error, so it sat there and was handed to an unrelated request minutes later,
telling a perfectly valid query it had a parse error.

The error is now bound to the request ids that were in flight when it arrived.
Anything started afterwards has its own reply coming and can never be the one
the server rejected.

Server-free: this is about which pending request the error is routed to, so it
is exercised through the routing helpers directly rather than by waiting out a
30-second RPC deadline.
"""

import asyncio

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.errors import SurrealError, ValidationError

WS_URL = "ws://localhost:8000"


def _connection() -> AsyncWsSurrealConnection:
    """A connection object with no socket - nothing here touches the network."""
    return AsyncWsSurrealConnection(WS_URL)


def _pending(connection: AsyncWsSurrealConnection, *query_ids: str) -> None:
    """Register *query_ids* as in flight, as ``_send`` does."""
    loop = asyncio.get_running_loop()
    for query_id in query_ids:
        connection.qry[query_id] = loop.create_future()


async def test_a_single_in_flight_request_is_failed_immediately() -> None:
    """With one candidate there is no ambiguity, so it need not wait."""
    connection = _connection()
    _pending(connection, "only")
    error = ValidationError(kind="Validation", message="Parse error")

    connection._deliver_uncorrelated(error)

    assert connection.qry.get("only") is None, "the request was not resolved"
    assert connection._uncorrelated_error is None, "nothing should be held"


async def test_the_error_is_held_when_several_are_in_flight() -> None:
    connection = _connection()
    _pending(connection, "a", "b", "c")
    error = ValidationError(kind="Validation", message="Parse error")

    connection._deliver_uncorrelated(error)

    # No future is resolved: the other two still have their own replies coming.
    assert all(not fut.done() for fut in connection.qry.values())
    assert connection._uncorrelated_error is error
    assert connection._uncorrelated_for == {"a", "b", "c"}


async def test_only_a_request_that_was_in_flight_can_collect_it() -> None:
    """The defect: a later, unrelated request used to be handed this error."""
    connection = _connection()
    _pending(connection, "a", "b")
    error = ValidationError(kind="Validation", message="Parse error")
    connection._deliver_uncorrelated(error)

    assert connection._take_uncorrelated("later") is None, (
        "a request started after the failure collected an error that cannot "
        "possibly be about it"
    )
    # And it is still there for one that could be responsible.
    assert connection._take_uncorrelated("a") is error


async def test_collecting_it_once_consumes_it() -> None:
    connection = _connection()
    _pending(connection, "a", "b")
    error = ValidationError(kind="Validation", message="Parse error")
    connection._deliver_uncorrelated(error)

    assert connection._take_uncorrelated("a") is error
    assert connection._take_uncorrelated("b") is None, "delivered twice"


async def test_an_abandoned_candidate_set_drops_the_error() -> None:
    """Nobody left to blame means the error must not outlive them.

    This is exactly the leak: both candidates gave up before their deadline, so
    without pruning the error waited for an unrelated request much later.
    """
    connection = _connection()
    _pending(connection, "a", "b")
    connection._deliver_uncorrelated(
        ValidationError(kind="Validation", message="Parse error")
    )

    # Both callers abandon their requests, as `_send`'s finally does.
    connection.qry.pop("a")
    connection._prune_uncorrelated()
    assert connection._uncorrelated_error is not None, "one candidate remains"

    connection.qry.pop("b")
    connection._prune_uncorrelated()

    assert connection._uncorrelated_error is None
    assert connection._uncorrelated_for == set()
    assert connection._take_uncorrelated("anything") is None


async def test_a_surviving_candidate_keeps_the_error() -> None:
    """Pruning must not throw the error away while it can still be delivered."""
    connection = _connection()
    _pending(connection, "a", "b")
    error = ValidationError(kind="Validation", message="Parse error")
    connection._deliver_uncorrelated(error)

    connection.qry.pop("a")
    connection._prune_uncorrelated()

    assert connection._take_uncorrelated("b") is error


async def test_closing_forgets_a_held_error() -> None:
    """A new socket is a new conversation; nothing carries over."""
    connection = _connection()
    _pending(connection, "a", "b")
    connection._deliver_uncorrelated(
        ValidationError(kind="Validation", message="Parse error")
    )

    await connection.close()

    assert connection._uncorrelated_error is None
    assert connection._uncorrelated_for == set()


@pytest.mark.parametrize("error", [ValidationError(kind="Validation", message="x")])
def test_the_held_error_is_a_surreal_error(error: SurrealError) -> None:
    """Whatever is delivered stays inside the documented exception tree."""
    assert isinstance(error, SurrealError)
