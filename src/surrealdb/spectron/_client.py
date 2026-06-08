from __future__ import annotations

import json as _json
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any

from surrealdb.spectron._idempotency import idempotency_key
from surrealdb.spectron._models import (
    AuditResponse,
    ChatResponse,
    ConsolidateResponse,
    ContextQueryResponse,
    ElaborateResponse,
    ForgetResponse,
    ProfileResponse,
    RecallResponse,
    ReflectResponse,
    RememberBatchResponse,
    RememberResponse,
    StateResponse,
    WhoamiResponse,
)
from surrealdb.spectron._namespaces.documents import (
    AsyncDocuments,
    BlockingDocuments,
)
from surrealdb.spectron._namespaces.entities import (
    AsyncEntities,
    BlockingEntities,
)
from surrealdb.spectron._namespaces.keys import AsyncKeys, BlockingKeys
from surrealdb.spectron._namespaces.lifecycle import (
    AsyncLifecycle,
    BlockingLifecycle,
)
from surrealdb.spectron._namespaces.principals import (
    AsyncPrincipals,
    BlockingPrincipals,
)
from surrealdb.spectron._namespaces.scopes import AsyncScopes, BlockingScopes
from surrealdb.spectron._namespaces.sessions import (
    AsyncSessions,
    BlockingSessions,
)
from surrealdb.spectron._namespaces.traces import AsyncTraces, BlockingTraces
from surrealdb.spectron._scope import ScopeArg
from surrealdb.spectron._scope import scope_paths as _scope_paths
from surrealdb.spectron._streaming import ChatChunk
from surrealdb.spectron._transport import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    AsyncTransport,
    BlockingTransport,
    on_behalf_of_header,
    quote_path,
)
from surrealdb.spectron._util import drop_none as _drop_none


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
        self.sessions = BlockingSessions(self._transport, context)
        self.entities = BlockingEntities(self._transport, context)
        self.scopes = BlockingScopes(self._transport, context)
        self.principals = BlockingPrincipals(self._transport, context)
        self.keys = BlockingKeys(self._transport, context)
        self.traces = BlockingTraces(self._transport, context)
        self.lifecycle = BlockingLifecycle(self._transport, context)

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
        labels: Sequence[str] | None = None,
        triples: list[dict[str, Any]] | None = None,
        on_behalf_of: str | None = None,
    ) -> RememberResponse:
        payload = _drop_none(
            {
                "text": text,
                "infer": infer,
                "session_id": session_id,
                "scope": _scope_paths(scope) or None,
                "role": role,
                "memory_category": memory_category,
                "labels": list(labels) if labels is not None else None,
                "triples": triples,
            }
        )
        path = f"{self._base}/facts"
        result = self._transport.request(
            "POST",
            path,
            json=payload,
            headers={
                **_idempotency_header("POST", path, payload),
                **on_behalf_of_header(on_behalf_of),
            },
            idempotent=True,
        )
        return RememberResponse.from_dict(result)

    def remember_many(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        session_id: str | None = None,
        scope: ScopeArg = None,
        extract: str | None = None,
        infer: str | None = None,
        labels: Sequence[str] | None = None,
        on_behalf_of: str | None = None,
    ) -> RememberBatchResponse:
        payload = _drop_none(
            {
                "messages": list(items),
                "session_id": session_id,
                "scope": _scope_paths(scope) or None,
                "extract": extract,
                "infer": infer,
                "labels": list(labels) if labels is not None else None,
            }
        )
        path = f"{self._base}/facts/batch"
        result = self._transport.request(
            "POST",
            path,
            json=payload,
            headers={
                **_idempotency_header("POST", path, payload),
                **on_behalf_of_header(on_behalf_of),
            },
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
        labels: Sequence[str] | None = None,
        lens: Sequence[str] | None = None,
        scope_view: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        source: str | None = None,
        location: Mapping[str, Any] | None = None,
        on_behalf_of: str | None = None,
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
                "labels": list(labels) if labels is not None else None,
                "lens": list(lens) if lens is not None else None,
                "scopeView": scope_view,
                "validFrom": valid_from,
                "validUntil": valid_until,
                "source": source,
                "location": dict(location) if location is not None else None,
            }
        )
        result = self._transport.request(
            "POST",
            f"{self._base}/query",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return RecallResponse.from_dict(result)

    def forget(
        self, query: str, *, purge: bool = False, on_behalf_of: str | None = None
    ) -> ForgetResponse:
        payload = _drop_none({"query": query, "purge": purge or None})
        result = self._transport.request(
            "POST",
            f"{self._base}/forget",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
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
        labels: Sequence[str] | None = None,
        on_behalf_of: str | None = None,
    ) -> ChatResponse | Iterator[ChatChunk]:
        payload = _drop_none(
            {
                "message": message,
                "stream": stream or None,
                "sessionId": session_id,
                "scope": _scope_paths(scope) or None,
                "model": model,
                "bypassCache": bypass_cache or None,
                "labels": list(labels) if labels is not None else None,
            }
        )
        path = f"{self._base}/chat"
        if stream:
            return self._transport.stream_sse(
                path,
                json=payload,
                headers=on_behalf_of_header(on_behalf_of) or None,
            )
        result = self._transport.request(
            "POST",
            path,
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ChatResponse.from_dict(result)

    def consolidate(
        self,
        *,
        dry_run: bool = False,
        fact_limit: int | None = None,
        observation_limit: int | None = None,
        on_behalf_of: str | None = None,
    ) -> ConsolidateResponse:
        payload = _drop_none(
            {
                "dryRun": dry_run or None,
                "factLimit": fact_limit,
                "observationLimit": observation_limit,
            }
        )
        result = self._transport.request(
            "POST",
            f"{self._base}/consolidate",
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ConsolidateResponse.from_dict(result)

    def audit(
        self,
        *,
        principal: str | None = None,
        key: str | None = None,
        kind: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int | None = None,
        on_behalf_of: str | None = None,
    ) -> AuditResponse:
        params = {
            "principal": principal,
            "key": key,
            "kind": kind,
            "since": since,
            "until": until,
            "limit": limit,
        }
        result = self._transport.request(
            "GET",
            f"{self._base}/audit",
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return AuditResponse.from_dict(result)

    def reflect(
        self, query: str, *, persist: bool = False, on_behalf_of: str | None = None
    ) -> ReflectResponse:
        payload = _drop_none({"query": query, "persist": persist or None})
        result = self._transport.request(
            "POST",
            f"{self._base}/reflect",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ReflectResponse.from_dict(result)

    def elaborate(
        self,
        *,
        entity_ref: str | None = None,
        budget: int | None = None,
        dry_run: bool = False,
        sweep: bool = False,
        on_behalf_of: str | None = None,
    ) -> ElaborateResponse:
        payload = _drop_none(
            {
                "entityRef": entity_ref,
                "budget": budget,
                "dryRun": dry_run or None,
                "sweep": sweep or None,
            }
        )
        result = self._transport.request(
            "POST",
            f"{self._base}/elaborate",
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ElaborateResponse.from_dict(result)

    def inspect(
        self,
        ref: str,
        *,
        as_of: str | None = None,
        at_instant: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        on_behalf_of: str | None = None,
    ) -> dict[str, Any]:
        """Inspect a single memory object by reference.

        The wire grammar for ``ref`` is ``entity:<type>/<name>``,
        ``attribute:<type>/<name>/<key>``, ``relation:<subject>/<label>/<object>``,
        or ``trace:<id>``. The response shape varies by the addressed object
        (discriminated by its ``kind`` field), so it is returned as the decoded
        payload rather than a fixed model.
        """
        params = {
            "ref": ref,
            "asOf": as_of,
            "atInstant": at_instant,
            "validFrom": valid_from,
            "validUntil": valid_until,
        }
        result = self._transport.request(
            "GET",
            f"{self._base}/inspect",
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return result

    def query_context(
        self,
        query: str,
        *,
        k: int | None = None,
        labels: Sequence[str] | None = None,
        lens: Sequence[str] | None = None,
        scope_view: str | None = None,
        on_behalf_of: str | None = None,
    ) -> ContextQueryResponse:
        payload = _drop_none(
            {
                "query": query,
                "k": k,
                "labels": list(labels) if labels is not None else None,
                "lens": list(lens) if lens is not None else None,
                "scopeView": scope_view,
            }
        )
        result = self._transport.request(
            "POST",
            f"{self._base}/context",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ContextQueryResponse.from_dict(result)

    def state(self, *, on_behalf_of: str | None = None) -> StateResponse:
        result = self._transport.request(
            "GET",
            f"{self._base}/state",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return StateResponse.from_dict(result)

    def whoami(self, *, on_behalf_of: str | None = None) -> WhoamiResponse:
        result = self._transport.request(
            "GET",
            f"{self._base}/me",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return WhoamiResponse.from_dict(result)

    def profile(self, *, on_behalf_of: str | None = None) -> ProfileResponse:
        result = self._transport.request(
            "GET",
            f"{self._base}/profile",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ProfileResponse.from_dict(result)

    def health(self) -> dict[str, Any]:
        """Liveness probe. Not context-scoped — hits ``/api/v1/health``."""
        return self._transport.request("GET", "/api/v1/health")

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
        self.sessions = AsyncSessions(self._transport, context)
        self.entities = AsyncEntities(self._transport, context)
        self.scopes = AsyncScopes(self._transport, context)
        self.principals = AsyncPrincipals(self._transport, context)
        self.keys = AsyncKeys(self._transport, context)
        self.traces = AsyncTraces(self._transport, context)
        self.lifecycle = AsyncLifecycle(self._transport, context)

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
        labels: Sequence[str] | None = None,
        triples: list[dict[str, Any]] | None = None,
        on_behalf_of: str | None = None,
    ) -> RememberResponse:
        payload = _drop_none(
            {
                "text": text,
                "infer": infer,
                "session_id": session_id,
                "scope": _scope_paths(scope) or None,
                "role": role,
                "memory_category": memory_category,
                "labels": list(labels) if labels is not None else None,
                "triples": triples,
            }
        )
        path = f"{self._base}/facts"
        result = await self._transport.request(
            "POST",
            path,
            json=payload,
            headers={
                **_idempotency_header("POST", path, payload),
                **on_behalf_of_header(on_behalf_of),
            },
            idempotent=True,
        )
        return RememberResponse.from_dict(result)

    async def remember_many(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        session_id: str | None = None,
        scope: ScopeArg = None,
        extract: str | None = None,
        infer: str | None = None,
        labels: Sequence[str] | None = None,
        on_behalf_of: str | None = None,
    ) -> RememberBatchResponse:
        payload = _drop_none(
            {
                "messages": list(items),
                "session_id": session_id,
                "scope": _scope_paths(scope) or None,
                "extract": extract,
                "infer": infer,
                "labels": list(labels) if labels is not None else None,
            }
        )
        path = f"{self._base}/facts/batch"
        result = await self._transport.request(
            "POST",
            path,
            json=payload,
            headers={
                **_idempotency_header("POST", path, payload),
                **on_behalf_of_header(on_behalf_of),
            },
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
        labels: Sequence[str] | None = None,
        lens: Sequence[str] | None = None,
        scope_view: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        source: str | None = None,
        location: Mapping[str, Any] | None = None,
        on_behalf_of: str | None = None,
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
                "labels": list(labels) if labels is not None else None,
                "lens": list(lens) if lens is not None else None,
                "scopeView": scope_view,
                "validFrom": valid_from,
                "validUntil": valid_until,
                "source": source,
                "location": dict(location) if location is not None else None,
            }
        )
        result = await self._transport.request(
            "POST",
            f"{self._base}/query",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return RecallResponse.from_dict(result)

    async def forget(
        self, query: str, *, purge: bool = False, on_behalf_of: str | None = None
    ) -> ForgetResponse:
        payload = _drop_none({"query": query, "purge": purge or None})
        result = await self._transport.request(
            "POST",
            f"{self._base}/forget",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
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
        labels: Sequence[str] | None = None,
        on_behalf_of: str | None = None,
    ) -> ChatResponse | AsyncIterator[ChatChunk]:
        payload = _drop_none(
            {
                "message": message,
                "stream": stream or None,
                "sessionId": session_id,
                "scope": _scope_paths(scope) or None,
                "model": model,
                "bypassCache": bypass_cache or None,
                "labels": list(labels) if labels is not None else None,
            }
        )
        path = f"{self._base}/chat"
        if stream:
            return self._transport.stream_sse(
                path,
                json=payload,
                headers=on_behalf_of_header(on_behalf_of) or None,
            )
        result = await self._transport.request(
            "POST",
            path,
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ChatResponse.from_dict(result)

    async def consolidate(
        self,
        *,
        dry_run: bool = False,
        fact_limit: int | None = None,
        observation_limit: int | None = None,
        on_behalf_of: str | None = None,
    ) -> ConsolidateResponse:
        payload = _drop_none(
            {
                "dryRun": dry_run or None,
                "factLimit": fact_limit,
                "observationLimit": observation_limit,
            }
        )
        result = await self._transport.request(
            "POST",
            f"{self._base}/consolidate",
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ConsolidateResponse.from_dict(result)

    async def audit(
        self,
        *,
        principal: str | None = None,
        key: str | None = None,
        kind: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int | None = None,
        on_behalf_of: str | None = None,
    ) -> AuditResponse:
        params = {
            "principal": principal,
            "key": key,
            "kind": kind,
            "since": since,
            "until": until,
            "limit": limit,
        }
        result = await self._transport.request(
            "GET",
            f"{self._base}/audit",
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return AuditResponse.from_dict(result)

    async def reflect(
        self, query: str, *, persist: bool = False, on_behalf_of: str | None = None
    ) -> ReflectResponse:
        payload = _drop_none({"query": query, "persist": persist or None})
        result = await self._transport.request(
            "POST",
            f"{self._base}/reflect",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ReflectResponse.from_dict(result)

    async def elaborate(
        self,
        *,
        entity_ref: str | None = None,
        budget: int | None = None,
        dry_run: bool = False,
        sweep: bool = False,
        on_behalf_of: str | None = None,
    ) -> ElaborateResponse:
        payload = _drop_none(
            {
                "entityRef": entity_ref,
                "budget": budget,
                "dryRun": dry_run or None,
                "sweep": sweep or None,
            }
        )
        result = await self._transport.request(
            "POST",
            f"{self._base}/elaborate",
            json=payload or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ElaborateResponse.from_dict(result)

    async def inspect(
        self,
        ref: str,
        *,
        as_of: str | None = None,
        at_instant: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        on_behalf_of: str | None = None,
    ) -> dict[str, Any]:
        """Inspect a single memory object by reference.

        The wire grammar for ``ref`` is ``entity:<type>/<name>``,
        ``attribute:<type>/<name>/<key>``, ``relation:<subject>/<label>/<object>``,
        or ``trace:<id>``. The response shape varies by the addressed object
        (discriminated by its ``kind`` field), so it is returned as the decoded
        payload rather than a fixed model.
        """
        params = {
            "ref": ref,
            "asOf": as_of,
            "atInstant": at_instant,
            "validFrom": valid_from,
            "validUntil": valid_until,
        }
        result = await self._transport.request(
            "GET",
            f"{self._base}/inspect",
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return result

    async def query_context(
        self,
        query: str,
        *,
        k: int | None = None,
        labels: Sequence[str] | None = None,
        lens: Sequence[str] | None = None,
        scope_view: str | None = None,
        on_behalf_of: str | None = None,
    ) -> ContextQueryResponse:
        payload = _drop_none(
            {
                "query": query,
                "k": k,
                "labels": list(labels) if labels is not None else None,
                "lens": list(lens) if lens is not None else None,
                "scopeView": scope_view,
            }
        )
        result = await self._transport.request(
            "POST",
            f"{self._base}/context",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ContextQueryResponse.from_dict(result)

    async def state(self, *, on_behalf_of: str | None = None) -> StateResponse:
        result = await self._transport.request(
            "GET",
            f"{self._base}/state",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return StateResponse.from_dict(result)

    async def whoami(self, *, on_behalf_of: str | None = None) -> WhoamiResponse:
        result = await self._transport.request(
            "GET",
            f"{self._base}/me",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return WhoamiResponse.from_dict(result)

    async def profile(self, *, on_behalf_of: str | None = None) -> ProfileResponse:
        result = await self._transport.request(
            "GET",
            f"{self._base}/profile",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ProfileResponse.from_dict(result)

    async def health(self) -> dict[str, Any]:
        """Liveness probe. Not context-scoped — hits ``/api/v1/health``."""
        return await self._transport.request("GET", "/api/v1/health")

    async def close(self) -> None:
        if self._owns_transport:
            await self._transport.close()

    async def __aenter__(self) -> AsyncSpectron:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()


__all__ = ["Spectron", "AsyncSpectron"]
