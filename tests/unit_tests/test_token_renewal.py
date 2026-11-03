"""Renewing the access token, on every transport, against fake servers.

The renewal tests under ``tests/unit_tests/connections/reconnect`` need a
running SurrealDB, which will not refuse a refresh token on demand; these
script the refusals.
"""

import asyncio
import time
from collections.abc import Iterator

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.types import Value
from tests.unit_tests.fake_surreal import (
    Call,
    FakeSurreal,
    FakeSurrealHttp,
    RpcFailure,
    jwt,
)

ROOT: dict[str, Value] = {"username": "root", "password": "root"}


def _due() -> str:
    """An access token that is still good but due for renewal."""
    return jwt("root", lifetime=30, iat=time.time() - 3600)


def _refused(call: Call) -> None:
    raise RpcFailure("The refresh token has expired or was revoked")


class _Signins:
    """Answers `signin`: a due token with a refresh token first, then fresh ones."""

    def __init__(self) -> None:
        self.issued: list[str] = []

    def __call__(self, call: Call) -> dict[str, str]:
        access = _due() if not self.issued else jwt("root")
        self.issued.append(access)
        return {"access": access, "refresh": f"refresh-{len(self.issued)}"}


@pytest.fixture
def http() -> Iterator[FakeSurrealHttp]:
    server = FakeSurrealHttp()
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def ws() -> Iterator[FakeSurreal]:
    server = FakeSurreal()
    try:
        yield server
    finally:
        server.close()


def test_blocking_http_a_refused_refresh_token_is_tried_once(
    http: FakeSurrealHttp,
) -> None:
    http.respond("signin", _Signins())
    http.respond("refresh", _refused)
    db = BlockingHttpSurrealConnection(http.url)
    db.signin(ROOT)

    db.query("RETURN 1").execute()
    db.query("RETURN 2").execute()

    assert http.methods().count("refresh") == 1
    assert http.methods().count("query") == 2


def test_blocking_http_a_refused_refresh_falls_back_to_auth(
    http: FakeSurrealHttp,
) -> None:
    signins = _Signins()
    http.respond("signin", signins)
    http.respond("refresh", _refused)
    db = BlockingHttpSurrealConnection(http.url, auth=ROOT)

    db.query("RETURN 1").execute()
    db.query("RETURN 2").execute()

    assert http.methods().count("refresh") == 1
    assert len(signins.issued) == 2
    assert http.calls_to("query")[-1].token == signins.issued[-1]


async def test_async_http_a_refused_refresh_token_is_tried_once(
    http: FakeSurrealHttp,
) -> None:
    http.respond("signin", _Signins())
    http.respond("refresh", _refused)
    db = AsyncHttpSurrealConnection(http.url)
    await db.signin(ROOT)

    await db.query("RETURN 1")
    await db.query("RETURN 2")

    assert http.methods().count("refresh") == 1
    assert http.methods().count("query") == 2


async def test_async_http_a_refused_refresh_falls_back_to_auth(
    http: FakeSurrealHttp,
) -> None:
    signins = _Signins()
    http.respond("signin", signins)
    http.respond("refresh", _refused)
    db = AsyncHttpSurrealConnection(http.url, auth=ROOT)

    await db.query("RETURN 1")
    await db.query("RETURN 2")

    assert http.methods().count("refresh") == 1
    assert len(signins.issued) == 2
    assert http.calls_to("query")[-1].token == signins.issued[-1]


async def test_async_ws_a_refused_refresh_falls_back_to_auth(ws: FakeSurreal) -> None:
    signins = _Signins()
    ws.respond("signin", signins)
    ws.respond("refresh", _refused)
    db = AsyncWsSurrealConnection(ws.url, auth=ROOT)
    errors: list[BaseException] = []
    db.subscribe("error", errors.append)
    try:
        await db.connect()
        deadline = time.monotonic() + 5
        while len(signins.issued) < 2 and time.monotonic() < deadline:
            await asyncio.sleep(0.01)

        assert ws.methods().count("refresh") == 1
        assert db.token == signins.issued[-1]
        assert any("refresh token" in str(error) for error in errors)
    finally:
        await db.close()


def test_blocking_ws_a_refused_refresh_token_is_tried_once(ws: FakeSurreal) -> None:
    ws.respond("signin", _Signins())
    ws.respond("refresh", _refused)
    db = BlockingWsSurrealConnection(ws.url)
    try:
        db.signin(ROOT)
        db.query("RETURN 1").execute()
        db.query("RETURN 2").execute()
        assert ws.methods().count("refresh") == 1
        assert ws.methods().count("query") == 2
    finally:
        db.close()


def test_blocking_ws_a_refused_refresh_falls_back_to_auth(ws: FakeSurreal) -> None:
    signins = _Signins()
    ws.respond("signin", signins)
    ws.respond("refresh", _refused)
    db = BlockingWsSurrealConnection(ws.url, auth=ROOT)
    try:
        db.connect()
        db.query("RETURN 1").execute()
        assert ws.methods().count("refresh") == 1
        assert db.token == signins.issued[-1]
    finally:
        db.close()
