"""Signing a connection in by itself, and keeping its access token fresh.

``auth=`` on a connection, or on ``Surreal``/``AsyncSurreal``, says how the
connection authenticates, as the JS SDK's ``authentication`` option does. It is
one of:

- a dict of credentials, as passed to ``signin()``;
- an access token, as passed to ``authenticate()``;
- :class:`~surrealdb.types.Tokens`, whose access token is used and whose
  refresh token is kept for renewing it;
- a function taking no arguments that returns any of those - or, on an async
  connection, a coroutine function - called each time they are needed, so it
  can fetch a fresh token from wherever tokens come from.

The connection applies it when the socket opens and again after every
reconnect, in place of replaying a token that may have expired while the
socket was down.

With ``renew_access`` on (the default), a connection also renews its own
access token shortly before it expires: with the refresh token if it holds
one and the server supports them, otherwise by applying ``auth=`` again. The
async connection does this on a timer; the blocking and HTTP connections have
no background work, so they do it before the next request that needs it.
"""

import base64
import binascii
import json
import time
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from surrealdb.types import Tokens, Value

AuthCredentials: TypeAlias = dict[str, Value] | str | Tokens
AuthProvider: TypeAlias = (
    AuthCredentials | Callable[[], AuthCredentials | Awaitable[AuthCredentials]]
)

# Renew this long before the access token expires, or a tenth of its lifetime
# if that is shorter, so a short-lived token is not renewed straight away.
RENEW_BEFORE = 60.0

# After a failed renewal, try again after this long, doubling each time up to
# RENEW_RETRY_MAX, while the token may still be renewed.
RENEW_RETRY = 5.0
RENEW_RETRY_MAX = 300.0


def check_auth_provider(provider: object) -> None:
    """Refuse an ``auth=`` the connection would not know how to apply."""
    if provider is None or callable(provider):
        return
    if not isinstance(provider, (dict, str, Tokens)):
        raise TypeError(
            "auth must be signin credentials (a dict), an access token (a "
            "str), Tokens, or a function returning one of those; got "
            f"{type(provider).__name__}"
        )


def check_credentials(provided: object) -> AuthCredentials:
    """What an ``auth=`` function returned, checked before it is used."""
    if isinstance(provided, (dict, str, Tokens)):
        return provided
    raise TypeError(
        "the auth function must return signin credentials (a dict), an "
        f"access token (a str) or Tokens; it returned {type(provided).__name__}"
    )


def _claims(token: str) -> dict[str, object] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, ValueError):
        return None
    return claims if isinstance(claims, dict) else None


def renew_at(token: str | None) -> float | None:
    """When to renew *token*, as a Unix time, or ``None`` if it never expires.

    Read from the token's own ``exp`` and ``iat`` claims without verifying
    its signature: the server does that, and only the timing is needed here.
    """
    if token is None:
        return None
    claims = _claims(token)
    if claims is None:
        return None
    expires = claims.get("exp")
    if not isinstance(expires, (int, float)) or isinstance(expires, bool):
        return None
    issued = claims.get("iat")
    lifetime = (
        expires - issued
        if isinstance(issued, (int, float)) and not isinstance(issued, bool)
        else RENEW_BEFORE * 10
    )
    return float(expires) - min(RENEW_BEFORE, max(lifetime / 10, 0.0))


def renewal_due(token: str | None) -> bool:
    """Whether *token* should be renewed now."""
    when = renew_at(token)
    return when is not None and time.time() >= when
