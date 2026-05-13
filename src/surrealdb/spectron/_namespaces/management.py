from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from surrealdb.spectron._models import (
    ApiKeyInfoResponse,
    ContextConfig,
    ContextConfigView,
    ContextModels,
    ContextProviders,
    ContextResponse,
    CreateContextBody,
    CreatedApiKey,
    PrincipalType,
)
from surrealdb.spectron._namespaces._paths import management_base
from surrealdb.spectron._scope import serialise_scope
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    quote_path,
)


def _key_create_payload(
    *,
    principal: PrincipalType | str,
    scope_floor: Mapping[str, str] | None,
    expires_at: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "principal": principal.value if isinstance(principal, PrincipalType) else principal,
    }
    scope_payload = serialise_scope(scope_floor)
    if scope_payload is not None:
        payload["scopeFloor"] = scope_payload
    if expires_at is not None:
        payload["expiresAt"] = expires_at
    return payload


def _normalise_context_create_body(
    *,
    namespace: str,
    database: str,
    config: ContextConfig | Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"namespace": namespace, "database": database}
    if config is not None:
        payload["config"] = (
            config.to_dict() if isinstance(config, ContextConfig) else dict(config)
        )
    return payload


class BlockingContextKeys:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{management_base()}/{quote_path(context_id)}/keys"

    def list(self) -> list[ApiKeyInfoResponse]:
        body = self._t.get(self._base)
        if isinstance(body, dict) and "keys" in body:
            body = body["keys"]
        if not isinstance(body, list):
            return []
        return [ApiKeyInfoResponse.from_dict(k) for k in body]

    def create(
        self,
        name: str,
        *,
        principal: PrincipalType | str = PrincipalType.AGENT,
        scope_floor: Mapping[str, str] | None = None,
        expires_at: str | None = None,
    ) -> CreatedApiKey:
        payload = _key_create_payload(
            principal=principal,
            scope_floor=scope_floor,
            expires_at=expires_at,
        )
        body = self._t.post(f"{self._base}/{quote_path(name)}", json=payload)
        return CreatedApiKey.from_dict(body)

    def delete(self, name: str) -> None:
        self._t.delete(f"{self._base}/{quote_path(name)}")


class _BlockingContextHandle:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self.id = context_id
        self.keys = BlockingContextKeys(transport, context_id)


class BlockingContexts:
    def __init__(self, transport: BlockingTransport) -> None:
        self._t = transport
        self._base = management_base()

    def __call__(self, context_id: str) -> _BlockingContextHandle:
        return _BlockingContextHandle(self._t, context_id)

    def list(self) -> list[ContextResponse]:
        body = self._t.get(self._base)
        if isinstance(body, dict) and "contexts" in body:
            body = body["contexts"]
        if not isinstance(body, list):
            return []
        return [ContextResponse.from_dict(c) for c in body]

    def get(self, context_id: str) -> ContextResponse:
        body = self._t.get(f"{self._base}/{quote_path(context_id)}")
        return ContextResponse.from_dict(body)

    def create(
        self,
        context_id: str,
        *,
        namespace: str,
        database: str,
        config: ContextConfig | Mapping[str, Any] | None = None,
    ) -> ContextResponse:
        payload = _normalise_context_create_body(
            namespace=namespace, database=database, config=config
        )
        body = self._t.post(f"{self._base}/{quote_path(context_id)}", json=payload)
        return ContextResponse.from_dict(body)

    def update(
        self,
        context_id: str,
        *,
        config: ContextConfig | Mapping[str, Any],
    ) -> ContextResponse:
        payload: dict[str, Any] = {
            "config": config.to_dict() if isinstance(config, ContextConfig) else dict(config)
        }
        body = self._t.patch(f"{self._base}/{quote_path(context_id)}", json=payload)
        return ContextResponse.from_dict(body)

    def delete(self, context_id: str) -> None:
        self._t.delete(f"{self._base}/{quote_path(context_id)}")


class BlockingConfig:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._url = f"{management_base()}/{quote_path(context_id)}"

    def models(self, **fields: str | None) -> ContextConfigView:
        payload = {"config": {"models": {k: v for k, v in fields.items() if v is not None}}}
        body = self._t.patch(self._url, json=payload)
        return ContextResponse.from_dict(body).config

    def providers(self, **fields: str | None) -> ContextConfigView:
        payload = {"config": {"providers": {k: v for k, v in fields.items() if v is not None}}}
        body = self._t.patch(self._url, json=payload)
        return ContextResponse.from_dict(body).config

    def ontology(
        self,
        *,
        entity_types: list[str] | None = None,
        attribute_keys: Mapping[str, list[str]] | None = None,
        relation_labels: list[str] | None = None,
    ) -> ContextConfigView:
        ontology: dict[str, Any] = {}
        if entity_types is not None:
            ontology["entityTypes"] = list(entity_types)
        if attribute_keys is not None:
            ontology["attributeKeys"] = {k: list(v) for k, v in attribute_keys.items()}
        if relation_labels is not None:
            ontology["relationLabels"] = list(relation_labels)
        body = self._t.patch(self._url, json={"config": {"ontology": ontology}})
        return ContextResponse.from_dict(body).config


class AsyncContextKeys:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{management_base()}/{quote_path(context_id)}/keys"

    async def list(self) -> list[ApiKeyInfoResponse]:
        body = await self._t.get(self._base)
        if isinstance(body, dict) and "keys" in body:
            body = body["keys"]
        if not isinstance(body, list):
            return []
        return [ApiKeyInfoResponse.from_dict(k) for k in body]

    async def create(
        self,
        name: str,
        *,
        principal: PrincipalType | str = PrincipalType.AGENT,
        scope_floor: Mapping[str, str] | None = None,
        expires_at: str | None = None,
    ) -> CreatedApiKey:
        payload = _key_create_payload(
            principal=principal,
            scope_floor=scope_floor,
            expires_at=expires_at,
        )
        body = await self._t.post(f"{self._base}/{quote_path(name)}", json=payload)
        return CreatedApiKey.from_dict(body)

    async def delete(self, name: str) -> None:
        await self._t.delete(f"{self._base}/{quote_path(name)}")


class _AsyncContextHandle:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self.id = context_id
        self.keys = AsyncContextKeys(transport, context_id)


class AsyncContexts:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport
        self._base = management_base()

    def __call__(self, context_id: str) -> _AsyncContextHandle:
        return _AsyncContextHandle(self._t, context_id)

    async def list(self) -> list[ContextResponse]:
        body = await self._t.get(self._base)
        if isinstance(body, dict) and "contexts" in body:
            body = body["contexts"]
        if not isinstance(body, list):
            return []
        return [ContextResponse.from_dict(c) for c in body]

    async def get(self, context_id: str) -> ContextResponse:
        body = await self._t.get(f"{self._base}/{quote_path(context_id)}")
        return ContextResponse.from_dict(body)

    async def create(
        self,
        context_id: str,
        *,
        namespace: str,
        database: str,
        config: ContextConfig | Mapping[str, Any] | None = None,
    ) -> ContextResponse:
        payload = _normalise_context_create_body(
            namespace=namespace, database=database, config=config
        )
        body = await self._t.post(f"{self._base}/{quote_path(context_id)}", json=payload)
        return ContextResponse.from_dict(body)

    async def update(
        self,
        context_id: str,
        *,
        config: ContextConfig | Mapping[str, Any],
    ) -> ContextResponse:
        payload: dict[str, Any] = {
            "config": config.to_dict() if isinstance(config, ContextConfig) else dict(config)
        }
        body = await self._t.patch(f"{self._base}/{quote_path(context_id)}", json=payload)
        return ContextResponse.from_dict(body)

    async def delete(self, context_id: str) -> None:
        await self._t.delete(f"{self._base}/{quote_path(context_id)}")


class AsyncConfig:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._url = f"{management_base()}/{quote_path(context_id)}"

    async def models(self, **fields: str | None) -> ContextConfigView:
        payload = {"config": {"models": {k: v for k, v in fields.items() if v is not None}}}
        body = await self._t.patch(self._url, json=payload)
        return ContextResponse.from_dict(body).config

    async def providers(self, **fields: str | None) -> ContextConfigView:
        payload = {"config": {"providers": {k: v for k, v in fields.items() if v is not None}}}
        body = await self._t.patch(self._url, json=payload)
        return ContextResponse.from_dict(body).config

    async def ontology(
        self,
        *,
        entity_types: list[str] | None = None,
        attribute_keys: Mapping[str, list[str]] | None = None,
        relation_labels: list[str] | None = None,
    ) -> ContextConfigView:
        ontology: dict[str, Any] = {}
        if entity_types is not None:
            ontology["entityTypes"] = list(entity_types)
        if attribute_keys is not None:
            ontology["attributeKeys"] = {k: list(v) for k, v in attribute_keys.items()}
        if relation_labels is not None:
            ontology["relationLabels"] = list(relation_labels)
        body = await self._t.patch(self._url, json={"config": {"ontology": ontology}})
        return ContextResponse.from_dict(body).config


__all__ = [
    "BlockingContexts",
    "BlockingContextKeys",
    "BlockingConfig",
    "AsyncContexts",
    "AsyncContextKeys",
    "AsyncConfig",
]
