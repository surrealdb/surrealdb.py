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

The connection applies it when the socket opens. After a reconnect it signs
in again with credentials, or asks the function again, in place of replaying a
token that may have expired while the socket was down; a token or ``Tokens``
given as they are is not applied again, since the tokens the connection holds
by then - renewed, perhaps - are at least as fresh.

With ``renew_access`` on (the default), a connection also renews its own
access token shortly before it expires: with the refresh token if it holds
one and the server supports them, otherwise by applying ``auth=`` again. The
async connection does this on a timer; the blocking and HTTP connections have
no background work, so they do it before the next request that needs it.

Signing the connection's own session in, up or out - ``signin()``,
``signup()``, ``authenticate()``, ``invalidate()`` or ``reset()`` - takes
over from ``auth=``, as an explicit sign-in does in the JS SDK: renewing then
uses only the refresh token the session holds, and a reconnect replays what
the caller chose. ``auth=`` applies again once the connection starts over:
re-pointed with ``connect(url)``, or, on a websocket, closed or dropped
without a reconnect.
"""

import base64
import binascii
import json
import time
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from surrealdb.request_message.methods import RequestMethod
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

SENT_WITHOUT_RENEWAL = frozenset(
    {RequestMethod.VERSION, RequestMethod.REFRESH, RequestMethod.REVOKE}
)

# The claims that say who a token signs in as. Renewing a token keeps them.
_IDENTITY_CLAIMS = ("NS", "DB", "AC", "ID")


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


def signs_in_afresh(provider: AuthProvider | None) -> bool:
    """Whether applying *provider* again gives a fresh sign-in.

    Credentials sign in anew, and a function is asked again. A token or
    :class:`Tokens` given as they are would only put back what the connection
    was first given, which renewing may since have replaced.
    """
    return callable(provider) or isinstance(provider, dict)


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


def token_identity(token: str | None) -> tuple[object, ...] | None:
    """Who *token* signs in as, or ``None`` for no token at all.

    Read from the token's ``NS``, ``DB``, ``AC`` and ``ID`` claims, which a
    renewed token keeps, so renewing does not count as signing in as someone
    else. Tokens whose claims cannot be read all count as the same identity.
    """
    if token is None:
        return None
    claims = _claims(token) or {}
    return tuple(claims.get(name) for name in _IDENTITY_CLAIMS)
