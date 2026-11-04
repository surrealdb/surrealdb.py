"""What the websocket connections replay after a reconnect, against a fake server.

The reconnect tests under ``tests/unit_tests/connections/reconnect`` need a
running SurrealDB; these run anywhere, so the failure paths a real server is
hard to steer into - a socket cut mid-session, a token expiring while it was
down, a session signed in as someone else - stay covered.
"""

import asyncio
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from websockets.protocol import State

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.reconnect import ReconnectOptions
from surrealdb.errors import ConnectionUnavailableError, TransportTimeoutError
from surrealdb.types import Tokens, Value
from tests.unit_tests.fake_surreal import Call, FakeSurreal, jwt, token_expired

FAST = ReconnectOptions(retry_delay=0.01, retry_delay_max=0.02, retry_delay_jitter=0)
ROOT: dict[str, Value] = {"username": "root", "password": "root"}


@pytest.fixture
def fake() -> Iterator[FakeSurreal]:
    server = FakeSurreal()
    try:
        yield server
    finally:
        server.close()


def _signin_as_user(call: Call) -> dict[str, str]:
    """Tokens for whoever signed in, with a refresh token to renew them by."""
    user = call.params[0]["user"]
    return {"access": jwt(user), "refresh": f"refresh-{uuid.uuid4().hex}"}


def _replay(fake: FakeSurreal, socket: int) -> list[tuple[str, Any]]:
    return [(c.method, c.params) for c in fake.calls if c.socket == socket]


async def _until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting for the condition")
        await asyncio.sleep(0.01)


async def _reconnected(db: AsyncWsSurrealConnection, fake: FakeSurreal) -> None:
    sockets = fake.sockets_opened
    fake.drop()
    await _until(lambda: fake.sockets_opened > sockets and db.status == "connected")


def _dropped(db: BlockingWsSurrealConnection, fake: FakeSurreal) -> None:
    """Cut the socket and wait until the client has seen it go."""
    fake.drop()
    fake.wait_for(lambda: db.socket is not None and db.socket.state is not State.OPEN)


async def test_async_a_live_query_restarts_in_its_own_namespace_and_database(
    fake: FakeSurreal,
) -> None:
    started, restarted = uuid.uuid4(), uuid.uuid4()
    ids = iter([started, restarted])
    fake.respond("live", lambda call: next(ids))
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        await db.use("ns1", "db1")
        subscription = await db.live("orders")
        await db.use("ns2", "db2")
        await _reconnected(db, fake)

        replay = _replay(fake, 1)
        live = [method for method, _ in replay].index("live")
        assert replay[live - 1] == ("use", ["ns1", "db1"])
        assert replay[live + 1] == ("use", ["ns2", "db2"])
        assert db.namespace == "ns2" and db.database == "db2"

        fake.notify(restarted, record={"id": 1})
        notification = await asyncio.wait_for(anext(aiter(subscription)), 5)
        assert notification["id"] == started
    finally:
        await db.close()


async def test_async_a_live_query_in_the_selected_database_restarts_directly(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        await db.use("ns1", "db1")
        await db.live("orders")
        await _reconnected(db, fake)
        assert [method for method, _ in _replay(fake, 1)] == ["version", "use", "live"]
    finally:
        await db.close()


async def test_async_a_live_query_is_not_restarted_as_someone_else(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin_as_user)
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST)
    errors: list[BaseException] = []
    db.subscribe("error", errors.append)
    try:
        await db.signin({"username": "alice", "password": "a"})
        subscription = await db.live("orders")
        waiting = asyncio.ensure_future(anext(aiter(subscription)))
        await db.signin({"username": "bob", "password": "b"})
        await _reconnected(db, fake)

        assert "live" not in fake.methods(1)
        assert any("no longer signed in" in str(error) for error in errors)
        assert not subscription.is_alive
        with pytest.raises(ConnectionUnavailableError):
            await asyncio.wait_for(waiting, 5)
    finally:
        await db.close()


async def test_async_a_renewed_token_keeps_a_live_query_restartable(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin_as_user)
    fake.respond(
        "refresh", lambda call: _signin_as_user(Call(0, "", [{"user": "alice"}], None))
    )
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        await db.signin({"username": "alice", "password": "a"})
        await db.live("orders")
        await db.refresh()
        await _reconnected(db, fake)
        assert "live" in fake.methods(1)
    finally:
        await db.close()


def test_blocking_a_live_query_restarts_in_its_own_namespace_and_database(
    fake: FakeSurreal,
) -> None:
    db = BlockingWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        db.use("ns1", "db1")
        db.live("orders")
        db.use("ns2", "db2")
        _dropped(db, fake)
        db.version()

        replay = _replay(fake, 1)
        live = [method for method, _ in replay].index("live")
        assert replay[live - 1] == ("use", ["ns1", "db1"])
        assert replay[live + 1] == ("use", ["ns2", "db2"])
        assert db.namespace == "ns2" and db.database == "db2"
    finally:
        db.close()


def test_blocking_a_live_query_is_not_restarted_as_someone_else(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin_as_user)
    db = BlockingWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        db.signin({"username": "alice", "password": "a"})
        subscription = db.live("orders")
        notifications = iter(subscription)
        db.signin({"username": "bob", "password": "b"})
        _dropped(db, fake)
        db.version()

        assert "live" not in fake.methods(1)
        assert not subscription.is_alive
        with pytest.raises(ConnectionUnavailableError):
            next(notifications)
    finally:
        db.close()


def test_blocking_live_query_survives_signing_in_again_as_the_same_user(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin_as_user)
    db = BlockingWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        db.signin({"username": "alice", "password": "a"})
        db.live("orders")
        db.signin({"username": "alice", "password": "a"})
        _dropped(db, fake)
        db.version()
        assert "live" in fake.methods(1)
    finally:
        db.close()


def _renewing(fake: FakeSurreal) -> dict[str, str]:
    """Answer `refresh` with one known pair of tokens, and return it."""
    renewed = {"access": jwt("root"), "refresh": "refresh-1"}
    fake.respond("refresh", lambda call: renewed)
    return renewed


async def test_async_a_reconnect_keeps_the_tokens_renewal_replaced(
    fake: FakeSurreal,
) -> None:
    renewed = _renewing(fake)
    given = Tokens(access=jwt("root"), refresh="refresh-0")
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST, auth=given)
    try:
        await db.connect()
        await db.refresh()
        await _reconnected(db, fake)

        assert [c.params for c in fake.calls_to("authenticate", socket=1)] == [
            [renewed["access"]]
        ]
        assert db.token == renewed["access"]
    finally:
        await db.close()


async def test_async_credentials_sign_in_afresh_after_a_reconnect(
    fake: FakeSurreal,
) -> None:
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST, auth=ROOT)
    try:
        await db.connect()
        await _reconnected(db, fake)
        assert "signin" in fake.methods(1)
        assert "authenticate" not in fake.methods(1)
    finally:
        await db.close()


def test_blocking_a_reconnect_keeps_the_tokens_renewal_replaced(
    fake: FakeSurreal,
) -> None:
    renewed = _renewing(fake)
    given = Tokens(access=jwt("root"), refresh="refresh-0")
    db = BlockingWsSurrealConnection(fake.url, reconnect=FAST, auth=given)
    try:
        db.connect()
        db.refresh()
        _dropped(db, fake)
        db.version()

        assert [c.params for c in fake.calls_to("authenticate", socket=1)] == [
            [renewed["access"]]
        ]
        assert db.token == renewed["access"]
    finally:
        db.close()


VIEWER: dict[str, Value] = {"username": "viewer", "password": "viewer"}


async def test_async_a_reconnect_keeps_an_explicit_signin_over_auth(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin_as_user)
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST, auth=ROOT)
    try:
        await db.connect()
        viewer = await db.signin(VIEWER)
        await _reconnected(db, fake)

        assert "signin" not in fake.methods(1)
        assert [c.params for c in fake.calls_to("authenticate", socket=1)] == [
            [viewer.access]
        ]
        assert db.token == viewer.access
    finally:
        await db.close()


def test_blocking_a_reconnect_keeps_an_explicit_signin_over_auth(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin_as_user)
    db = BlockingWsSurrealConnection(fake.url, reconnect=FAST, auth=ROOT)
    try:
        db.connect()
        viewer = db.signin(VIEWER)
        _dropped(db, fake)
        db.version()

        assert "signin" not in fake.methods(1)
        assert [c.params for c in fake.calls_to("authenticate", socket=1)] == [
            [viewer.access]
        ]
        assert db.token == viewer.access
    finally:
        db.close()


async def test_async_auth_signs_in_again_once_the_connection_is_closed(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin_as_user)
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST, auth=ROOT)
    try:
        await db.connect()
        await db.signin(VIEWER)
        await db.close()
        await db.connect()

        assert [c.params[0]["user"] for c in fake.calls_to("signin", socket=1)] == [
            "root"
        ]
    finally:
        await db.close()


def test_blocking_giving_up_ends_a_live_iterator_already_running(
    fake: FakeSurreal,
) -> None:
    options = ReconnectOptions(
        attempts=2, retry_delay=0.01, retry_delay_max=0.02, retry_delay_jitter=0
    )
    db = BlockingWsSurrealConnection(fake.url, reconnect=options)
    outcome: list[BaseException | dict[str, Value]] = []
    try:
        notifications = iter(db.live("orders"))
        fake.accepting = False
        _dropped(db, fake)
        with pytest.raises(ConnectionUnavailableError):
            db.version()
        fake.accepting = True
        db.version()

        def consume() -> None:
            try:
                outcome.append(next(notifications))
            except BaseException as exc:
                outcome.append(exc)

        consumer = threading.Thread(target=consume, daemon=True)
        consumer.start()
        consumer.join(5)
        assert not consumer.is_alive(), "the live iterator is still waiting"
        assert isinstance(outcome[0], ConnectionUnavailableError)
    finally:
        db.close()


def test_blocking_the_first_reconnect_attempt_is_immediate(fake: FakeSurreal) -> None:
    db = BlockingWsSurrealConnection(fake.url)
    try:
        db.use("ns", "db")
        _dropped(db, fake)
        started = time.monotonic()
        db.version()
        assert time.monotonic() - started < 1.0
        assert "use" in fake.methods(1)
    finally:
        db.close()


def test_blocking_a_reconnect_keeps_to_the_request_timeout(fake: FakeSurreal) -> None:
    options = ReconnectOptions(attempts=3, retry_delay=0.5, retry_delay_jitter=0)
    db = BlockingWsSurrealConnection(fake.url, timeout=0.5, reconnect=options)
    try:
        db.version()
        fake.accepting = False
        _dropped(db, fake)
        started = time.monotonic()
        with pytest.raises(TransportTimeoutError):
            db.version()
        assert time.monotonic() - started < 1.5
    finally:
        db.close()


def test_blocking_threads_waiting_on_a_reconnect_keep_to_their_own_timeout(
    fake: FakeSurreal,
) -> None:
    options = ReconnectOptions(retry_delay=0.2, retry_delay_jitter=0)
    db = BlockingWsSurrealConnection(fake.url, reconnect=options)
    outcomes: dict[str, Any] = {}

    def request(name: str, seconds: float) -> None:
        started = time.monotonic()
        try:
            with db.timeout(seconds):
                outcomes[name] = db.version()
        except BaseException as exc:
            outcomes[name] = exc
        outcomes[f"{name} took"] = time.monotonic() - started

    try:
        db.version()
        fake.accepting = False
        _dropped(db, fake)
        patient = threading.Thread(target=request, args=("patient", 10.0))
        patient.start()
        fake.wait_for(lambda: db.status == "reconnecting")
        hasty = threading.Thread(target=request, args=("hasty", 0.3))
        hasty.start()
        hasty.join(5)
        assert isinstance(outcomes["hasty"], TransportTimeoutError)
        assert outcomes["hasty took"] < 1.5

        fake.accepting = True
        patient.join(10)
        assert outcomes["patient"] == fake.version
    finally:
        db.close()


def test_blocking_a_reconnect_carries_on_after_its_caller_timed_out(
    fake: FakeSurreal,
) -> None:
    options = ReconnectOptions(retry_delay=0.1, retry_delay_jitter=0)
    db = BlockingWsSurrealConnection(fake.url, timeout=0.2, reconnect=options)
    try:
        db.use("ns", "db")
        fake.accepting = False
        _dropped(db, fake)
        with pytest.raises(TransportTimeoutError):
            db.version()
        fake.accepting = True
        fake.wait_for(lambda: db.status == "connected")
        assert ("use", ["ns", "db"]) in _replay(fake, fake.sockets_opened - 1)
        assert db.version() == fake.version
    finally:
        db.close()


def _expire_every_token(fake: FakeSurreal) -> dict[str, str]:
    """From now on refuse every access token as expired; renew with fresh ones."""

    def expired(call: Call) -> None:
        raise token_expired()

    renewed = {"access": jwt("root"), "refresh": "refresh-1"}
    fake.respond("authenticate", expired)
    fake.respond("refresh", lambda call: renewed)
    return renewed


async def test_async_a_replay_renews_an_access_token_that_expired_meanwhile(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", lambda call: {"access": jwt("root"), "refresh": "r-0"})
    db = AsyncWsSurrealConnection(fake.url, reconnect=FAST)
    errors: list[BaseException] = []
    db.subscribe("error", errors.append)
    try:
        await db.signin(ROOT)
        renewed = _expire_every_token(fake)
        await _reconnected(db, fake)
        assert fake.methods(1)[-2:] == ["authenticate", "refresh"]
        assert db.token == renewed["access"]
        assert not errors
    finally:
        await db.close()


def test_blocking_a_replay_renews_an_access_token_that_expired_meanwhile(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", lambda call: {"access": jwt("root"), "refresh": "r-0"})
    db = BlockingWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        db.signin(ROOT)
        renewed = _expire_every_token(fake)
        _dropped(db, fake)
        db.version()
        assert fake.methods(1)[-3:] == ["authenticate", "refresh", "version"]
        assert db.token == renewed["access"]
    finally:
        db.close()


async def test_async_kill_during_a_reconnect_kills_the_restarted_query(
    fake: FakeSurreal,
) -> None:
    started, restarted = uuid.uuid4(), uuid.uuid4()
    ids = iter([started, restarted])
    fake.respond("live", lambda call: next(ids))
    slow = ReconnectOptions(retry_delay=0.2, retry_delay_jitter=0)
    db = AsyncWsSurrealConnection(fake.url, reconnect=slow)
    try:
        subscription = await db.live("orders")
        fake.drop()
        await _until(lambda: db.status == "reconnecting")
        await db.kill(subscription)
        assert [call.params for call in fake.calls_to("kill")] == [[restarted]]
    finally:
        await db.close()


def test_blocking_kill_after_a_drop_kills_the_restarted_query(
    fake: FakeSurreal,
) -> None:
    started, restarted = uuid.uuid4(), uuid.uuid4()
    ids = iter([started, restarted])
    fake.respond("live", lambda call: next(ids))
    db = BlockingWsSurrealConnection(fake.url, reconnect=FAST)
    try:
        subscription = db.live("orders")
        _dropped(db, fake)
        db.kill(subscription)
        assert [call.params for call in fake.calls_to("kill")] == [[restarted]]
    finally:
        db.close()


async def test_async_close_during_a_reconnect_fails_waiting_requests_cleanly(
    fake: FakeSurreal,
) -> None:
    slow = ReconnectOptions(retry_delay=0.2, retry_delay_jitter=0)
    db = AsyncWsSurrealConnection(fake.url, reconnect=slow)
    await db.version()
    fake.accepting = False
    fake.drop()
    await _until(lambda: db.status == "reconnecting")
    waiting = asyncio.ensure_future(db.version())
    await asyncio.sleep(0.05)
    await db.close()
    with pytest.raises(ConnectionUnavailableError, match="closed while"):
        await asyncio.wait_for(waiting, 5)


def test_blocking_close_during_a_reconnect_stops_it(fake: FakeSurreal) -> None:
    slow = ReconnectOptions(retry_delay=0.2, retry_delay_jitter=0)
    db = BlockingWsSurrealConnection(fake.url, reconnect=slow)
    outcome: list[BaseException | str] = []

    def request() -> None:
        try:
            outcome.append(db.version())
        except BaseException as exc:
            outcome.append(exc)

    db.version()
    fake.accepting = False
    _dropped(db, fake)
    waiter = threading.Thread(target=request)
    waiter.start()
    fake.wait_for(lambda: db.status == "reconnecting")
    db.close()
    waiter.join(5)
    assert isinstance(outcome[0], ConnectionUnavailableError)
    assert "closed while" in str(outcome[0])

    sockets = fake.sockets_opened
    fake.accepting = True
    time.sleep(1.0)
    assert fake.sockets_opened == sockets
    assert db.socket is None
    assert db.status == "disconnected"
