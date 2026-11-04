"""When an access token is due for renewal, read from its own claims."""

import base64
import json
import time

import pytest

from surrealdb.connections.auth_provider import (
    RENEW_BEFORE,
    check_auth_provider,
    renew_at,
    renewal_due,
)
from surrealdb.types import Tokens


def _jwt(claims: dict[str, object]) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"e30.{payload.decode()}.signature"


def test_a_long_token_is_renewed_a_minute_early() -> None:
    assert renew_at(_jwt({"iat": 0, "exp": 3600})) == 3600 - RENEW_BEFORE


def test_a_short_token_is_renewed_a_tenth_of_its_life_early() -> None:
    assert renew_at(_jwt({"iat": 100, "exp": 110})) == 109


@pytest.mark.parametrize(
    "token", [None, "not-a-jwt", "a.b.c", _jwt({"iat": 0}), _jwt({"exp": "soon"})]
)
def test_a_token_without_a_readable_expiry_is_never_due(token: str | None) -> None:
    assert renew_at(token) is None
    assert not renewal_due(token)


def test_due_once_the_renewal_time_has_passed() -> None:
    now = int(time.time())
    assert renewal_due(_jwt({"iat": now - 3600, "exp": now + 1}))
    assert not renewal_due(_jwt({"iat": now, "exp": now + 3600}))


@pytest.mark.parametrize(
    "provider", [None, {"username": "u"}, "token", Tokens(access="a"), lambda: "t"]
)
def test_accepted_providers(provider: object) -> None:
    check_auth_provider(provider)


def test_anything_else_is_refused() -> None:
    with pytest.raises(TypeError, match="auth must be"):
        check_auth_provider(42)
