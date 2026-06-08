from __future__ import annotations

from typing import Any

from surrealdb.spectron._models import (
    Session,
    SessionContextResponse,
    TurnListResponse,
)
from surrealdb.spectron._scope import ScopeArg, scope_paths
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)
from surrealdb.spectron._util import drop_none


def _base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/sessions"


class BlockingSessions:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    def create(
        self,
        *,
        scope: ScopeArg = None,
        metadata: Any | None = None,
        on_behalf_of: str | None = None,
    ) -> Session:
        payload = drop_none({"scope": scope_paths(scope) or None, "metadata": metadata})
        result = self._transport.request(
            "POST",
            self._base,
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Session.from_dict(result)

    def delete(self, session_id: str, *, on_behalf_of: str | None = None) -> None:
        self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(session_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    def context(
        self, session_id: str, query: str, *, on_behalf_of: str | None = None
    ) -> SessionContextResponse:
        result = self._transport.request(
            "POST",
            f"{self._base}/{quote_path(session_id)}/context",
            json={"query": query},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return SessionContextResponse.from_dict(result)

    def turns(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        on_behalf_of: str | None = None,
    ) -> TurnListResponse:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(session_id)}/turns",
            params={"limit": limit, "offset": offset},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TurnListResponse.from_dict(result)


class AsyncSessions:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    async def create(
        self,
        *,
        scope: ScopeArg = None,
        metadata: Any | None = None,
        on_behalf_of: str | None = None,
    ) -> Session:
        payload = drop_none({"scope": scope_paths(scope) or None, "metadata": metadata})
        result = await self._transport.request(
            "POST",
            self._base,
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Session.from_dict(result)

    async def delete(self, session_id: str, *, on_behalf_of: str | None = None) -> None:
        await self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(session_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    async def context(
        self, session_id: str, query: str, *, on_behalf_of: str | None = None
    ) -> SessionContextResponse:
        result = await self._transport.request(
            "POST",
            f"{self._base}/{quote_path(session_id)}/context",
            json={"query": query},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return SessionContextResponse.from_dict(result)

    async def turns(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        on_behalf_of: str | None = None,
    ) -> TurnListResponse:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(session_id)}/turns",
            params={"limit": limit, "offset": offset},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TurnListResponse.from_dict(result)


__all__ = ["BlockingSessions", "AsyncSessions"]
