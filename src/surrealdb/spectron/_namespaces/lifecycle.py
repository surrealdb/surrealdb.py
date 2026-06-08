from __future__ import annotations

from surrealdb.spectron._models import FsckReport, LifecycleResponse
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)
from surrealdb.spectron._util import drop_none as _drop_none


def _base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}"


class BlockingLifecycle:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    def decay(self, *, on_behalf_of: str | None = None) -> LifecycleResponse:
        result = self._transport.request(
            "POST",
            f"{self._base}/lifecycle/decay",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return LifecycleResponse.from_dict(result)

    def expire(self, *, on_behalf_of: str | None = None) -> LifecycleResponse:
        result = self._transport.request(
            "POST",
            f"{self._base}/lifecycle/expire",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return LifecycleResponse.from_dict(result)

    def fsck(
        self,
        *,
        check: str | None = None,
        duplicate_threshold: float | None = None,
        max_results: int | None = None,
        on_behalf_of: str | None = None,
    ) -> FsckReport:
        payload = _drop_none(
            {
                "check": check,
                "duplicateThreshold": duplicate_threshold,
                "maxResults": max_results,
            }
        )
        result = self._transport.request(
            "POST",
            f"{self._base}/fsck",
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return FsckReport.from_dict(result)


class AsyncLifecycle:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    async def decay(self, *, on_behalf_of: str | None = None) -> LifecycleResponse:
        result = await self._transport.request(
            "POST",
            f"{self._base}/lifecycle/decay",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return LifecycleResponse.from_dict(result)

    async def expire(self, *, on_behalf_of: str | None = None) -> LifecycleResponse:
        result = await self._transport.request(
            "POST",
            f"{self._base}/lifecycle/expire",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return LifecycleResponse.from_dict(result)

    async def fsck(
        self,
        *,
        check: str | None = None,
        duplicate_threshold: float | None = None,
        max_results: int | None = None,
        on_behalf_of: str | None = None,
    ) -> FsckReport:
        payload = _drop_none(
            {
                "check": check,
                "duplicateThreshold": duplicate_threshold,
                "maxResults": max_results,
            }
        )
        result = await self._transport.request(
            "POST",
            f"{self._base}/fsck",
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return FsckReport.from_dict(result)


__all__ = ["BlockingLifecycle", "AsyncLifecycle"]
