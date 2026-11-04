"""A forked session and its source each keep their own refresh token.

A refresh token is spent the first time the server takes it. The fork used to
be given the source's, so renewing either spent it for both: refreshing the
fork made the source's next refresh fail, though the two are documented as
independent once forked.
"""

from collections.abc import Iterator

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.types import Value
from tests.unit_tests.fake_surreal import Call, FakeSurreal, jwt

ROOT: dict[str, Value] = {"username": "root", "password": "root"}


@pytest.fixture
def fake() -> Iterator[FakeSurreal]:
    server = FakeSurreal()
    try:
        yield server
    finally:
        server.close()


def _signin(call: Call) -> dict[str, str]:
    return {"access": jwt("root"), "refresh": "refresh-source"}


def _spent(fake: FakeSurreal) -> list[str]:
    return [call.params[0]["refresh"] for call in fake.calls_to("refresh")]


async def test_async_a_fork_does_not_spend_the_sources_refresh_token(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin)
    db = AsyncWsSurrealConnection(fake.url, reconnect=False)
    try:
        await db.signin(ROOT)
        fork = await db.fork_session()
        with pytest.raises(ValueError, match="needs a refresh token"):
            await fork.refresh()
        assert db._registry.state(fork._session_id).access == db.token
        await db.refresh()
        assert _spent(fake) == ["refresh-source"]
    finally:
        await db.close()


def test_blocking_a_fork_does_not_spend_the_sources_refresh_token(
    fake: FakeSurreal,
) -> None:
    fake.respond("signin", _signin)
    db = BlockingWsSurrealConnection(fake.url, reconnect=False)
    try:
        db.signin(ROOT)
        fork = db.fork_session()
        with pytest.raises(ValueError, match="needs a refresh token"):
            fork.refresh()
        assert db._registry.state(fork._session_id).access == db.token
        db.refresh()
        assert _spent(fake) == ["refresh-source"]
    finally:
        db.close()
