"""A bad frame must not brick an async websocket connection.

``_recv_task`` used to end on the first frame it could not handle - a
protocol-level error carrying no ``id``, or anything that failed to decode.
The socket stayed open, so ``connect()`` saw a live socket and no-opped, and
every later request registered a future nothing would ever resolve. With no
timeout on that wait, the caller hung forever and the reported error ("the
connection closed") was wrong: the socket was open the whole time.

The blocking transport was given a deadline when the same class of bug was
found there; these tests cover the async twin, which was missed.
"""

import asyncio

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import SurrealError

# Long enough not to flake on CI, far below an indefinite hang.
_BUDGET_SECONDS = 15.0


@pytest.mark.parametrize(
    ("label", "bad_call"),
    [
        # A protocol-level error: the server cannot correlate this to a
        # request, so its reply carries no `id`.
        (
            "integer too large to encode",
            lambda db: db.query("RETURN $v", {"v": 2**200}),
        ),
        ("record id with a null table", lambda db: db.select(RecordID(None, 1))),
    ],
)
async def test_connection_survives_a_protocol_error(
    async_ws_connection: AsyncWsSurrealConnection,
    label: str,
    bad_call: object,
) -> None:
    """The failure is reported, and the connection keeps working afterwards."""
    with pytest.raises(SurrealError):
        await bad_call(async_ws_connection)  # type: ignore[operator]

    assert async_ws_connection.recv_task is not None
    assert not async_ws_connection.recv_task.done(), f"{label}: reader died"

    result = await asyncio.wait_for(
        async_ws_connection.query("RETURN 42").first(), timeout=_BUDGET_SECONDS
    )
    assert result == 42


async def test_connection_survives_an_undecodable_frame(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """A frame the SDK cannot decode fails one call, not the connection.

    A zero-valued duration is the real-world trigger: the server encodes it as
    an empty CBOR array, which the decoder does not handle.
    """
    with pytest.raises(SurrealError):
        await async_ws_connection.query('RETURN <duration>"0s"').first()

    # The reader itself must survive. Without this the test would still pass
    # via `connect()`'s dead-reader recovery, hiding the very regression it is
    # meant to guard.
    assert async_ws_connection.recv_task is not None
    assert not async_ws_connection.recv_task.done()

    result = await asyncio.wait_for(
        async_ws_connection.query("RETURN 7").first(), timeout=_BUDGET_SECONDS
    )
    assert result == 7
