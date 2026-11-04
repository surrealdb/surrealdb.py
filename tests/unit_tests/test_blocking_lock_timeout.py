"""A blocking websocket request's timeout covers its wait for the connection.

One thread's request holds the connection lock until its reply arrives, so a
request from another thread waits for it before it is even sent. The timeout
used to start only once the request had the lock: inside ``timeout(0.3)`` a
request queued behind a 1.5 s statement came back after 1.4 s.
"""

import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import TransportTimeoutError
from tests.unit_tests.fake_surreal import Call, FakeSurreal


@pytest.fixture
def fake() -> Iterator[FakeSurreal]:
    server = FakeSurreal()
    try:
        yield server
    finally:
        server.close()


def _hold(db: BlockingWsSurrealConnection, seconds: float) -> threading.Thread:
    """Hold the connection's lock on another thread, as a slow request does."""
    held = threading.Event()

    def holder() -> None:
        with db._lock:
            held.set()
            time.sleep(seconds)

    thread = threading.Thread(target=holder, daemon=True)
    thread.start()
    assert held.wait(5)
    return thread


def _slow_query(call: Call) -> list[Any]:
    time.sleep(0.4)
    return []


def test_a_request_waiting_behind_another_times_out_on_time(fake: FakeSurreal) -> None:
    db = BlockingWsSurrealConnection(fake.url, reconnect=False)
    try:
        db.connect()
        holder = _hold(db, 1.0)
        started = time.monotonic()
        with (
            pytest.raises(TransportTimeoutError, match="another request"),
            db.timeout(0.3),
        ):
            db.version()
        assert time.monotonic() - started < 0.6
        holder.join(5)
        assert db.version() == fake.version
    finally:
        db.close()


def test_the_wait_for_the_connection_counts_against_the_reply(
    fake: FakeSurreal,
) -> None:
    """A request that gets the lock late has only what is left to wait for its reply."""
    fake.respond("query", _slow_query)
    db = BlockingWsSurrealConnection(fake.url, reconnect=False)
    try:
        db.connect()
        holder = _hold(db, 0.3)
        started = time.monotonic()
        with pytest.raises(TransportTimeoutError, match="no reply"), db.timeout(0.5):
            db.query("RETURN 1").execute()
        assert time.monotonic() - started < 0.65
        holder.join(5)
    finally:
        db.close()
