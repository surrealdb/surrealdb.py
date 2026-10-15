"""How long a request waits for its reply.

Every remote connection has a default, set with ``timeout=`` when it is built,
and any block of requests can override it with ``with db.timeout(seconds):``.
The override lives in a context variable, so it follows the code that set it -
across ``await`` and into tasks started inside the block - and never leaks into
a concurrent task or thread using the same connection.
"""

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
    if value != value or value <= 0:
        raise ValueError(
            f"{name} must be a positive number of seconds, or None to wait "
            f"indefinitely; got {value!r}"
        )
    return float(value)


def effective_timeout(owner: object, default: float | None) -> float | None:
    """The timeout for a request on *owner* made from the current context."""
    overrides = _OVERRIDES.get()
    key = id(owner)
    if key in overrides:
        return overrides[key]
    return default


@contextmanager
def scoped_timeout(owner: object, seconds: float | None) -> Generator[None, None, None]:
    """Apply *seconds* to every request *owner* makes inside the block."""
    value = check_timeout("timeout", seconds)
    current = _OVERRIDES.get()
    token = _OVERRIDES.set(MappingProxyType({**current, id(owner): value}))
    try:
        yield
    finally:
        _OVERRIDES.reset(token)


def describe(seconds: float | None) -> str:
    """Render a timeout for an error message."""
    if seconds is None:
        return "with no timeout"
    return f"within {seconds:g}s"
