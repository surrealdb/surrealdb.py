from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO, Any

from surrealdb.spectron._models import UploadResponse
from surrealdb.spectron._transport import (
    AsyncTransport,
    BlockingTransport,
    build_aiohttp_form,
    build_multipart_payload,
    quote_path,
)

ScopeArg = Mapping[str, str] | Sequence[tuple[str, str]] | None


def _scope_pairs(scope: ScopeArg) -> list[dict[str, str]]:
    if scope is None:
        return []
    items = scope.items() if isinstance(scope, Mapping) else scope
    return [{"key": str(k), "value": str(v)} for k, v in items]


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
        scope: ScopeArg = None,
    ) -> UploadResponse:
        file_payload, resolved_filename = _resolve_file(path, filename)
        scope_pairs = _scope_pairs(scope)
        fields: dict[str, Any] = {}
        if scope_pairs:
            fields["scope"] = scope_pairs
        files, data = build_multipart_payload(
            file=file_payload,
            filename=resolved_filename,
            mime_type=content_type,
            fields=fields,
        )
        result = self._transport.request(
            "POST",
            _documents_path(self._context_id),
            files=files,
            data=data or None,
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
        scope: ScopeArg = None,
    ) -> UploadResponse:
        file_payload, resolved_filename = _resolve_file(path, filename)
        scope_pairs = _scope_pairs(scope)
        fields: dict[str, Any] = {}
        if scope_pairs:
            fields["scope"] = scope_pairs
        form = build_aiohttp_form(
            file=file_payload,
            filename=resolved_filename,
            mime_type=content_type,
            fields=fields,
        )
        result = await self._transport.request(
            "POST",
            _documents_path(self._context_id),
            data=form,
        )
        return UploadResponse.from_dict(result)


__all__ = ["BlockingDocuments", "AsyncDocuments"]
