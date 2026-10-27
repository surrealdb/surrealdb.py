import threading
from typing import TypeVar
from uuid import UUID, uuid4

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.connections.reconnect import SessionRegistry
from surrealdb.errors import NotAllowedError

EXPIRED = NotAllowedError(
    "NotAllowed",
    "The token has expired",
    details={"kind": "Auth", "details": {"kind": "TokenExpired"}},
)
DENIED = NotAllowedError("NotAllowed", "Anonymous access not allowed")

C = TypeVar("C", AsyncWsSurrealConnection, BlockingWsSurrealConnection)


def _bare(cls: type[C]) -> C:
    """A connection with no socket, holding only the session state."""
    conn = object.__new__(cls)
    conn._registry = SessionRegistry()
    conn._init_events()
    if isinstance(conn, BlockingWsSurrealConnection):
        conn._lock = threading.Lock()
        conn._lock_owner = None
        conn._pending_events = []
        conn._session_lock = threading.RLock()
    return conn


@pytest.mark.asyncio
async def test_async_new_session_survives_expired_token() -> None:
    conn = _bare(AsyncWsSurrealConnection)
    conn.token = "expired"
    sid = uuid4()

    async def attach() -> UUID:
        return sid

    async def authenticate(token: str, session_id: UUID | None = None) -> None:
        raise EXPIRED

    conn.attach = attach  # type: ignore
    conn.authenticate = authenticate  # type: ignore
    session = await conn.new_session()
    assert session is not None
    assert conn.token is None


@pytest.mark.asyncio
async def test_async_new_session_detaches_on_other_errors() -> None:
    conn = _bare(AsyncWsSurrealConnection)
    conn.token = "bad"
    detached: list[UUID] = []
    sid = uuid4()

    async def attach() -> UUID:
        return sid

    async def authenticate(token: str, session_id: UUID | None = None) -> None:
        raise DENIED

    async def detach(session_id: UUID) -> None:
        detached.append(session_id)

    conn.attach = attach  # type: ignore
    conn.authenticate = authenticate  # type: ignore
    conn.detach = detach  # type: ignore
    with pytest.raises(NotAllowedError):
        await conn.new_session()
    assert detached == [sid]


def test_blocking_new_session_survives_expired_token() -> None:
    conn = _bare(BlockingWsSurrealConnection)
    conn.token = "expired"
    sid = uuid4()

    def authenticate(token: str, session_id: UUID | None = None) -> None:
        raise EXPIRED

    conn.attach = lambda: sid  # type: ignore
    conn.authenticate = authenticate  # type: ignore
    assert conn.new_session() is not None
    assert conn.token is None


def test_blocking_session_signin_keeps_connection_token() -> None:
    conn = _bare(BlockingWsSurrealConnection)
    conn.token = "connection-jwt"
    conn._send = lambda message, action: {"result": "session-jwt"}  # type: ignore
    conn.check_response_for_result = lambda response, action: None  # type: ignore
    conn.signin({"user": "u"}, session_id=uuid4())
    assert conn.token == "connection-jwt"
    conn.signin({"user": "u"})
    assert conn.token == "session-jwt"
