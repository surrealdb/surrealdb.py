"""``live()`` over HTTP is refused, and says why.

This was an ``xfail`` asserting the *old* behaviour - that `live()` on an HTTP
connection returned a ``UUID``, marked "live method not implemented for HTTP
connections". It has been refused with ``UnsupportedFeatureError`` since live
queries were made consistent across the transports, so the marker described a
version of the SDK that no longer exists.

Worse, an ``xfail`` only records *that* something failed. This one would have
stayed green if ``live()`` had started raising ``AttributeError`` from a typo,
because that is a failure too. The refusal is a documented part of the API, so
it is asserted directly.
"""

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.errors import SurrealError, UnsupportedFeatureError


async def test_live_is_refused_with_the_reason(
    async_http_connection_with_user: AsyncHttpSurrealConnection,
) -> None:
    with pytest.raises(UnsupportedFeatureError, match="WebSocket") as caught:
        await async_http_connection_with_user.live("user")

    # Catchable through the tree the README tells people to use.
    assert isinstance(caught.value, SurrealError)


async def test_the_connection_still_works_afterwards(
    async_http_connection_with_user: AsyncHttpSurrealConnection,
) -> None:
    """The refusal is local, so it costs the connection nothing."""
    with pytest.raises(UnsupportedFeatureError):
        await async_http_connection_with_user.live("user")

    assert await async_http_connection_with_user.query("RETURN 1").first() == 1
