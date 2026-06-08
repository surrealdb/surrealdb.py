from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any

from surrealdb.spectron._models import (
    ChunkPage,
    Document,
    DocumentKeywordsResponse,
    DocumentPage,
    DocumentQueryResponse,
    KeywordDetail,
    KeywordPage,
    KeywordSearchResponse,
    RecomputeLinksResponse,
    UploadResponse,
)
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    build_aiohttp_form,
    build_multipart_payload,
    on_behalf_of_header,
    quote_path,
)
from surrealdb.spectron._util import drop_none


def _resolve_file(
    path: str | os.PathLike[str] | IO[bytes] | bytes | bytearray | memoryview,
    filename: str | None,
) -> tuple[Any, str | None]:
    if isinstance(path, (bytes, bytearray, memoryview)):
        return path, filename
    if isinstance(path, (str, os.PathLike)):
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(p)
        return str(p), filename or p.name
    # File-like object
    return path, filename


def _metadata_fields(title: str | None, source: str | None) -> dict[str, Any]:
    """Build the `metadata` multipart part the upload handler reads.

    Only `title` and `source` are surfaced here; the file's MIME type rides on
    the `file` part's Content-Type, which the server prefers when the metadata
    part omits `mime_type`.
    """
    metadata = {k: v for k, v in (("title", title), ("source", source)) if v}
    return {"metadata": metadata} if metadata else {}


def _query_body(
    query: str,
    *,
    k: int | None,
    mode: str | None,
    threshold: float | None,
    expand_graph: bool | None,
    filter: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return drop_none(
        {
            "query": query,
            "k": k,
            "mode": mode,
            "threshold": threshold,
            "expandGraph": expand_graph,
            "filter": dict(filter) if filter is not None else None,
        }
    )


def _docs_base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/documents"


class BlockingDocumentKeywords:
    """Corpus-level keyword index for a context's documents."""

    def __init__(self, transport: BlockingTransport, docs_base: str) -> None:
        self._transport = transport
        self._base = f"{docs_base}/keywords"
        self._docs_base = docs_base

    def list(
        self,
        *,
        q: str | None = None,
        min_document_count: int | None = None,
        sort: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        on_behalf_of: str | None = None,
    ) -> KeywordPage:
        params = {
            "q": q,
            "minDocumentCount": min_document_count,
            "sort": sort,
            "page": page,
            "page_size": page_size,
        }
        result = self._transport.request(
            "GET",
            self._base,
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return KeywordPage.from_dict(result)

    def get(self, normalised: str, *, on_behalf_of: str | None = None) -> KeywordDetail:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(normalised)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return KeywordDetail.from_dict(result)

    def search(
        self,
        query: str,
        *,
        k: int | None = None,
        threshold: float | None = None,
        on_behalf_of: str | None = None,
    ) -> KeywordSearchResponse:
        payload = drop_none({"query": query, "k": k, "threshold": threshold})
        result = self._transport.request(
            "POST",
            f"{self._base}/search",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return KeywordSearchResponse.from_dict(result)

    def for_document(
        self, doc_id: str, *, on_behalf_of: str | None = None
    ) -> DocumentKeywordsResponse:
        result = self._transport.request(
            "GET",
            f"{self._docs_base}/{quote_path(doc_id)}/keywords",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return DocumentKeywordsResponse.from_dict(result)


class BlockingDocuments:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._context_id = context_id
        self._base = _docs_base(context_id)
        self.keywords = BlockingDocumentKeywords(transport, self._base)

    def upload(
        self,
        path: str | os.PathLike[str] | IO[bytes] | bytes | bytearray | memoryview,
        *,
        content_type: str | None = None,
        filename: str | None = None,
        title: str | None = None,
        source: str | None = None,
        on_behalf_of: str | None = None,
    ) -> UploadResponse:
        file_payload, resolved_filename = _resolve_file(path, filename)
        files, data = build_multipart_payload(
            file=file_payload,
            filename=resolved_filename,
            mime_type=content_type,
            fields=_metadata_fields(title, source),
        )
        result = self._transport.request(
            "POST",
            self._base,
            files=files,
            data=data or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return UploadResponse.from_dict(result)

    def get(self, doc_id: str, *, on_behalf_of: str | None = None) -> Document:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(doc_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Document.from_dict(result)

    def delete(self, doc_id: str, *, on_behalf_of: str | None = None) -> None:
        self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(doc_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    def list(
        self,
        *,
        status: str | None = None,
        mime_type: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        on_behalf_of: str | None = None,
    ) -> DocumentPage:
        params = {
            "status": status,
            "mime_type": mime_type,
            "page": page,
            "page_size": page_size,
        }
        result = self._transport.request(
            "GET",
            self._base,
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return DocumentPage.from_dict(result)

    def query(
        self,
        query: str,
        *,
        k: int | None = None,
        mode: str | None = None,
        threshold: float | None = None,
        expand_graph: bool | None = None,
        filter: Mapping[str, Any] | None = None,
        on_behalf_of: str | None = None,
    ) -> DocumentQueryResponse:
        payload = _query_body(
            query,
            k=k,
            mode=mode,
            threshold=threshold,
            expand_graph=expand_graph,
            filter=filter,
        )
        result = self._transport.request(
            "POST",
            f"{self._base}/query",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return DocumentQueryResponse.from_dict(result)

    def fetch_raw(self, doc_id: str, *, on_behalf_of: str | None = None) -> bytes:
        response = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(doc_id)}/raw",
            return_raw=True,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return response.content

    def reprocess(
        self, doc_id: str, *, on_behalf_of: str | None = None
    ) -> UploadResponse:
        result = self._transport.request(
            "PUT",
            f"{self._base}/{quote_path(doc_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return UploadResponse.from_dict(result)

    def recompute_links(
        self, *, on_behalf_of: str | None = None
    ) -> RecomputeLinksResponse:
        result = self._transport.request(
            "POST",
            f"{self._base}/recompute-links",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return RecomputeLinksResponse.from_dict(result)

    def chunks(
        self,
        doc_id: str,
        *,
        page: int | None = None,
        page_size: int | None = None,
        on_behalf_of: str | None = None,
    ) -> ChunkPage:
        result = self._transport.request(
            "GET",
            f"{self._base}/{quote_path(doc_id)}/chunks",
            params={"page": page, "page_size": page_size},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ChunkPage.from_dict(result)


class AsyncDocumentKeywords:
    """Corpus-level keyword index for a context's documents (async)."""

    def __init__(self, transport: AsyncTransport, docs_base: str) -> None:
        self._transport = transport
        self._base = f"{docs_base}/keywords"
        self._docs_base = docs_base

    async def list(
        self,
        *,
        q: str | None = None,
        min_document_count: int | None = None,
        sort: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        on_behalf_of: str | None = None,
    ) -> KeywordPage:
        params = {
            "q": q,
            "minDocumentCount": min_document_count,
            "sort": sort,
            "page": page,
            "page_size": page_size,
        }
        result = await self._transport.request(
            "GET",
            self._base,
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return KeywordPage.from_dict(result)

    async def get(
        self, normalised: str, *, on_behalf_of: str | None = None
    ) -> KeywordDetail:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(normalised)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return KeywordDetail.from_dict(result)

    async def search(
        self,
        query: str,
        *,
        k: int | None = None,
        threshold: float | None = None,
        on_behalf_of: str | None = None,
    ) -> KeywordSearchResponse:
        payload = drop_none({"query": query, "k": k, "threshold": threshold})
        result = await self._transport.request(
            "POST",
            f"{self._base}/search",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return KeywordSearchResponse.from_dict(result)

    async def for_document(
        self, doc_id: str, *, on_behalf_of: str | None = None
    ) -> DocumentKeywordsResponse:
        result = await self._transport.request(
            "GET",
            f"{self._docs_base}/{quote_path(doc_id)}/keywords",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return DocumentKeywordsResponse.from_dict(result)


class AsyncDocuments:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._context_id = context_id
        self._base = _docs_base(context_id)
        self.keywords = AsyncDocumentKeywords(transport, self._base)

    async def upload(
        self,
        path: str | os.PathLike[str] | IO[bytes] | bytes | bytearray | memoryview,
        *,
        content_type: str | None = None,
        filename: str | None = None,
        title: str | None = None,
        source: str | None = None,
        on_behalf_of: str | None = None,
    ) -> UploadResponse:
        file_payload, resolved_filename = _resolve_file(path, filename)
        form = build_aiohttp_form(
            file=file_payload,
            filename=resolved_filename,
            mime_type=content_type,
            fields=_metadata_fields(title, source),
        )
        result = await self._transport.request(
            "POST",
            self._base,
            data=form,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return UploadResponse.from_dict(result)

    async def get(self, doc_id: str, *, on_behalf_of: str | None = None) -> Document:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(doc_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return Document.from_dict(result)

    async def delete(self, doc_id: str, *, on_behalf_of: str | None = None) -> None:
        await self._transport.request(
            "DELETE",
            f"{self._base}/{quote_path(doc_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )

    async def list(
        self,
        *,
        status: str | None = None,
        mime_type: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        on_behalf_of: str | None = None,
    ) -> DocumentPage:
        params = {
            "status": status,
            "mime_type": mime_type,
            "page": page,
            "page_size": page_size,
        }
        result = await self._transport.request(
            "GET",
            self._base,
            params=params,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return DocumentPage.from_dict(result)

    async def query(
        self,
        query: str,
        *,
        k: int | None = None,
        mode: str | None = None,
        threshold: float | None = None,
        expand_graph: bool | None = None,
        filter: Mapping[str, Any] | None = None,
        on_behalf_of: str | None = None,
    ) -> DocumentQueryResponse:
        payload = _query_body(
            query,
            k=k,
            mode=mode,
            threshold=threshold,
            expand_graph=expand_graph,
            filter=filter,
        )
        result = await self._transport.request(
            "POST",
            f"{self._base}/query",
            json=payload,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return DocumentQueryResponse.from_dict(result)

    async def fetch_raw(self, doc_id: str, *, on_behalf_of: str | None = None) -> bytes:
        response = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(doc_id)}/raw",
            return_raw=True,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        try:
            return await response.read()
        finally:
            response.release()

    async def reprocess(
        self, doc_id: str, *, on_behalf_of: str | None = None
    ) -> UploadResponse:
        result = await self._transport.request(
            "PUT",
            f"{self._base}/{quote_path(doc_id)}",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return UploadResponse.from_dict(result)

    async def recompute_links(
        self, *, on_behalf_of: str | None = None
    ) -> RecomputeLinksResponse:
        result = await self._transport.request(
            "POST",
            f"{self._base}/recompute-links",
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return RecomputeLinksResponse.from_dict(result)

    async def chunks(
        self,
        doc_id: str,
        *,
        page: int | None = None,
        page_size: int | None = None,
        on_behalf_of: str | None = None,
    ) -> ChunkPage:
        result = await self._transport.request(
            "GET",
            f"{self._base}/{quote_path(doc_id)}/chunks",
            params={"page": page, "page_size": page_size},
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return ChunkPage.from_dict(result)


__all__ = [
    "BlockingDocuments",
    "AsyncDocuments",
    "BlockingDocumentKeywords",
    "AsyncDocumentKeywords",
]
