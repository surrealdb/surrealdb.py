"""`timeout()` overrides belong to the connection that set them, and to no other."""

import contextvars

from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.timeouts import (
    _OVERRIDES,
    _key,
    effective_timeout,
    scoped_timeout,
)


def _connection() -> BlockingHttpSurrealConnection:
    return BlockingHttpSurrealConnection("http://localhost:8000", timeout=30)


def test_an_override_applies_only_to_its_own_connection() -> None:
    first, second = _connection(), _connection()
    with scoped_timeout(first, 1.0):
        assert effective_timeout(first, 30) == 1.0
        assert effective_timeout(second, 30) == 30
    assert effective_timeout(first, 30) == 30


def test_an_override_is_not_keyed_by_a_reusable_id() -> None:
    """A task started inside the block keeps its overrides after the block ends.

    Keyed by ``id()``, a connection created later at the same address (which
    CPython reuses readily) inherited the dead connection's override. The key
    is a token no other object is ever given instead.
    """
    owner, other = _connection(), _connection()
    with scoped_timeout(owner, 1.0):
        kept = contextvars.copy_context()
    overrides = kept[_OVERRIDES]
    assert list(overrides.values()) == [1.0]
    assert id(owner) not in overrides
    assert _key(owner) in overrides and _key(other) not in overrides
    assert _key(owner) == _key(owner) != _key(other)
