from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from surrealdb.spectron._models import KeyDetail, MintedKey
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)
from surrealdb.spectron._util import drop_none


def _base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/keys"


class BlockingKeys:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    def create(
        self,
        *,
        name: str | None = None,
        grants: Mapping[str, Any] | None = None,
        ttl_seconds: int | None = None,
        on_behalf_of: str | None = None,
    ) -> MintedKey:
        payload = drop_none(
            {"name": name, "grants": dict(grants) if grants is not None else None}
        )
        result = self._transport.request(
            "POST",
            self._base,
            json=payload or None,
            params={"ttlSeconds": ttl_seconds},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return MintedKey.from_dict(result)

    def list(self, *, on_behalf_of: str | None = None) -> list[KeyDetail]:
        result = self._transport.request(
            "GET",
            self._base,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return [KeyDetail.from_dict(item) for item in result or []]

    def delete(self, key_name: str, *, on_behalf_of: str | None = None) -> None:
        self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(key_name)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    def rotate(
        self,
        key_name: str,
        *,
        ttl_seconds: int | None = None,
        on_behalf_of: str | None = None,
    ) -> MintedKey:
        result = self._transport.request(
            "POST",
            f"{self._base}/{quote_path(key_name)}/rotate",
            params={"ttlSeconds": ttl_seconds},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return MintedKey.from_dict(result)


class AsyncKeys:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    async def create(
        self,
        *,
        name: str | None = None,
        grants: Mapping[str, Any] | None = None,
        ttl_seconds: int | None = None,
        on_behalf_of: str | None = None,
    ) -> MintedKey:
        payload = drop_none(
            {"name": name, "grants": dict(grants) if grants is not None else None}
        )
        result = await self._transport.request(
            "POST",
            self._base,
            json=payload or None,
            params={"ttlSeconds": ttl_seconds},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return MintedKey.from_dict(result)

    async def list(self, *, on_behalf_of: str | None = None) -> list[KeyDetail]:
        result = await self._transport.request(
            "GET",
            self._base,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return [KeyDetail.from_dict(item) for item in result or []]

    async def delete(self, key_name: str, *, on_behalf_of: str | None = None) -> None:
        await self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(key_name)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    async def rotate(
        self,
        key_name: str,
        *,
        ttl_seconds: int | None = None,
        on_behalf_of: str | None = None,
    ) -> MintedKey:
        result = await self._transport.request(
            "POST",
            f"{self._base}/{quote_path(key_name)}/rotate",
            params={"ttlSeconds": ttl_seconds},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return MintedKey.from_dict(result)


__all__ = ["BlockingKeys", "AsyncKeys"]
