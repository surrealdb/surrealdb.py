from __future__ import annotations

import builtins
import io
from collections.abc import Iterable, Mapping
from typing import Any

from surrealdb.spectron._models import (
    ChunkPageJson,
    DocumentJson,
    DocumentKeywordJson,
    DocumentKeywordsResponse,
    DocumentPageJson,
    KeywordDetailJson,
    KeywordPageJson,
    KeywordSearchResponseJson,
    KnowledgeLinkUpsert,
    KnowledgeNodeFullJson,
    KnowledgeNodePageJson,
    KnowledgeNodeSearchResponseJson,
    KnowledgeNodeUpsertRow,
    QueryFilter,
    QueryMode,
    QueryResponseJson,
    TraverseApiResponse,
    TraverseStartJson,
    UploadResponse,
)
from surrealdb.spectron._namespaces._paths import enduser_base
from surrealdb.spectron._scope import serialise_scope
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    build_aiohttp_form,
    build_multipart_payload,
    quote_path,
)


def _query_request_payload(
    *,
    query: str,
    mode: QueryMode | str | None,
    k: int | None,
    threshold: float | None,
    vector_weight: float | None,
    rrf_k: float | None,
    graph_alpha: float | None,
    graph_edges: list[str] | None,
    graph_depth: int | None,
    expand_graph: bool | None,
    filter: QueryFilter | Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": query}
    if mode is not None:
        payload["mode"] = mode.value if isinstance(mode, QueryMode) else mode
    if k is not None:
        payload["k"] = k
    if threshold is not None:
        payload["threshold"] = threshold
    if vector_weight is not None:
        payload["vectorWeight"] = vector_weight
    if rrf_k is not None:
        payload["rrfK"] = rrf_k
    if graph_alpha is not None:
        payload["graphAlpha"] = graph_alpha
    if graph_edges is not None:
        payload["graphEdges"] = list(graph_edges)
    if graph_depth is not None:
        payload["graphDepth"] = graph_depth
    if expand_graph is not None:
        payload["expandGraph"] = expand_graph
    if filter is not None:
        payload["filter"] = (
            filter.to_dict() if isinstance(filter, QueryFilter) else dict(filter)
        )
    return payload


def _traverse_request_payload(
    *,
    start: list[TraverseStartJson | Mapping[str, Any]],
    edges: list[str],
    direction: str | None,
    labels: list[str] | None,
    max_depth: int | None,
    limit_per_hop: int | None,
    min_score: float | None,
) -> dict[str, Any]:
    encoded_start: list[dict[str, Any]] = []
    for item in start:
        if isinstance(item, TraverseStartJson):
            encoded_start.append(item.to_dict())
        else:
            encoded_start.append(dict(item))
    payload: dict[str, Any] = {"start": encoded_start, "edges": list(edges)}
    if direction is not None:
        payload["direction"] = direction
    if labels is not None:
        payload["labels"] = list(labels)
    if max_depth is not None:
        payload["maxDepth"] = max_depth
    if limit_per_hop is not None:
        payload["limitPerHop"] = limit_per_hop
    if min_score is not None:
        payload["minScore"] = min_score
    return payload


def _upload_fields(
    *,
    title: str | None,
    profile: str | None,
    scope: Mapping[str, str] | None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if title is not None:
        fields["title"] = title
    if profile is not None:
        fields["profile"] = profile
    serialised = serialise_scope(scope)
    if serialised is not None:
        fields["scope"] = serialised
    return fields


class _BlockingKeywords:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/knowledge/keywords"

    def list(
        self,
        *,
        q: str | None = None,
        min_document_count: int | None = None,
        sort: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> KeywordPageJson:
        params = {
            "q": q,
            "minDocumentCount": min_document_count,
            "sort": sort,
            "page": page,
            "pageSize": page_size,
        }
        body = self._t.get(self._base, params=params)
        return KeywordPageJson.from_dict(body)

    def search(
        self, query: str, *, k: int | None = None, threshold: float | None = None
    ) -> KeywordSearchResponseJson:
        payload: dict[str, Any] = {"query": query}
        if k is not None:
            payload["k"] = k
        if threshold is not None:
            payload["threshold"] = threshold
        body = self._t.post(f"{self._base}/search", json=payload)
        return KeywordSearchResponseJson.from_dict(body)

    def get(self, normalised: str) -> KeywordDetailJson:
        body = self._t.get(f"{self._base}/{quote_path(normalised)}")
        return KeywordDetailJson.from_dict(body)

    def related(self, normalised: str) -> TraverseApiResponse:
        body = self._t.get(f"{self._base}/{quote_path(normalised)}/related")
        return TraverseApiResponse.from_dict(body)

    def for_document(self, document_id: str) -> builtins.list[DocumentKeywordJson]:
        base = self._base.rsplit("/keywords", 1)[0]
        body = self._t.get(f"{base}/{quote_path(document_id)}/keywords")
        return DocumentKeywordsResponse.from_dict(body).keywords


class _BlockingNodes:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/knowledge/nodes"

    def list(
        self,
        *,
        kind: str | None = None,
        q: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> KnowledgeNodePageJson:
        params = {"kind": kind, "q": q, "page": page, "pageSize": page_size}
        body = self._t.get(self._base, params=params)
        return KnowledgeNodePageJson.from_dict(body)

    def upsert(
        self,
        *,
        nodes: Iterable[KnowledgeNodeUpsertRow | Mapping[str, Any]],
        relations: Iterable[KnowledgeLinkUpsert | Mapping[str, Any]] | None = None,
        scope: Mapping[str, str] | None = None,
    ) -> None:
        encoded_nodes: list[dict[str, Any]] = []
        for n in nodes:
            encoded_nodes.append(
                n.to_dict() if isinstance(n, KnowledgeNodeUpsertRow) else dict(n)
            )
        payload: dict[str, Any] = {"nodes": encoded_nodes}
        if relations is not None:
            encoded_relations: list[dict[str, Any]] = []
            for r in relations:
                encoded_relations.append(
                    r.to_dict() if isinstance(r, KnowledgeLinkUpsert) else dict(r)
                )
            payload["relations"] = encoded_relations
        scope_payload = serialise_scope(scope)
        if scope_payload is not None:
            payload["scope"] = scope_payload
        self._t.post(f"{self._base}/batch", json=payload)

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        threshold: float = 0.0,
        rrf_k: int | None = None,
        vector_weight: float | None = None,
        kind_filter: str | None = None,
    ) -> KnowledgeNodeSearchResponseJson:
        payload: dict[str, Any] = {"query": query, "k": k, "threshold": threshold}
        if rrf_k is not None:
            payload["rrfK"] = rrf_k
        if vector_weight is not None:
            payload["vectorWeight"] = vector_weight
        if kind_filter is not None:
            payload["kindFilter"] = kind_filter
        body = self._t.post(f"{self._base}/search", json=payload)
        return KnowledgeNodeSearchResponseJson.from_dict(body)

    def get(self, kind: str, slug: str) -> KnowledgeNodeFullJson:
        body = self._t.get(f"{self._base}/{quote_path(kind)}/{quote_path(slug)}")
        return KnowledgeNodeFullJson.from_dict(body)

    def related(
        self,
        kind: str,
        slug: str,
        *,
        label: str | None = None,
        depth: int | None = None,
    ) -> TraverseApiResponse:
        params = {"label": label, "depth": depth}
        body = self._t.get(
            f"{self._base}/{quote_path(kind)}/{quote_path(slug)}/related",
            params=params,
        )
        return TraverseApiResponse.from_dict(body)

    def delete(self, kind: str, slug: str) -> None:
        self._t.delete(f"{self._base}/{quote_path(kind)}/{quote_path(slug)}")


class _BlockingTraverse:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/knowledge/traverse"

    def __call__(
        self,
        *,
        start: list[TraverseStartJson | Mapping[str, Any]],
        edges: list[str],
        direction: str | None = None,
        labels: list[str] | None = None,
        max_depth: int | None = None,
        limit_per_hop: int | None = None,
        min_score: float | None = None,
    ) -> TraverseApiResponse:
        payload = _traverse_request_payload(
            start=start,
            edges=edges,
            direction=direction,
            labels=labels,
            max_depth=max_depth,
            limit_per_hop=limit_per_hop,
            min_score=min_score,
        )
        body = self._t.post(self._base, json=payload)
        return TraverseApiResponse.from_dict(body)

    def recursive(
        self,
        *,
        start: TraverseStartJson | Mapping[str, Any],
        edge: str,
        max_depth: int = 3,
        direction: str | None = None,
    ) -> TraverseApiResponse:
        payload: dict[str, Any] = {
            "start": start.to_dict()
            if isinstance(start, TraverseStartJson)
            else dict(start),
            "edge": edge,
            "maxDepth": max_depth,
        }
        if direction is not None:
            payload["direction"] = direction
        body = self._t.post(f"{self._base}/recursive", json=payload)
        return TraverseApiResponse.from_dict(body)

    def siblings(
        self,
        *,
        start: TraverseStartJson | Mapping[str, Any],
        edge: str,
    ) -> TraverseApiResponse:
        payload: dict[str, Any] = {
            "start": start.to_dict()
            if isinstance(start, TraverseStartJson)
            else dict(start),
            "edge": edge,
        }
        body = self._t.post(f"{self._base}/siblings", json=payload)
        return TraverseApiResponse.from_dict(body)


class BlockingKnowledge:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._base = f"{enduser_base(context_id)}/knowledge"
        self.keywords = _BlockingKeywords(transport, context_id)
        self.nodes = _BlockingNodes(transport, context_id)
        self._traverse_helper = _BlockingTraverse(transport, context_id)

    def upload(
        self,
        file: bytes | bytearray | memoryview | io.IOBase | str,
        *,
        title: str | None = None,
        profile: str | None = None,
        scope: Mapping[str, str] | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> UploadResponse:
        files, data = build_multipart_payload(
            file=file,
            filename=filename,
            mime_type=mime_type,
            fields=_upload_fields(title=title, profile=profile, scope=scope),
        )
        body = self._t.post(self._base, files=files, data=data)
        return UploadResponse.from_dict(body)

    def replace(
        self,
        document_id: str,
        file: bytes | bytearray | memoryview | io.IOBase | str,
        *,
        title: str | None = None,
        profile: str | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> UploadResponse:
        files, data = build_multipart_payload(
            file=file,
            filename=filename,
            mime_type=mime_type,
            fields=_upload_fields(title=title, profile=profile, scope=None),
        )
        body = self._t.put(
            f"{self._base}/{quote_path(document_id)}",
            files=files,
            data=data,
        )
        return (
            UploadResponse.from_dict(body)
            if body
            else UploadResponse(
                content_hash="", deduplicated=False, id=document_id, status="queued"
            )
        )

    def get(self, document_id: str) -> DocumentJson:
        body = self._t.get(f"{self._base}/{quote_path(document_id)}")
        return DocumentJson.from_dict(body)

    def raw(self, document_id: str) -> bytes:
        chunks = list(
            self._t.stream_bytes(f"{self._base}/{quote_path(document_id)}/raw")
        )
        return b"".join(chunks)

    def chunks(
        self,
        document_id: str,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> ChunkPageJson:
        params = {"page": page, "page_size": page_size}
        body = self._t.get(
            f"{self._base}/{quote_path(document_id)}/chunks",
            params=params,
        )
        return ChunkPageJson.from_dict(body)

    def list(
        self,
        *,
        status: str | None = None,
        mime_type: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> DocumentPageJson:
        params = {
            "status": status,
            "mime_type": mime_type,
            "page": page,
            "page_size": page_size,
        }
        body = self._t.get(self._base, params=params)
        return DocumentPageJson.from_dict(body)

    def related(self, document_id: str) -> TraverseApiResponse:
        body = self._t.get(f"{self._base}/{quote_path(document_id)}/related")
        return TraverseApiResponse.from_dict(body)

    def delete(self, document_id: str) -> None:
        self._t.delete(f"{self._base}/{quote_path(document_id)}")

    def query(
        self,
        query: str,
        *,
        mode: QueryMode | str | None = None,
        k: int | None = None,
        threshold: float | None = None,
        vector_weight: float | None = None,
        rrf_k: float | None = None,
        graph_alpha: float | None = None,
        graph_edges: builtins.list[str] | None = None,
        graph_depth: int | None = None,
        expand_graph: bool | None = None,
        filter: QueryFilter | Mapping[str, Any] | None = None,
    ) -> QueryResponseJson:
        payload = _query_request_payload(
            query=query,
            mode=mode,
            k=k,
            threshold=threshold,
            vector_weight=vector_weight,
            rrf_k=rrf_k,
            graph_alpha=graph_alpha,
            graph_edges=graph_edges,
            graph_depth=graph_depth,
            expand_graph=expand_graph,
            filter=filter,
        )
        body = self._t.post(f"{self._base}/query", json=payload)
        return QueryResponseJson.from_dict(body)

    def traverse(self, **kw: Any) -> TraverseApiResponse:
        return self._traverse_helper(**kw)

    def traverse_recursive(self, **kw: Any) -> TraverseApiResponse:
        return self._traverse_helper.recursive(**kw)

    def traverse_siblings(self, **kw: Any) -> TraverseApiResponse:
        return self._traverse_helper.siblings(**kw)


class _AsyncKeywords:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/knowledge/keywords"

    async def list(
        self,
        *,
        q: str | None = None,
        min_document_count: int | None = None,
        sort: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> KeywordPageJson:
        params = {
            "q": q,
            "minDocumentCount": min_document_count,
            "sort": sort,
            "page": page,
            "pageSize": page_size,
        }
        body = await self._t.get(self._base, params=params)
        return KeywordPageJson.from_dict(body)

    async def search(
        self, query: str, *, k: int | None = None, threshold: float | None = None
    ) -> KeywordSearchResponseJson:
        payload: dict[str, Any] = {"query": query}
        if k is not None:
            payload["k"] = k
        if threshold is not None:
            payload["threshold"] = threshold
        body = await self._t.post(f"{self._base}/search", json=payload)
        return KeywordSearchResponseJson.from_dict(body)

    async def get(self, normalised: str) -> KeywordDetailJson:
        body = await self._t.get(f"{self._base}/{quote_path(normalised)}")
        return KeywordDetailJson.from_dict(body)

    async def related(self, normalised: str) -> TraverseApiResponse:
        body = await self._t.get(f"{self._base}/{quote_path(normalised)}/related")
        return TraverseApiResponse.from_dict(body)

    async def for_document(
        self, document_id: str
    ) -> builtins.list[DocumentKeywordJson]:
        base = self._base.rsplit("/keywords", 1)[0]
        body = await self._t.get(f"{base}/{quote_path(document_id)}/keywords")
        return DocumentKeywordsResponse.from_dict(body).keywords


class _AsyncNodes:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/knowledge/nodes"

    async def list(
        self,
        *,
        kind: str | None = None,
        q: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> KnowledgeNodePageJson:
        params = {"kind": kind, "q": q, "page": page, "pageSize": page_size}
        body = await self._t.get(self._base, params=params)
        return KnowledgeNodePageJson.from_dict(body)

    async def upsert(
        self,
        *,
        nodes: Iterable[KnowledgeNodeUpsertRow | Mapping[str, Any]],
        relations: Iterable[KnowledgeLinkUpsert | Mapping[str, Any]] | None = None,
        scope: Mapping[str, str] | None = None,
    ) -> None:
        encoded_nodes: list[dict[str, Any]] = []
        for n in nodes:
            encoded_nodes.append(
                n.to_dict() if isinstance(n, KnowledgeNodeUpsertRow) else dict(n)
            )
        payload: dict[str, Any] = {"nodes": encoded_nodes}
        if relations is not None:
            encoded_relations: list[dict[str, Any]] = []
            for r in relations:
                encoded_relations.append(
                    r.to_dict() if isinstance(r, KnowledgeLinkUpsert) else dict(r)
                )
            payload["relations"] = encoded_relations
        scope_payload = serialise_scope(scope)
        if scope_payload is not None:
            payload["scope"] = scope_payload
        await self._t.post(f"{self._base}/batch", json=payload)

    async def search(
        self,
        query: str,
        *,
        k: int = 10,
        threshold: float = 0.0,
        rrf_k: int | None = None,
        vector_weight: float | None = None,
        kind_filter: str | None = None,
    ) -> KnowledgeNodeSearchResponseJson:
        payload: dict[str, Any] = {"query": query, "k": k, "threshold": threshold}
        if rrf_k is not None:
            payload["rrfK"] = rrf_k
        if vector_weight is not None:
            payload["vectorWeight"] = vector_weight
        if kind_filter is not None:
            payload["kindFilter"] = kind_filter
        body = await self._t.post(f"{self._base}/search", json=payload)
        return KnowledgeNodeSearchResponseJson.from_dict(body)

    async def get(self, kind: str, slug: str) -> KnowledgeNodeFullJson:
        body = await self._t.get(f"{self._base}/{quote_path(kind)}/{quote_path(slug)}")
        return KnowledgeNodeFullJson.from_dict(body)

    async def related(
        self,
        kind: str,
        slug: str,
        *,
        label: str | None = None,
        depth: int | None = None,
    ) -> TraverseApiResponse:
        params = {"label": label, "depth": depth}
        body = await self._t.get(
            f"{self._base}/{quote_path(kind)}/{quote_path(slug)}/related",
            params=params,
        )
        return TraverseApiResponse.from_dict(body)

    async def delete(self, kind: str, slug: str) -> None:
        await self._t.delete(f"{self._base}/{quote_path(kind)}/{quote_path(slug)}")


class _AsyncTraverse:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._base = f"{enduser_base(context_id)}/knowledge/traverse"

    async def __call__(
        self,
        *,
        start: list[TraverseStartJson | Mapping[str, Any]],
        edges: list[str],
        direction: str | None = None,
        labels: list[str] | None = None,
        max_depth: int | None = None,
        limit_per_hop: int | None = None,
        min_score: float | None = None,
    ) -> TraverseApiResponse:
        payload = _traverse_request_payload(
            start=start,
            edges=edges,
            direction=direction,
            labels=labels,
            max_depth=max_depth,
            limit_per_hop=limit_per_hop,
            min_score=min_score,
        )
        body = await self._t.post(self._base, json=payload)
        return TraverseApiResponse.from_dict(body)

    async def recursive(
        self,
        *,
        start: TraverseStartJson | Mapping[str, Any],
        edge: str,
        max_depth: int = 3,
        direction: str | None = None,
    ) -> TraverseApiResponse:
        payload: dict[str, Any] = {
            "start": start.to_dict()
            if isinstance(start, TraverseStartJson)
            else dict(start),
            "edge": edge,
            "maxDepth": max_depth,
        }
        if direction is not None:
            payload["direction"] = direction
        body = await self._t.post(f"{self._base}/recursive", json=payload)
        return TraverseApiResponse.from_dict(body)

    async def siblings(
        self,
        *,
        start: TraverseStartJson | Mapping[str, Any],
        edge: str,
    ) -> TraverseApiResponse:
        payload: dict[str, Any] = {
            "start": start.to_dict()
            if isinstance(start, TraverseStartJson)
            else dict(start),
            "edge": edge,
        }
        body = await self._t.post(f"{self._base}/siblings", json=payload)
        return TraverseApiResponse.from_dict(body)


class AsyncKnowledge:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._t = transport
        self._context_id = context_id
        self._base = f"{enduser_base(context_id)}/knowledge"
        self.keywords = _AsyncKeywords(transport, context_id)
        self.nodes = _AsyncNodes(transport, context_id)
        self._traverse_helper = _AsyncTraverse(transport, context_id)

    async def upload(
        self,
        file: bytes | bytearray | memoryview | io.IOBase | str,
        *,
        title: str | None = None,
        profile: str | None = None,
        scope: Mapping[str, str] | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> UploadResponse:
        form = build_aiohttp_form(
            file=file,
            filename=filename,
            mime_type=mime_type,
            fields=_upload_fields(title=title, profile=profile, scope=scope),
        )
        body = await self._t.post(self._base, data=form)
        return UploadResponse.from_dict(body)

    async def replace(
        self,
        document_id: str,
        file: bytes | bytearray | memoryview | io.IOBase | str,
        *,
        title: str | None = None,
        profile: str | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> UploadResponse:
        form = build_aiohttp_form(
            file=file,
            filename=filename,
            mime_type=mime_type,
            fields=_upload_fields(title=title, profile=profile, scope=None),
        )
        body = await self._t.put(f"{self._base}/{quote_path(document_id)}", data=form)
        return (
            UploadResponse.from_dict(body)
            if body
            else UploadResponse(
                content_hash="", deduplicated=False, id=document_id, status="queued"
            )
        )

    async def get(self, document_id: str) -> DocumentJson:
        body = await self._t.get(f"{self._base}/{quote_path(document_id)}")
        return DocumentJson.from_dict(body)

    async def raw(self, document_id: str) -> bytes:
        response = await self._t.request(
            "GET",
            f"{self._base}/{quote_path(document_id)}/raw",
            return_raw=True,
        )
        try:
            data = await response.read()
        finally:
            response.release()
        return data

    async def chunks(
        self,
        document_id: str,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> ChunkPageJson:
        params = {"page": page, "page_size": page_size}
        body = await self._t.get(
            f"{self._base}/{quote_path(document_id)}/chunks",
            params=params,
        )
        return ChunkPageJson.from_dict(body)

    async def list(
        self,
        *,
        status: str | None = None,
        mime_type: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> DocumentPageJson:
        params = {
            "status": status,
            "mime_type": mime_type,
            "page": page,
            "page_size": page_size,
        }
        body = await self._t.get(self._base, params=params)
        return DocumentPageJson.from_dict(body)

    async def related(self, document_id: str) -> TraverseApiResponse:
        body = await self._t.get(f"{self._base}/{quote_path(document_id)}/related")
        return TraverseApiResponse.from_dict(body)

    async def delete(self, document_id: str) -> None:
        await self._t.delete(f"{self._base}/{quote_path(document_id)}")

    async def query(
        self,
        query: str,
        *,
        mode: QueryMode | str | None = None,
        k: int | None = None,
        threshold: float | None = None,
        vector_weight: float | None = None,
        rrf_k: float | None = None,
        graph_alpha: float | None = None,
        graph_edges: builtins.list[str] | None = None,
        graph_depth: int | None = None,
        expand_graph: bool | None = None,
        filter: QueryFilter | Mapping[str, Any] | None = None,
    ) -> QueryResponseJson:
        payload = _query_request_payload(
            query=query,
            mode=mode,
            k=k,
            threshold=threshold,
            vector_weight=vector_weight,
            rrf_k=rrf_k,
            graph_alpha=graph_alpha,
            graph_edges=graph_edges,
            graph_depth=graph_depth,
            expand_graph=expand_graph,
            filter=filter,
        )
        body = await self._t.post(f"{self._base}/query", json=payload)
        return QueryResponseJson.from_dict(body)

    async def traverse(self, **kw: Any) -> TraverseApiResponse:
        return await self._traverse_helper(**kw)

    async def traverse_recursive(self, **kw: Any) -> TraverseApiResponse:
        return await self._traverse_helper.recursive(**kw)

    async def traverse_siblings(self, **kw: Any) -> TraverseApiResponse:
        return await self._traverse_helper.siblings(**kw)


__all__ = ["BlockingKnowledge", "AsyncKnowledge"]
