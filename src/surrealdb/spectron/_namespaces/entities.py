from __future__ import annotations

from surrealdb.spectron._models import (
    EntityHistoryResponse,
    EntityListResponse,
    EntityResponse,
)
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)


def _base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/entities"


class BlockingEntities:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    def list(
        self, *, entity_type: str | None = None, on_behalf_of: str | None = None
    ) -> EntityListResponse:
        result = self._transport.request(
            "GET",
            self._base,
            params={"type": entity_type},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EntityListResponse.from_dict(result)

    def get(
        self, entity_type: str, entity_name: str, *, on_behalf_of: str | None = None
    ) -> EntityResponse:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(entity_type)}/{quote_path(entity_name)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EntityResponse.from_dict(result)

    def delete(
        self, entity_type: str, entity_name: str, *, on_behalf_of: str | None = None
    ) -> None:
        self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(entity_type)}/{quote_path(entity_name)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    def history(
        self,
        entity_type: str,
        entity_name: str,
        key: str,
        *,
        on_behalf_of: str | None = None,
    ) -> EntityHistoryResponse:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(entity_type)}/{quote_path(entity_name)}"
            f"/history/{quote_path(key)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EntityHistoryResponse.from_dict(result)


class AsyncEntities:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    async def list(
        self, *, entity_type: str | None = None, on_behalf_of: str | None = None
    ) -> EntityListResponse:
        result = await self._transport.request(
            "GET",
            self._base,
            params={"type": entity_type},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EntityListResponse.from_dict(result)

    async def get(
        self, entity_type: str, entity_name: str, *, on_behalf_of: str | None = None
    ) -> EntityResponse:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(entity_type)}/{quote_path(entity_name)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EntityResponse.from_dict(result)

    async def delete(
        self, entity_type: str, entity_name: str, *, on_behalf_of: str | None = None
    ) -> None:
        await self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(entity_type)}/{quote_path(entity_name)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    async def history(
        self,
        entity_type: str,
        entity_name: str,
        key: str,
        *,
        on_behalf_of: str | None = None,
    ) -> EntityHistoryResponse:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(entity_type)}/{quote_path(entity_name)}"
            f"/history/{quote_path(key)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return EntityHistoryResponse.from_dict(result)


__all__ = ["BlockingEntities", "AsyncEntities"]
