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
from surrealdb.errors import HttpStatusError
from surrealdb.types import Tokens, Value
from tests.unit_tests.fake_surreal import (
    Call,
    FakeSurreal,
    FakeSurrealHttp,
    RpcFailure,
    jwt,
    token_expired,
)

ROOT: dict[str, Value] = {"username": "root", "password": "root"}


def _due(subject: str = "root") -> str:
    """An access token that is still good but due for renewal."""
    return jwt(subject, lifetime=30, iat=time.time() - 3600)


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


def test_blocking_http_a_due_token_is_not_renewed_before_every_request(
    http: FakeSurrealHttp,
) -> None:
    http.respond("signin", lambda call: _due())
    db = BlockingHttpSurrealConnection(http.url, auth=ROOT)
    for n in range(5):
        db.query(f"RETURN {n}").execute()
    # The sign-in, then one renewal that produced nothing newer.
    assert http.methods().count("signin") == 2


async def test_async_http_a_due_token_is_not_renewed_before_every_request(
    http: FakeSurrealHttp,
) -> None:
    http.respond("signin", lambda call: _due())
    db = AsyncHttpSurrealConnection(http.url, auth=ROOT)
    for n in range(5):
        await db.query(f"RETURN {n}")
    # The sign-in, then one renewal that produced nothing newer.
    assert http.methods().count("signin") == 2


def test_blocking_http_a_static_due_token_is_not_authenticated_again(
    http: FakeSurrealHttp,
) -> None:
    db = BlockingHttpSurrealConnection(http.url, auth=_due())
    for n in range(5):
        db.query(f"RETURN {n}").execute()
    assert http.methods().count("authenticate") == 1


def test_blocking_ws_a_due_token_is_not_renewed_before_every_request(
    ws: FakeSurreal,
) -> None:
    ws.respond("signin", lambda call: _due())
    db = BlockingWsSurrealConnection(ws.url, auth=ROOT)
    try:
        db.connect()
        for n in range(5):
            db.query(f"RETURN {n}").execute()
        # The sign-in, then one renewal that produced nothing newer.
        assert ws.methods().count("signin") == 2
    finally:
        db.close()


def test_blocking_ws_a_failed_renewal_waits_before_it_is_tried_again(
    ws: FakeSurreal,
) -> None:
    asked = 0

    def credentials() -> dict[str, Value]:
        nonlocal asked
        asked += 1
        if asked > 1:
            raise RuntimeError("the credential store is down")
        return dict(ROOT)

    ws.respond("signin", lambda call: _due())
    db = BlockingWsSurrealConnection(ws.url, auth=credentials)
    errors: list[BaseException] = []
    db.subscribe("error", errors.append)
    try:
        db.connect()
        for n in range(5):
            db.query(f"RETURN {n}").execute()
        assert asked == 2
        assert sum(isinstance(error, RuntimeError) for error in errors) == 1
    finally:
        db.close()


class _SavedTokens:
    """`auth=Tokens(...)` saved past its access token's expiry."""

    def __init__(self, server: FakeSurreal | FakeSurrealHttp) -> None:
        expired = jwt("root", lifetime=-60)
        self.given = Tokens(access=expired, refresh="refresh-0")
        self.renewed = {"access": jwt("root"), "refresh": "refresh-1"}

        def authenticate(call: Call) -> None:
            if call.params[0] == expired:
                raise token_expired()

        server.respond("authenticate", authenticate)
        server.respond("refresh", lambda call: self.renewed)


def test_blocking_http_renews_auth_tokens_whose_access_token_expired(
    http: FakeSurrealHttp,
) -> None:
    saved = _SavedTokens(http)
    db = BlockingHttpSurrealConnection(http.url, auth=saved.given)
    db.query("RETURN 1").execute()
    db.query("RETURN 2").execute()
    assert http.methods().count("refresh") == 1
    assert http.calls_to("query")[-1].token == saved.renewed["access"]


async def test_async_http_renews_auth_tokens_whose_access_token_expired(
    http: FakeSurrealHttp,
) -> None:
    saved = _SavedTokens(http)
    db = AsyncHttpSurrealConnection(http.url, auth=saved.given)
    await db.query("RETURN 1")
    await db.query("RETURN 2")
    assert http.methods().count("refresh") == 1
    assert http.calls_to("query")[-1].token == saved.renewed["access"]


def _refuse_with_401(http: FakeSurrealHttp, token: str | None) -> None:
    """Answer any request bearing *token* as a real server does over HTTP: 401, unread."""
    http.proxy = lambda call: 401 if call.token == token else None


def test_blocking_http_renews_auth_tokens_the_server_refuses_with_a_401(
    http: FakeSurrealHttp,
) -> None:
    saved = _SavedTokens(http)
    _refuse_with_401(http, saved.given.access)
    db = BlockingHttpSurrealConnection(http.url, auth=saved.given)
    db.query("RETURN 1").execute()
    assert http.methods().count("refresh") == 1
    assert http.calls_to("query")[-1].token == saved.renewed["access"]


async def test_async_http_renews_auth_tokens_the_server_refuses_with_a_401(
    http: FakeSurrealHttp,
) -> None:
    saved = _SavedTokens(http)
    _refuse_with_401(http, saved.given.access)
    db = AsyncHttpSurrealConnection(http.url, auth=saved.given)
    await db.query("RETURN 1")
    assert http.methods().count("refresh") == 1
    assert http.calls_to("query")[-1].token == saved.renewed["access"]


def test_http_does_not_refresh_auth_tokens_on_a_status_other_than_401(
    http: FakeSurrealHttp,
) -> None:
    saved = _SavedTokens(http)
    http.proxy = lambda call: 503 if call.method == "authenticate" else None
    db = BlockingHttpSurrealConnection(http.url, auth=saved.given)
    with pytest.raises(HttpStatusError, match="503"):
        db.query("RETURN 1").execute()
    assert "refresh" not in http.methods()


async def test_async_ws_renews_auth_tokens_whose_access_token_expired(
    ws: FakeSurreal,
) -> None:
    saved = _SavedTokens(ws)
    db = AsyncWsSurrealConnection(ws.url, auth=saved.given)
    try:
        await db.connect()
        assert db.token == saved.renewed["access"]
    finally:
        await db.close()


def test_blocking_ws_renews_auth_tokens_whose_access_token_expired(
    ws: FakeSurreal,
) -> None:
    saved = _SavedTokens(ws)
    db = BlockingWsSurrealConnection(ws.url, auth=saved.given)
    try:
        db.connect()
        assert db.token == saved.renewed["access"]
    finally:
        db.close()


OWNER: dict[str, Value] = {"username": "owner", "password": "owner"}
VIEWER: dict[str, Value] = {"username": "viewer", "password": "viewer"}


def _owner_or_due_viewer(call: Call) -> str:
    """The owner's token is good for an hour; the viewer's is due already."""
    user = call.params[0]["user"]
    return _due(user) if user == "viewer" else jwt(user)


def test_blocking_http_renewal_keeps_an_explicit_signin(http: FakeSurrealHttp) -> None:
    http.respond("signin", _owner_or_due_viewer)
    db = BlockingHttpSurrealConnection(http.url, auth=OWNER)
    viewer = db.signin(VIEWER)

    db.query("RETURN 1").execute()

    assert http.methods().count("signin") == 2
    assert http.calls_to("query")[-1].token == viewer.access


async def test_async_http_renewal_keeps_an_explicit_signin(
    http: FakeSurrealHttp,
) -> None:
    http.respond("signin", _owner_or_due_viewer)
    db = AsyncHttpSurrealConnection(http.url, auth=OWNER)
    viewer = await db.signin(VIEWER)

    await db.query("RETURN 1")

    assert http.methods().count("signin") == 2
    assert http.calls_to("query")[-1].token == viewer.access


async def test_async_ws_renewal_keeps_an_explicit_signin(ws: FakeSurreal) -> None:
    ws.respond("signin", _owner_or_due_viewer)
    db = AsyncWsSurrealConnection(ws.url, auth=OWNER)
    try:
        await db.connect()
        viewer = await db.signin(VIEWER)
        await asyncio.sleep(0.2)

        assert ws.methods().count("signin") == 2
        assert db.token == viewer.access
    finally:
        await db.close()


def test_blocking_ws_renewal_keeps_an_explicit_signin(ws: FakeSurreal) -> None:
    ws.respond("signin", _owner_or_due_viewer)
    db = BlockingWsSurrealConnection(ws.url, auth=OWNER)
    try:
        db.connect()
        viewer = db.signin(VIEWER)
        db.query("RETURN 1").execute()

        assert ws.methods().count("signin") == 2
        assert db.token == viewer.access
    finally:
        db.close()


def test_blocking_http_auth_applies_again_after_re_pointing(
    http: FakeSurrealHttp,
) -> None:
    http.respond("signin", _owner_or_due_viewer)
    db = BlockingHttpSurrealConnection(http.url, auth=OWNER)
    db.signin(VIEWER)
    db.connect(http.url)

    db.query("RETURN 1").execute()

    signed_in = [call.params[0]["user"] for call in http.calls_to("signin")]
    assert signed_in == ["owner", "viewer", "owner"]
