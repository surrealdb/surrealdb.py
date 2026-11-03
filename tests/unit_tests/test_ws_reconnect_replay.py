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
from surrealdb.errors import ConnectionUnavailableError
from surrealdb.types import Tokens, Value
from tests.unit_tests.fake_surreal import Call, FakeSurreal, jwt

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
