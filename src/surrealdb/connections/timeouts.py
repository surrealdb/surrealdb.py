"""How long a request waits for its reply.

Every remote connection has a default, set with ``timeout=`` when it is built,
and any block of requests can override it with ``with db.timeout(seconds):``.
The override lives in a context variable, so it follows the code that set it -
across ``await`` and into tasks started inside the block - and never leaks into
a concurrent task or thread using the same connection.
"""

import itertools
import math
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType
from typing import Any

DEFAULT_TIMEOUT = 30.0

_EMPTY: "MappingProxyType[int, float | None]" = MappingProxyType({})

_OVERRIDES: "ContextVar[MappingProxyType[int, float | None]]" = ContextVar(
    "surrealdb_request_timeouts", default=_EMPTY
)


def check_timeout(name: str, value: Any) -> float | None:
    """Validate a timeout in seconds; ``None`` means wait indefinitely."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"{name} must be a number of seconds or None, not "
            f"{type(value).__name__}: {value!r}"
        )
    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            f"{name} must be a positive, finite number of seconds, or None to "
            f"wait indefinitely; got {value!r}"
        )
    return float(value)


_KEYS = itertools.count()


def _key(owner: object) -> int:
    """A key for *owner* that no other object will ever have.

    Not ``id(owner)``: a task started inside a ``timeout()`` block keeps the
    overrides after the block ends, and an id can be reused by a connection
    created later, which would then inherit an override that was never its.
    """
    key: int | None = getattr(owner, "_timeout_key", None)
    if key is None:
        key = next(_KEYS)
        vars(owner)["_timeout_key"] = key
    return key


def effective_timeout(owner: object, default: float | None) -> float | None:
    """The timeout for a request on *owner* made from the current context."""
    overrides = _OVERRIDES.get()
    key = _key(owner)
    if key in overrides:
        return overrides[key]
    return default


@contextmanager
def scoped_timeout(owner: object, seconds: float | None) -> Generator[None, None, None]:
    """Apply *seconds* to every request *owner* makes inside the block."""
    value = check_timeout("timeout", seconds)
    current = _OVERRIDES.get()
    token = _OVERRIDES.set(MappingProxyType({**current, _key(owner): value}))
    try:
        yield
    finally:
        _OVERRIDES.reset(token)


def describe(seconds: float | None) -> str:
    """Render a timeout for an error message."""
    if seconds is None:
        return "with no timeout"
    return f"within {seconds:g}s"
