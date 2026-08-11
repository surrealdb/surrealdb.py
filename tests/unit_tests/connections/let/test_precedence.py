"""A query's own variables beat ``let()``, and the caller's dict is not touched.

The HTTP transports have no server-side session to hold ``let()`` bindings, so
they replay them as query parameters. Which side won when a name appeared on
both was therefore an SDK decision, and it was the wrong one: the session
values were written *over* the caller's, so

    db.let("limit", 99)
    db.query("RETURN $limit", {"limit": 5})

returned ``99`` on HTTP and ``5`` on a 3.x websocket - the caller's own
argument silently ignored, on one transport only.

On the websocket transports ``let()`` is a real RPC, so the *server* decides,
and the two supported majors decide differently: 3.x shadows the session
binding with the query's own variables, 2.x does not. That is pinned below
rather than skipped, so a change in either server is visible here.

The same line merged into the dict the caller passed, so a ``let()`` binding -
including anything sensitive someone had bound to the session - was left in an
object the caller still held and could reuse for an unrelated query. Only
``query_raw`` reached this: ``query`` hands its variables to a builder, which
copies them. Both are public, and the copy in the builder is incidental, so
both are covered here.

Run against every transport rather than just the two that were broken, so the
four cannot drift apart again.
"""

from typing import Any

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

# ------------------------------------------------------- per-query precedence


def test_blocking_http_query_vars_beat_let(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    blocking_http_connection.let("limit", 99)

    assert blocking_http_connection.query("RETURN $limit", {"limit": 5}).first() == 5
    # The binding is only shadowed for that one query, not consumed.
    assert blocking_http_connection.query("RETURN $limit").first() == 99


async def test_async_http_query_vars_beat_let(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.let("limit", 99)

    assert await async_http_connection.query("RETURN $limit", {"limit": 5}).first() == 5
    assert await async_http_connection.query("RETURN $limit").first() == 99


def _shadows_session_vars(version: str) -> bool:
    """Whether this server lets a query's own variables shadow ``let()``."""
    text = (version or "").strip().lower()
    for prefix in ("surrealdb-", "v"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    try:
        return int(text.split(".")[0]) >= 3
    except (ValueError, IndexError):
        return False


def test_blocking_ws_precedence_is_the_servers_to_decide(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.let("limit", 99)

    outcome = blocking_ws_connection.query("RETURN $limit", {"limit": 5}).first()

    expected = 5 if _shadows_session_vars(blocking_ws_connection.version()) else 99
    assert outcome == expected
    # Either way the binding survives the query that shadowed it.
    assert blocking_ws_connection.query("RETURN $limit").first() == 99


async def test_async_ws_precedence_is_the_servers_to_decide(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await async_ws_connection.let("limit", 99)

    outcome = await async_ws_connection.query("RETURN $limit", {"limit": 5}).first()

    expected = 5 if _shadows_session_vars(await async_ws_connection.version()) else 99
    assert outcome == expected
    assert await async_ws_connection.query("RETURN $limit").first() == 99


# ------------------------------------------------------ caller dict isolation


def test_blocking_http_query_raw_does_not_touch_the_callers_vars(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    blocking_http_connection.let("session_secret", "s3cret")
    mine: dict[str, Any] = {"name": "alice"}

    blocking_http_connection.query_raw("RETURN $name", mine)

    assert mine == {"name": "alice"}


async def test_async_http_query_raw_does_not_touch_the_callers_vars(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.let("session_secret", "s3cret")
    mine: dict[str, Any] = {"name": "alice"}

    await async_http_connection.query_raw("RETURN $name", mine)

    assert mine == {"name": "alice"}


def test_blocking_http_query_does_not_touch_the_callers_vars(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    """``query`` is only safe because the builder copies; pin that too."""
    blocking_http_connection.let("session_secret", "s3cret")
    mine: dict[str, Any] = {"name": "alice"}

    blocking_http_connection.query("RETURN $name", mine).execute()

    assert mine == {"name": "alice"}


def test_blocking_http_reusing_a_vars_dict_does_not_leak_session_state(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    """The end-to-end shape of the mutation bug, without inspecting the dict.

    A caller who keeps one ``vars`` dict around and reuses it got every
    ``let()`` binding folded into it by the first ``query_raw``, so a *later*
    query naming one of those variables still resolved it - even after the
    binding had been ``unset()``.
    """
    reused: dict[str, Any] = {"name": "alice"}
    blocking_http_connection.let("ghost", "haunting")
    blocking_http_connection.query_raw("RETURN $name", reused)

    blocking_http_connection.unset("ghost")

    # `$ghost` is unbound now, so it resolves to NONE. Anything else means the
    # value came back out of the caller's own dict.
    response = blocking_http_connection.query_raw("RETURN $ghost", reused)
    assert response["result"][0]["result"] is None


# ------------------------------------------------ unset() of an unbound name


def test_blocking_http_unset_unknown_key_is_a_no_op(
    blocking_http_connection: BlockingHttpSurrealConnection,
) -> None:
    """Only HTTP raised here, and with ``KeyError`` - outside ``SurrealError``."""
    blocking_http_connection.unset("never_bound")


async def test_async_http_unset_unknown_key_is_a_no_op(
    async_http_connection: AsyncHttpSurrealConnection,
) -> None:
    await async_http_connection.unset("never_bound")


def test_blocking_ws_unset_unknown_key_is_a_no_op(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    blocking_ws_connection.unset("never_bound")


async def test_async_ws_unset_unknown_key_is_a_no_op(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    await async_ws_connection.unset("never_bound")
