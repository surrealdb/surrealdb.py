from __future__ import annotations

import asyncio
import io
import json as _json
import os
import time
from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import quote

import aiohttp
import requests

from surrealdb.spectron._errors import SpectronError, error_from_response
from surrealdb.spectron._retry import backoff_schedule, should_retry

DEFAULT_BASE_URL = "https://api.spectron.dev"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
_USER_AGENT = "surrealdb-py-spectron/1.0"


def _resolve_api_key(api_key: str | None) -> str:
    if api_key is not None and api_key != "":
        return api_key
    env = os.environ.get("SPECTRON_API_KEY")
    if env:
        return env
    raise ValueError(
        "Spectron API key is required. Pass api_key=... or set SPECTRON_API_KEY."
    )


def _build_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def quote_path(value: str) -> str:
    return quote(str(value), safe="")


def _decode_json(body: bytes | str | None) -> Any:
    if body is None or body == b"" or body == "":
        return None
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        return _json.loads(body)
    except (ValueError, TypeError):
        return body


class _BaseTransport:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = _resolve_api_key(api_key)
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(
        self,
        *,
        extra: Mapping[str, str] | None = None,
        content_type: str | None = "application/json",
    ) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        if content_type:
            headers["Content-Type"] = content_type
        if extra:
            for k, v in extra.items():
                if v is not None:
                    headers[k] = v
        return headers


class BlockingTransport(_BaseTransport):
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._session = session or requests.Session()
        self._owns_session = session is None

    def close(self) -> None:
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> BlockingTransport:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stream: bool = False,
        allow_redirects: bool = True,
        return_raw: bool = False,
    ) -> Any:
        url = _build_url(self.base_url, path)
        attempt = 0
        schedule = backoff_schedule(self.max_retries)
        method_upper = method.upper()
        content_type: str | None = "application/json" if json is not None else None
        if files is not None or data is not None:
            content_type = None
        h = self._headers(extra=headers, content_type=content_type)
        if params is not None:
            params = {k: v for k, v in params.items() if v is not None}
        while True:
            try:
                response = self._session.request(
                    method_upper,
                    url,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    headers=h,
                    timeout=timeout if timeout is not None else self.timeout,
                    stream=stream,
                    allow_redirects=allow_redirects,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                if not should_retry(method_upper, None, attempt, self.max_retries):
                    raise SpectronError(
                        status=0,
                        title="Connection failed",
                        detail=str(exc),
                    ) from exc
                time.sleep(schedule[attempt])
                attempt += 1
                continue

            status = response.status_code
            if status >= 400 and should_retry(method_upper, status, attempt, self.max_retries):
                time.sleep(schedule[attempt])
                attempt += 1
                continue

            if status >= 400:
                body = _decode_json(response.content)
                raise error_from_response(status, body, dict(response.headers))

            if return_raw or stream:
                return response
            if status == 204 or not response.content:
                return None
            return _decode_json(response.content)

    def get(self, path: str, **kw: Any) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw: Any) -> Any:
        return self.request("PUT", path, **kw)

    def patch(self, path: str, **kw: Any) -> Any:
        return self.request("PATCH", path, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.request("DELETE", path, **kw)

    def stream_bytes(self, path: str, **kw: Any) -> Iterator[bytes]:
        response = self.request("GET", path, stream=True, return_raw=True, **kw)
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            response.close()


class AsyncTransport(_BaseTransport):
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._session = session
        self._owns_session = session is None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> AsyncTransport:
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        return_raw: bool = False,
    ) -> Any:
        session = await self._ensure_session()
        url = _build_url(self.base_url, path)
        attempt = 0
        schedule = backoff_schedule(self.max_retries)
        method_upper = method.upper()
        content_type: str | None = "application/json" if json is not None else None
        if data is not None:
            content_type = None
        h = self._headers(extra=headers, content_type=content_type)
        if params is not None:
            params = {k: v for k, v in params.items() if v is not None}
        req_timeout = aiohttp.ClientTimeout(total=timeout if timeout is not None else self.timeout)

        while True:
            try:
                response = await session.request(
                    method_upper,
                    url,
                    params=params,
                    json=json,
                    data=data,
                    headers=h,
                    timeout=req_timeout,
                    allow_redirects=True,
                )
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as exc:
                if not should_retry(method_upper, None, attempt, self.max_retries):
                    raise SpectronError(
                        status=0,
                        title="Connection failed",
                        detail=str(exc),
                    ) from exc
                await asyncio.sleep(schedule[attempt])
                attempt += 1
                continue

            status = response.status
            if status >= 400 and should_retry(method_upper, status, attempt, self.max_retries):
                response.release()
                await asyncio.sleep(schedule[attempt])
                attempt += 1
                continue

            if status >= 400:
                body_bytes = await response.read()
                headers_dict = {k: v for k, v in response.headers.items()}
                response.release()
                body = _decode_json(body_bytes)
                raise error_from_response(status, body, headers_dict)

            if return_raw:
                return response
            if status == 204:
                response.release()
                return None
            body_bytes = await response.read()
            response.release()
            if not body_bytes:
                return None
            return _decode_json(body_bytes)

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.request("POST", path, **kw)

    async def put(self, path: str, **kw: Any) -> Any:
        return await self.request("PUT", path, **kw)

    async def patch(self, path: str, **kw: Any) -> Any:
        return await self.request("PATCH", path, **kw)

    async def delete(self, path: str, **kw: Any) -> Any:
        return await self.request("DELETE", path, **kw)


def build_multipart_payload(
    *,
    file: bytes | bytearray | memoryview | io.IOBase | str,
    filename: str | None,
    mime_type: str | None,
    fields: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], dict[str, Any]]:
    if isinstance(file, str):
        fp = open(file, "rb")  # noqa: SIM115
        if filename is None:
            filename = os.path.basename(file)
        payload: Any = fp
    elif isinstance(file, (bytes, bytearray, memoryview)):
        payload = bytes(file)
    else:
        payload = file
    files: dict[str, tuple[str | None, Any, str | None]] = {
        "file": (filename, payload, mime_type),
    }
    data: dict[str, Any] = {}
    if fields:
        for k, v in fields.items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                data[k] = _json.dumps(v)
            else:
                data[k] = str(v)
    return files, data


def build_aiohttp_form(
    *,
    file: bytes | bytearray | memoryview | io.IOBase | str,
    filename: str | None,
    mime_type: str | None,
    fields: Mapping[str, Any] | None,
) -> aiohttp.FormData:
    form = aiohttp.FormData()
    payload: Any
    if isinstance(file, str):
        with open(file, "rb") as fp:
            payload = fp.read()
        if filename is None:
            filename = os.path.basename(file)
    elif isinstance(file, (bytes, bytearray, memoryview)):
        payload = bytes(file)
    else:
        payload = file.read() if hasattr(file, "read") else file
    form.add_field(
        "file",
        payload,
        filename=filename or "upload",
        content_type=mime_type or "application/octet-stream",
    )
    if fields:
        for k, v in fields.items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                form.add_field(k, _json.dumps(v), content_type="application/json")
            else:
                form.add_field(k, str(v))
    return form


__all__ = [
    "BlockingTransport",
    "AsyncTransport",
    "build_multipart_payload",
    "build_aiohttp_form",
    "quote_path",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "DEFAULT_MAX_RETRIES",
]
