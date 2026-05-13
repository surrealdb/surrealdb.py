from __future__ import annotations

from typing import Any

from surrealdb.spectron._namespaces.knowledge import AsyncKnowledge, BlockingKnowledge
from surrealdb.spectron._namespaces.management import (
    AsyncConfig,
    AsyncContexts,
    BlockingConfig,
    BlockingContexts,
)
from surrealdb.spectron._namespaces.memory import AsyncMemory, BlockingMemory
from surrealdb.spectron._transport import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    AsyncTransport,
    BlockingTransport,
)


class Spectron:
    def __init__(
        self,
        context: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: BlockingTransport | None = None,
    ) -> None:
        self._context_id = context
        self._transport = transport or BlockingTransport(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._owns_transport = transport is None
        memory = BlockingMemory(self._transport, context)
        self._memory = memory
        self.knowledge = BlockingKnowledge(self._transport, context)
        self.sessions = memory.sessions
        self.entities = memory.entities
        self.lifecycle = memory.lifecycle
        self.traces = memory.traces
        self.config = BlockingConfig(self._transport, context)

    @property
    def context_id(self) -> str:
        return self._context_id

    @property
    def memory(self) -> BlockingMemory:
        return self._memory

    def query(self, *args: Any, **kw: Any) -> Any:
        return self._memory.query(*args, **kw)

    def context(self, *args: Any, **kw: Any) -> Any:
        return self._memory.context(*args, **kw)

    def state(self) -> Any:
        return self._memory.state()

    def profile(self) -> Any:
        return self._memory.profile()

    def reflect(self, *args: Any, **kw: Any) -> Any:
        return self._memory.reflect(*args, **kw)

    def forget(self, *args: Any, **kw: Any) -> Any:
        return self._memory.forget(*args, **kw)

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
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: AsyncTransport | None = None,
    ) -> None:
        self._context_id = context
        self._transport = transport or AsyncTransport(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._owns_transport = transport is None
        memory = AsyncMemory(self._transport, context)
        self._memory = memory
        self.knowledge = AsyncKnowledge(self._transport, context)
        self.sessions = memory.sessions
        self.entities = memory.entities
        self.lifecycle = memory.lifecycle
        self.traces = memory.traces
        self.config = AsyncConfig(self._transport, context)

    @property
    def context_id(self) -> str:
        return self._context_id

    @property
    def memory(self) -> AsyncMemory:
        return self._memory

    async def query(self, *args: Any, **kw: Any) -> Any:
        return await self._memory.query(*args, **kw)

    async def context(self, *args: Any, **kw: Any) -> Any:
        return await self._memory.context(*args, **kw)

    async def state(self) -> Any:
        return await self._memory.state()

    async def profile(self) -> Any:
        return await self._memory.profile()

    async def reflect(self, *args: Any, **kw: Any) -> Any:
        return await self._memory.reflect(*args, **kw)

    async def forget(self, *args: Any, **kw: Any) -> Any:
        return await self._memory.forget(*args, **kw)

    async def close(self) -> None:
        if self._owns_transport:
            await self._transport.close()

    async def __aenter__(self) -> AsyncSpectron:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()


class SpectronManagement:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: BlockingTransport | None = None,
    ) -> None:
        self._transport = transport or BlockingTransport(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._owns_transport = transport is None
        self.contexts = BlockingContexts(self._transport)

    def close(self) -> None:
        if self._owns_transport:
            self._transport.close()

    def __enter__(self) -> SpectronManagement:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


class AsyncSpectronManagement:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: AsyncTransport | None = None,
    ) -> None:
        self._transport = transport or AsyncTransport(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._owns_transport = transport is None
        self.contexts = AsyncContexts(self._transport)

    async def close(self) -> None:
        if self._owns_transport:
            await self._transport.close()

    async def __aenter__(self) -> AsyncSpectronManagement:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()


__all__ = ["Spectron", "AsyncSpectron", "SpectronManagement", "AsyncSpectronManagement"]
