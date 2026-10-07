from uuid import UUID, uuid4

import pytest

from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.errors import NotAllowedError

EXPIRED = NotAllowedError(
    "NotAllowed",
    "The token has expired",
    details={"kind": "Auth", "details": {"kind": "TokenExpired"}},
)
DENIED = NotAllowedError("NotAllowed", "Anonymous access not allowed")


@pytest.mark.asyncio
async def test_async_new_session_survives_expired_token() -> None:
    conn = object.__new__(AsyncWsSurrealConnection)
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
    conn = object.__new__(AsyncWsSurrealConnection)
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
    conn = object.__new__(BlockingWsSurrealConnection)
    conn.token = "expired"
    sid = uuid4()

    def authenticate(token: str, session_id: UUID | None = None) -> None:
        raise EXPIRED

    conn.attach = lambda: sid  # type: ignore
    conn.authenticate = authenticate  # type: ignore
    assert conn.new_session() is not None
    assert conn.token is None


def test_blocking_session_signin_keeps_connection_token() -> None:
    conn = object.__new__(BlockingWsSurrealConnection)
    conn.token = "connection-jwt"
    conn._send = lambda message, action: {"result": "session-jwt"}  # type: ignore
    conn.check_response_for_result = lambda response, action: None  # type: ignore
    conn.signin({"user": "u"}, session_id=uuid4())
    assert conn.token == "connection-jwt"
    conn.signin({"user": "u"})
    assert conn.token == "session-jwt"
