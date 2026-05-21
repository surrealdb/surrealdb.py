from __future__ import annotations

import json as _json
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any

from surrealdb.spectron._idempotency import idempotency_key
from surrealdb.spectron._models import (
    ChatResponse,
    ForgetResponse,
    RecallResponse,
    RememberBatchResponse,
    RememberResponse,
)
from surrealdb.spectron._namespaces.documents import (
    AsyncDocuments,
    BlockingDocuments,
)
from surrealdb.spectron._streaming import ChatChunk
from surrealdb.spectron._transport import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    AsyncTransport,
    BlockingTransport,
    quote_path,
)

ScopeArg = Mapping[str, str] | Sequence[tuple[str, str]] | None


def _scope_pairs(scope: ScopeArg) -> list[dict[str, str]]:
    if scope is None:
        return []
    items = scope.items() if isinstance(scope, Mapping) else scope
    return [{"key": str(k), "value": str(v)} for k, v in items]


def _drop_none(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if v is not None}


def _base_path(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}"


def _idempotency_header(method: str, path: str, body: Any) -> dict[str, str]:
    body_bytes = (
        b""
        if body is None
        else _json.dumps(body, separators=(",", ":")).encode("utf-8")
    )
    return {"Idempotency-Key": idempotency_key(method, path, body_bytes)}


class Spectron:
    def __init__(
        self,
        context: str,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: BlockingTransport | None = None,
    ) -> None:
        self._context_id = context
        self._transport = transport or BlockingTransport(
            endpoint=endpoint,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._owns_transport = transport is None
        self._base = _base_path(context)
        self.documents = BlockingDocuments(self._transport, context)

    @property
    def context_id(self) -> str:
        return self._context_id

    @property
    def endpoint(self) -> str:
        return self._transport.endpoint

    @property
    def api_key(self) -> str:
        return self._transport.api_key

    def remember(
        self,
        text: str | None = None,
        *,
        infer: str | None = None,
        session_id: str | None = None,
        scope: ScopeArg = None,
        role: str | None = None,
        memory_category: str | None = None,
        triples: list[dict[str, Any]] | None = None,
    ) -> RememberResponse:
        payload = _drop_none(
            {
                "text": text,
                "infer": infer,
                "sessionId": session_id,
                "scope": _scope_pairs(scope) or None,
                "role": role,
                "memoryCategory": memory_category,
                "triples": triples,
            }
        )
        path = f"{self._base}/facts"
        result = self._transport.request(
            "POST",
            path,
            json=payload,
            headers=_idempotency_header("POST", path, payload),
            idempotent=True,
        )
        return RememberResponse.from_dict(result)

    def remember_many(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        session_id: str | None = None,
        scope: ScopeArg = None,
    ) -> RememberBatchResponse:
        payload = _drop_none(
            {
                "messages": list(items),
                "sessionId": session_id,
                "scope": _scope_pairs(scope) or None,
            }
        )
        path = f"{self._base}/facts/batch"
        result = self._transport.request(
            "POST",
            path,
            json=payload,
            headers=_idempotency_header("POST", path, payload),
            idempotent=True,
        )
        return RememberBatchResponse.from_dict(result)

    def recall(
        self,
        query: str,
        *,
        k: int | None = None,
        mode: str | None = None,
        session_id: str | None = None,
        include: Sequence[str] | None = None,
        as_of: str | None = None,
        at_instant: str | None = None,
    ) -> RecallResponse:
        payload = _drop_none(
            {
                "query": query,
                "k": k,
                "mode": mode,
                "sessionId": session_id,
                "include": list(include) if include is not None else None,
                "asOf": as_of,
                "atInstant": at_instant,
            }
        )
        result = self._transport.request(
            "POST",
            f"{self._base}/query",
            json=payload,
        )
        return RecallResponse.from_dict(result)

    def forget(self, query: str, *, purge: bool = False) -> ForgetResponse:
        payload = _drop_none({"query": query, "purge": purge or None})
        result = self._transport.request(
            "POST",
            f"{self._base}/forget",
            json=payload,
        )
        return ForgetResponse.from_dict(result)

    def chat(
        self,
        message: str,
        *,
        stream: bool = False,
        session_id: str | None = None,
        scope: ScopeArg = None,
        model: str | None = None,
        bypass_cache: bool = False,
    ) -> ChatResponse | Iterator[ChatChunk]:
        payload = _drop_none(
            {
                "message": message,
                "stream": stream or None,
                "sessionId": session_id,
                "scope": _scope_pairs(scope) or None,
                "model": model,
                "bypassCache": bypass_cache or None,
            }
        )
        path = f"{self._base}/chat"
        if stream:
            return self._transport.stream_sse(path, json=payload)
        result = self._transport.request("POST", path, json=payload)
        return ChatResponse.from_dict(result)

    def close(self) -> None:
        if self._owns_transport:
            self._transport.close()

    def __enter__(self) -> Spectron:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


class AsyncSpectron:
    def __init__(
        self,
        context: str,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: AsyncTransport | None = None,
    ) -> None:
        self._context_id = context
        self._transport = transport or AsyncTransport(
            endpoint=endpoint,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._owns_transport = transport is None
        self._base = _base_path(context)
        self.documents = AsyncDocuments(self._transport, context)

    @property
    def context_id(self) -> str:
        return self._context_id

    @property
    def endpoint(self) -> str:
        return self._transport.endpoint

    @property
    def api_key(self) -> str:
        return self._transport.api_key

    async def remember(
        self,
        text: str | None = None,
        *,
        infer: str | None = None,
        session_id: str | None = None,
        scope: ScopeArg = None,
        role: str | None = None,
        memory_category: str | None = None,
        triples: list[dict[str, Any]] | None = None,
    ) -> RememberResponse:
        payload = _drop_none(
            {
                "text": text,
                "infer": infer,
                "sessionId": session_id,
                "scope": _scope_pairs(scope) or None,
                "role": role,
                "memoryCategory": memory_category,
                "triples": triples,
            }
        )
        path = f"{self._base}/facts"
        result = await self._transport.request(
            "POST",
            path,
            json=payload,
            headers=_idempotency_header("POST", path, payload),
            idempotent=True,
        )
        return RememberResponse.from_dict(result)

    async def remember_many(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        session_id: str | None = None,
        scope: ScopeArg = None,
    ) -> RememberBatchResponse:
        payload = _drop_none(
            {
                "messages": list(items),
                "sessionId": session_id,
                "scope": _scope_pairs(scope) or None,
            }
        )
        path = f"{self._base}/facts/batch"
        result = await self._transport.request(
            "POST",
            path,
            json=payload,
            headers=_idempotency_header("POST", path, payload),
            idempotent=True,
        )
        return RememberBatchResponse.from_dict(result)

    async def recall(
        self,
        query: str,
        *,
        k: int | None = None,
        mode: str | None = None,
        session_id: str | None = None,
        include: Sequence[str] | None = None,
        as_of: str | None = None,
        at_instant: str | None = None,
    ) -> RecallResponse:
        payload = _drop_none(
            {
                "query": query,
                "k": k,
                "mode": mode,
                "sessionId": session_id,
                "include": list(include) if include is not None else None,
                "asOf": as_of,
                "atInstant": at_instant,
            }
        )
        result = await self._transport.request(
            "POST",
            f"{self._base}/query",
            json=payload,
        )
        return RecallResponse.from_dict(result)

    async def forget(self, query: str, *, purge: bool = False) -> ForgetResponse:
        payload = _drop_none({"query": query, "purge": purge or None})
        result = await self._transport.request(
            "POST",
            f"{self._base}/forget",
            json=payload,
        )
        return ForgetResponse.from_dict(result)

    async def chat(
        self,
        message: str,
        *,
        stream: bool = False,
        session_id: str | None = None,
        scope: ScopeArg = None,
        model: str | None = None,
        bypass_cache: bool = False,
    ) -> ChatResponse | AsyncIterator[ChatChunk]:
        payload = _drop_none(
            {
                "message": message,
                "stream": stream or None,
                "sessionId": session_id,
                "scope": _scope_pairs(scope) or None,
                "model": model,
                "bypassCache": bypass_cache or None,
            }
        )
        path = f"{self._base}/chat"
        if stream:
            return self._transport.stream_sse(path, json=payload)
        result = await self._transport.request("POST", path, json=payload)
        return ChatResponse.from_dict(result)

    async def close(self) -> None:
        if self._owns_transport:
            await self._transport.close()

    async def __aenter__(self) -> AsyncSpectron:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()


__all__ = ["Spectron", "AsyncSpectron"]
