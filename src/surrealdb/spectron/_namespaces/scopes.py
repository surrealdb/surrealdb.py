from __future__ import annotations

from surrealdb.spectron._models import ForgetScopeResponse, ScopeNode
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)
from surrealdb.spectron._util import drop_none


def _base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/scopes"


class BlockingScopes:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    def register(
        self,
        path: str,
        *,
        description: str | None = None,
        display_name: str | None = None,
        on_behalf_of: str | None = None,
    ) -> ScopeNode:
        payload = drop_none(
            {"path": path, "description": description, "displayName": display_name}
        )
        result = self._transport.request(
            "POST",
            self._base,
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ScopeNode.from_dict(result)

    def list(self, *, on_behalf_of: str | None = None) -> list[ScopeNode]:
        result = self._transport.request(
            "GET",
            self._base,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return [ScopeNode.from_dict(item) for item in result or []]

    def delete(self, path: str, *, on_behalf_of: str | None = None) -> None:
        self._transport.request(
            "DELETE",
            self._base,
            params={"path": path},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    def forget(
        self, path: str | None = None, *, on_behalf_of: str | None = None
    ) -> ForgetScopeResponse:
        result = self._transport.request(
            "POST",
            f"{self._base}/forget",
            json=drop_none({"path": path}) or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ForgetScopeResponse.from_dict(result)


class AsyncScopes:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    async def register(
        self,
        path: str,
        *,
        description: str | None = None,
        display_name: str | None = None,
        on_behalf_of: str | None = None,
    ) -> ScopeNode:
        payload = drop_none(
            {"path": path, "description": description, "displayName": display_name}
        )
        result = await self._transport.request(
            "POST",
            self._base,
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ScopeNode.from_dict(result)

    async def list(self, *, on_behalf_of: str | None = None) -> list[ScopeNode]:
        result = await self._transport.request(
            "GET",
            self._base,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return [ScopeNode.from_dict(item) for item in result or []]

    async def delete(self, path: str, *, on_behalf_of: str | None = None) -> None:
        await self._transport.request(
            "DELETE",
            self._base,
            params={"path": path},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    async def forget(
        self, path: str | None = None, *, on_behalf_of: str | None = None
    ) -> ForgetScopeResponse:
        result = await self._transport.request(
            "POST",
            f"{self._base}/forget",
            json=drop_none({"path": path}) or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ForgetScopeResponse.from_dict(result)


__all__ = ["BlockingScopes", "AsyncScopes"]
