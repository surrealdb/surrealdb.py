from __future__ import annotations

from surrealdb.spectron._models import (
    TraceListResponse,
    TraceRecord,
    TraceStatsResponse,
)
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)


def _base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/traces"


class BlockingTraces:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    def list(
        self, *, limit: int | None = None, on_behalf_of: str | None = None
    ) -> TraceListResponse:
        result = self._transport.request(
            "GET",
            self._base,
            params={"limit": limit},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TraceListResponse.from_dict(result)

    def get(self, trace_id: str, *, on_behalf_of: str | None = None) -> TraceRecord:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(trace_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TraceRecord.from_dict(result)

    def stats(self, *, on_behalf_of: str | None = None) -> TraceStatsResponse:
        result = self._transport.request(
            "GET",
            f"{self._base}/stats",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TraceStatsResponse.from_dict(result)


class AsyncTraces:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._base = _base(context_id)

    async def list(
        self, *, limit: int | None = None, on_behalf_of: str | None = None
    ) -> TraceListResponse:
        result = await self._transport.request(
            "GET",
            self._base,
            params={"limit": limit},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TraceListResponse.from_dict(result)

    async def get(
        self, trace_id: str, *, on_behalf_of: str | None = None
    ) -> TraceRecord:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(trace_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TraceRecord.from_dict(result)

    async def stats(self, *, on_behalf_of: str | None = None) -> TraceStatsResponse:
        result = await self._transport.request(
            "GET",
            f"{self._base}/stats",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return TraceStatsResponse.from_dict(result)


__all__ = ["BlockingTraces", "AsyncTraces"]
