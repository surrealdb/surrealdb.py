"""The async and blocking APIs behave the same way for the same call.

Divergences here are the worst kind of bug to receive as a report: the code
"works" on one transport and silently does nothing on the other, so the symptom
surfaces far from the cause.
"""

import inspect

import pytest

from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import (
    AsyncSurrealSession,
    AsyncWsSurrealConnection,
)
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import (
    BlockingSurrealSession,
    BlockingWsSurrealConnection,
)
from surrealdb.connections.builders import _UNSET

_DATA_METHODS = ("create", "update", "upsert", "insert")
_CONNECTIONS = (
    AsyncWsSurrealConnection,
    AsyncHttpSurrealConnection,
    BlockingWsSurrealConnection,
    BlockingHttpSurrealConnection,
)


@pytest.mark.parametrize("connection", _CONNECTIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("method", _DATA_METHODS)
def test_data_argument_distinguishes_omitted_from_none(
    connection: type, method: str
) -> None:
    """``data`` defaults to the sentinel, not ``None``, on every transport.

    With ``None`` as the default, an explicit ``data=None`` is indistinguishable
    from omitting it. The async transports therefore returned an unconfigured
    builder and silently ignored the argument, while the blocking ones ran
    ``CONTENT NULL`` and raised - the same call, opposite behaviour.

    ``None`` remains a legal *value* (it means ``CONTENT NULL``); it is only
    disqualified as the marker for "not supplied".
    """
    signature = inspect.signature(getattr(connection, method))
    data = signature.parameters["data"]

    assert data.default is _UNSET, (
        f"{connection.__name__}.{method} uses {data.default!r} as the data "
        "default, so an explicit None cannot be told from an omitted argument"
    )


@pytest.mark.parametrize(
    "session", (AsyncSurrealSession, BlockingSurrealSession), ids=lambda c: c.__name__
)
def test_sessions_can_consume_the_live_queries_they_start(session: type) -> None:
    """A session exposing ``live``/``kill`` must expose ``subscribe_live`` too.

    Without it a session could start a live query and had no way to read from
    it, forcing callers to reach past the wrapper to the connection.
    """
    for method in ("live", "kill", "subscribe_live"):
        assert hasattr(session, method), f"{session.__name__} is missing {method}()"


@pytest.mark.parametrize("connection", _CONNECTIONS, ids=lambda c: c.__name__)
def test_no_connection_exposes_set_token(connection: type) -> None:
    """``set_token`` is gone rather than propagated to the other transports.

    It existed only on the two HTTP connections, was undocumented and
    unreferenced, and assigned ``self.token`` without the ``AUTHENTICATE`` call
    that validates it - so a caller could believe they were authenticated when
    the server had never seen the token. ``token`` is a public attribute, so
    nothing that assignment could do was lost.
    """
    assert not hasattr(connection, "set_token")
