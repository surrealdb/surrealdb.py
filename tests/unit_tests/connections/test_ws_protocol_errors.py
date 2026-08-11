"""A protocol-level websocket error must raise, not hang.

SurrealDB answers a request it cannot parse or correlate with an error frame
carrying no top-level ``id``. ``_send`` classifies any id-less frame as a
live-query notification, so those replies were discarded and the receive loop
blocked on ``recv()`` forever - an unbounded hang with no timeout, on ordinary
calls such as passing an out-of-range integer.
"""

import threading
import time
from typing import Any

import pytest

from surrealdb.connections import blocking_ws
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID
from surrealdb.errors import SurrealError, TransportTimeoutError

# Generous enough that a slow CI box does not flake, far below the hang.
_BUDGET_SECONDS = 20.0


def _within_budget(call: Any) -> tuple[str, Any]:
    """Run *call* on a worker thread so a hang fails instead of blocking pytest."""
    outcome: dict[str, tuple[str, Any]] = {}

    def run() -> None:
        try:
            outcome["r"] = ("returned", call())
        except SurrealError as error:
            outcome["r"] = ("surreal-error", error)
        except Exception as error:  # noqa: BLE001 - reporting, not handling
            outcome["r"] = ("leaked", error)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(_BUDGET_SECONDS)
    if worker.is_alive():
        return ("hung", None)
    return outcome["r"]


# Both inputs are rejected by every server version in the support matrix. A
# non-string mapping key is deliberately NOT used here: SurrealDB 2.x coerces
# `{1: "a"}` to `{"1": "a"}` and returns it successfully, so it only triggers a
# protocol error on 3.x.
@pytest.mark.parametrize(
    ("label", "make_call"),
    [
        (
            "integer too large to encode",
            lambda db: db.query("RETURN $v", {"v": 2**200}).first(),
        ),
        ("record id with a null table", lambda db: db.select(RecordID(None, 1))),
    ],
)
def test_protocol_error_raises_instead_of_hanging(
    blocking_ws_connection: BlockingWsSurrealConnection,
    label: str,
    make_call: Any,
) -> None:
    kind, value = _within_budget(lambda: make_call(blocking_ws_connection))

    assert kind != "hung", f"{label}: blocked for over {_BUDGET_SECONDS}s"
    assert kind == "surreal-error", (
        f"{label}: expected a SurrealError, got {kind} {value!r}"
    )


def test_connection_still_usable_after_a_protocol_error(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> None:
    """The socket survives the error frame, so the connection is not poisoned."""
    with pytest.raises(SurrealError):
        blocking_ws_connection.query("RETURN $v", {"v": 2**200}).first()

    assert blocking_ws_connection.query("RETURN 1").first() == 1


def test_connection_recovers_after_an_rpc_timeout(
    blocking_ws_connection: BlockingWsSurrealConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed-out request does not desynchronise every later one.

    The RPC deadline that stopped protocol errors hanging forever introduced
    its own failure: the request had already been sent, so the server's late
    reply stayed in the socket, and the next call read *that* instead of its
    own - mismatching ids from then on, permanently one behind.
    """
    monkeypatch.setattr(blocking_ws, "_RPC_RECV_TIMEOUT", 2.0)

    with pytest.raises(TransportTimeoutError):
        blocking_ws_connection.query("RETURN sleep(5s)").first()

    # Let the abandoned reply land in the socket buffer before continuing.
    time.sleep(4)

    assert blocking_ws_connection.query("RETURN 1").first() == 1
    assert blocking_ws_connection.query("RETURN 2").first() == 2
