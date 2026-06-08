from __future__ import annotations

import os
from pathlib import Path
from typing import IO, Any

from surrealdb.spectron._models import UploadResponse
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    build_aiohttp_form,
    build_multipart_payload,
    on_behalf_of_header,
    quote_path,
)


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


def _documents_path(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}/documents"


class BlockingDocuments:
    def __init__(self, transport: BlockingTransport, context_id: str) -> None:
        self._transport = transport
        self._context_id = context_id

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
            _documents_path(self._context_id),
            files=files,
            data=data or None,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return UploadResponse.from_dict(result)


class AsyncDocuments:
    def __init__(self, transport: AsyncTransport, context_id: str) -> None:
        self._transport = transport
        self._context_id = context_id

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
            _documents_path(self._context_id),
            data=form,
            headers=on_behalf_of_header(on_behalf_of) or None,
        )
        return UploadResponse.from_dict(result)


__all__ = ["BlockingDocuments", "AsyncDocuments"]
