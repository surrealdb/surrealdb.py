from __future__ import annotations

from collections.abc import Sequence

from surrealdb.spectron._models import EffectiveGrants, Principal
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)


def _base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/principals"


class BlockingPrincipals:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    def list(self, *, on_behalf_of: str | None = None) -> list[Principal]:
        result = self._transport.request(
            "GET",
            self._base,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return [Principal.from_dict(item) for item in result or []]

    def get(self, principal_id: str, *, on_behalf_of: str | None = None) -> Principal:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(principal_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Principal.from_dict(result)

    def grant(
        self,
        principal_id: str,
        path: str,
        verbs: Sequence[str],
        *,
        on_behalf_of: str | None = None,
    ) -> Principal:
        result = self._transport.request(
            "POST",
            f"{self._base}/{quote_path(principal_id)}/grants",
            json={"path": path, "verbs": list(verbs)},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Principal.from_dict(result)

    def revoke(
        self,
        principal_id: str,
        path: str,
        verbs: Sequence[str],
        *,
        on_behalf_of: str | None = None,
    ) -> Principal:
        result = self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(principal_id)}/grants",
            json={"path": path, "verbs": list(verbs)},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Principal.from_dict(result)

    def effective(
        self,
        principal_id: str,
        path: str,
        *,
        as_of: str | None = None,
        on_behalf_of: str | None = None,
    ) -> EffectiveGrants:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(principal_id)}/effective",
            params={"path": path, "asOf": as_of},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EffectiveGrants.from_dict(result)


class AsyncPrincipals:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    async def list(self, *, on_behalf_of: str | None = None) -> list[Principal]:
        result = await self._transport.request(
            "GET",
            self._base,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return [Principal.from_dict(item) for item in result or []]

    async def get(
        self, principal_id: str, *, on_behalf_of: str | None = None
    ) -> Principal:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(principal_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Principal.from_dict(result)

    async def grant(
        self,
        principal_id: str,
        path: str,
        verbs: Sequence[str],
        *,
        on_behalf_of: str | None = None,
    ) -> Principal:
        result = await self._transport.request(
            "POST",
            f"{self._base}/{quote_path(principal_id)}/grants",
            json={"path": path, "verbs": list(verbs)},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Principal.from_dict(result)

    async def revoke(
        self,
        principal_id: str,
        path: str,
        verbs: Sequence[str],
        *,
        on_behalf_of: str | None = None,
    ) -> Principal:
        result = await self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(principal_id)}/grants",
            json={"path": path, "verbs": list(verbs)},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Principal.from_dict(result)

    async def effective(
        self,
        principal_id: str,
        path: str,
        *,
        as_of: str | None = None,
        on_behalf_of: str | None = None,
    ) -> EffectiveGrants:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(principal_id)}/effective",
            params={"path": path, "asOf": as_of},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EffectiveGrants.from_dict(result)


__all__ = ["BlockingPrincipals", "AsyncPrincipals"]
