from __future__ import annotations

import builtins
from collections.abc import Mapping
from typing import Any

from surrealdb.spectron._models import (
    ChatReply,
    ContextResult,
    Entity,
    EntityHistoryEntry,
    ExtractionResult,
    ForgetResult,
    MemoryQueryResponse,
    ProfileResponse,
    ReflectionResult,
    SessionInfo,
    StructuredState,
    TraceListResponse,
    TraceRecord,
    TraceStats,
    Turn,
    TurnRole,
)
from surrealdb.spectron._namespaces._paths import enduser_base
from surrealdb.spectron._scope import serialise_scope
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    quote_path,
)


def _session_create_payload(
    scope: Mapping[str, str] | None,
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    scope_payload = serialise_scope(scope)
    if scope_payload is not None:
        payload["scope"] = scope_payload
    if metadata is not None:
        payload["metadata"] = dict(metadata)
    return payload


def _turn_payload(role: TurnRole | str, content: str) -> dict[str, Any]:
    return {
        "role": role.value if isinstance(role, TurnRole) else role,
        "content": content,
    }


def _context_payload(query: str, k: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": query}
    if k is not None:
        payload["k"] = k
    return payload


class BlockingSession:
    def __init__(
        self,
        transport: BlockingTransport,
        context_id: str,
        info: SessionInfo,
    ) -> None:
        self._t = transport
        self._context_id = context_id
        self._info = info
        self._base = f"{enduser_base(context_id)}/sessions/{quote_path(info.id)}"

    @property
    def id(self) -> str:
        return self._info.id

    @property
    def info(self) -> SessionInfo:
        return self._info

    def close(self) -> None:
        self._t.delete(self._base)

    def turn(self, role: TurnRole | str, content: str) -> ExtractionResult:
        body = self._t.post(f"{self._base}/turns", json=_turn_payload(role, content))
        return ExtractionResult.from_dict(body)

    def turns(self) -> list[Turn]:
        body = self._t.get(f"{self._base}/turns")
        if isinstance(body, dict) and "turns" in body:
            body = body["turns"]
        if not isinstance(body, list):
            return []
        return [Turn.from_dict(t) for t in body]

    def context(self, query: str, *, k: int | None = None) -> ContextResult:
        body = self._t.post(f"{self._base}/context", json=_context_payload(query, k))
        return ContextResult.from_dict(body)

    def chat(self, message: str) -> ChatReply:
        body = self._t.post(f"{self._base}/chat", json={"message": message})
        return ChatReply.from_dict(body)


class BlockingSessions:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._base = f"{enduser_base(context_id)}/sessions"

    def create(
        self,
        *,
        scope: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> BlockingSession:
        body = self._t.post(self._base, json=_session_create_payload(scope, metadata))
        if not isinstance(body, dict):
            raise ValueError(
                f"Expected JSON object from session create, got {type(body).__name__}"
            )
        info = SessionInfo.from_dict(body)
        return BlockingSession(self._t, self._context_id, info)


class BlockingEntities:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/entities"

    def list(self, *, type: str | None = None) -> list[Entity]:
        body = self._t.get(self._base, params={"type": type})
        if isinstance(body, dict) and "entities" in body:
            body = body["entities"]
        if not isinstance(body, list):
            return []
        return [Entity.from_dict(e) for e in body]

    def get(self, type: str, name: str) -> Entity:
        body = self._t.get(f"{self._base}/{quote_path(type)}/{quote_path(name)}")
        return Entity.from_dict(body)

    def history(
        self, type: str, name: str, key: str
    ) -> builtins.list[EntityHistoryEntry]:
        body = self._t.get(
            f"{self._base}/{quote_path(type)}/{quote_path(name)}/history/{quote_path(key)}"
        )
        if isinstance(body, dict) and "history" in body:
            body = body["history"]
        if not isinstance(body, list):
            return []
        return [EntityHistoryEntry.from_dict(e) for e in body]

    def delete(self, type: str, name: str) -> None:
        self._t.delete(f"{self._base}/{quote_path(type)}/{quote_path(name)}")


class BlockingLifecycle:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/lifecycle"

    def expire(self) -> None:
        self._t.post(f"{self._base}/expire", json={})

    def decay(self) -> None:
        self._t.post(f"{self._base}/decay", json={})


class BlockingTraces:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/traces"

    def list(self, *, limit: int | None = None) -> list[TraceRecord]:
        body = self._t.get(self._base, params={"limit": limit})
        if isinstance(body, dict) and "traces" in body:
            return TraceListResponse.from_dict(body).traces
        if isinstance(body, list):
            return [TraceRecord.from_dict(t) for t in body]
        return []

    def get(self, trace_id: str) -> TraceRecord:
        body = self._t.get(f"{self._base}/{quote_path(trace_id)}")
        return TraceRecord.from_dict(body)

    def stats(self) -> TraceStats:
        body = self._t.get(f"{self._base}/stats")
        return TraceStats.from_dict(body)


class BlockingMemory:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._base = enduser_base(context_id)
        self.sessions = BlockingSessions(transport, context_id)
        self.entities = BlockingEntities(transport, context_id)
        self.lifecycle = BlockingLifecycle(transport, context_id)
        self.traces = BlockingTraces(transport, context_id)

    def query(
        self,
        query: str,
        *,
        k: int | None = None,
        session_id: str | None = None,
    ) -> MemoryQueryResponse:
        payload: dict[str, Any] = {"query": query}
        if k is not None:
            payload["k"] = k
        if session_id is not None:
            payload["sessionId"] = session_id
        body = self._t.post(f"{self._base}/query", json=payload)
        return MemoryQueryResponse.from_dict(body)

    def context(self, query: str, *, k: int | None = None) -> ContextResult:
        body = self._t.post(f"{self._base}/context", json=_context_payload(query, k))
        return ContextResult.from_dict(body)

    def state(self) -> StructuredState:
        body = self._t.get(f"{self._base}/state")
        return StructuredState.from_dict(body)

    def profile(self) -> ProfileResponse:
        body = self._t.get(f"{self._base}/profile")
        return ProfileResponse.from_dict(body)

    def reflect(self, query: str, *, persist: bool = False) -> ReflectionResult:
        payload: dict[str, Any] = {"query": query, "persist": persist}
        body = self._t.post(f"{self._base}/reflect", json=payload)
        return ReflectionResult.from_dict(body)

    def forget(self, query: str) -> ForgetResult:
        body = self._t.post(f"{self._base}/forget", json={"query": query})
        if isinstance(body, int):
            return ForgetResult(deleted=body)
        return ForgetResult.from_dict(body)


class AsyncSession:
    def __init__(
        self,
        transport: AsyncTransport,
        context_id: str,
        info: SessionInfo,
    ) -> None:
        self._t = transport
        self._context_id = context_id
        self._info = info
        self._base = f"{enduser_base(context_id)}/sessions/{quote_path(info.id)}"

    @property
    def id(self) -> str:
        return self._info.id

    @property
    def info(self) -> SessionInfo:
        return self._info

    async def close(self) -> None:
        await self._t.delete(self._base)

    async def turn(self, role: TurnRole | str, content: str) -> ExtractionResult:
        body = await self._t.post(
            f"{self._base}/turns", json=_turn_payload(role, content)
        )
        return ExtractionResult.from_dict(body)

    async def turns(self) -> list[Turn]:
        body = await self._t.get(f"{self._base}/turns")
        if isinstance(body, dict) and "turns" in body:
            body = body["turns"]
        if not isinstance(body, list):
            return []
        return [Turn.from_dict(t) for t in body]

    async def context(self, query: str, *, k: int | None = None) -> ContextResult:
        body = await self._t.post(
            f"{self._base}/context", json=_context_payload(query, k)
        )
        return ContextResult.from_dict(body)

    async def chat(self, message: str) -> ChatReply:
        body = await self._t.post(f"{self._base}/chat", json={"message": message})
        return ChatReply.from_dict(body)


class AsyncSessions:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._base = f"{enduser_base(context_id)}/sessions"

    async def create(
        self,
        *,
        scope: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AsyncSession:
        body = await self._t.post(
            self._base, json=_session_create_payload(scope, metadata)
        )
        if not isinstance(body, dict):
            raise ValueError(
                f"Expected JSON object from session create, got {type(body).__name__}"
            )
        info = SessionInfo.from_dict(body)
        return AsyncSession(self._t, self._context_id, info)


class AsyncEntities:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/entities"

    async def list(self, *, type: str | None = None) -> list[Entity]:
        body = await self._t.get(self._base, params={"type": type})
        if isinstance(body, dict) and "entities" in body:
            body = body["entities"]
        if not isinstance(body, list):
            return []
        return [Entity.from_dict(e) for e in body]

    async def get(self, type: str, name: str) -> Entity:
        body = await self._t.get(f"{self._base}/{quote_path(type)}/{quote_path(name)}")
        return Entity.from_dict(body)

    async def history(
        self, type: str, name: str, key: str
    ) -> builtins.list[EntityHistoryEntry]:
        body = await self._t.get(
            f"{self._base}/{quote_path(type)}/{quote_path(name)}/history/{quote_path(key)}"
        )
        if isinstance(body, dict) and "history" in body:
            body = body["history"]
        if not isinstance(body, list):
            return []
        return [EntityHistoryEntry.from_dict(e) for e in body]

    async def delete(self, type: str, name: str) -> None:
        await self._t.delete(f"{self._base}/{quote_path(type)}/{quote_path(name)}")


class AsyncLifecycle:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/lifecycle"

    async def expire(self) -> None:
        await self._t.post(f"{self._base}/expire", json={})

    async def decay(self) -> None:
        await self._t.post(f"{self._base}/decay", json={})


class AsyncTraces:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/traces"

    async def list(self, *, limit: int | None = None) -> list[TraceRecord]:
        body = await self._t.get(self._base, params={"limit": limit})
        if isinstance(body, dict) and "traces" in body:
            return TraceListResponse.from_dict(body).traces
        if isinstance(body, list):
            return [TraceRecord.from_dict(t) for t in body]
        return []

    async def get(self, trace_id: str) -> TraceRecord:
        body = await self._t.get(f"{self._base}/{quote_path(trace_id)}")
        return TraceRecord.from_dict(body)

    async def stats(self) -> TraceStats:
        body = await self._t.get(f"{self._base}/stats")
        return TraceStats.from_dict(body)


class AsyncMemory:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._base = enduser_base(context_id)
        self.sessions = AsyncSessions(transport, context_id)
        self.entities = AsyncEntities(transport, context_id)
        self.lifecycle = AsyncLifecycle(transport, context_id)
        self.traces = AsyncTraces(transport, context_id)

    async def query(
        self,
        query: str,
        *,
        k: int | None = None,
        session_id: str | None = None,
    ) -> MemoryQueryResponse:
        payload: dict[str, Any] = {"query": query}
        if k is not None:
            payload["k"] = k
        if session_id is not None:
            payload["sessionId"] = session_id
        body = await self._t.post(f"{self._base}/query", json=payload)
        return MemoryQueryResponse.from_dict(body)

    async def context(self, query: str, *, k: int | None = None) -> ContextResult:
        body = await self._t.post(
            f"{self._base}/context", json=_context_payload(query, k)
        )
        return ContextResult.from_dict(body)

    async def state(self) -> StructuredState:
        body = await self._t.get(f"{self._base}/state")
        return StructuredState.from_dict(body)

    async def profile(self) -> ProfileResponse:
        body = await self._t.get(f"{self._base}/profile")
        return ProfileResponse.from_dict(body)

    async def reflect(self, query: str, *, persist: bool = False) -> ReflectionResult:
        payload: dict[str, Any] = {"query": query, "persist": persist}
        body = await self._t.post(f"{self._base}/reflect", json=payload)
        return ReflectionResult.from_dict(body)

    async def forget(self, query: str) -> ForgetResult:
        body = await self._t.post(f"{self._base}/forget", json={"query": query})
        if isinstance(body, int):
            return ForgetResult(deleted=body)
        return ForgetResult.from_dict(body)


__all__ = [
    "BlockingMemory",
    "BlockingSession",
    "BlockingSessions",
    "BlockingEntities",
    "BlockingLifecycle",
    "BlockingTraces",
    "AsyncMemory",
    "AsyncSession",
    "AsyncSessions",
    "AsyncEntities",
    "AsyncLifecycle",
    "AsyncTraces",
]
