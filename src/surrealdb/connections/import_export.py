"""``import_()`` and ``export()``, over the server's ``/import`` and ``/export``.

Neither has an RPC method, so every transport makes a plain HTTP request to the
same server, carrying the connection's token, namespace and database.

``export()`` returns the SurrealQL the server produced, and ``export_to()``
writes it to a file as it arrives, for exports too large to hold in memory.
With no options they use ``GET /export``, which every supported server
answers. With options they post them to ``/export``, which SurrealDB 2.0 does
not accept.

``import_()`` sends SurrealQL - an export, or anything else that starts with
``OPTION IMPORT;``, which SurrealDB 3 requires. A statement that fails does not
stop the rest, so the server's answer is read for failures: SurrealDB 3.1 and
later answers 422 with only the failed statements, and older servers answer
200 with every statement's result. Either way any failures are raised together
as :class:`~surrealdb.errors.ImportFailedError`.

Neither is bound by the connection's default ``timeout``, as in the JS SDK: a
transfer is long-running, and a limit meant for a single reply would cut it
short. Only a ``with db.timeout(seconds):`` block around the call limits it.
"""

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import IO, Any, TypeVar

import aiohttp
import requests

from surrealdb.connections.http_body import iter_body, read_body
from surrealdb.connections.timeouts import describe
from surrealdb.connections.url import Url, UrlScheme
from surrealdb.errors import (
    ConnectionUnavailableError,
    HttpStatusError,
    ImportFailedError,
    TransportTimeoutError,
    UnsupportedFeatureError,
    parse_query_error,
)
from surrealdb.features import parse_version

ExportTables = bool | Sequence[str] | Mapping[str, Sequence[str]]


@dataclass(frozen=True)
class ExportOptions:
    """What ``export()`` includes. ``None`` leaves the server's default.

    Attributes:
        users, accesses, params, functions, analyzers, versions, records,
        sequences: Whether to include each kind of definition or data.
        tables: ``True`` or ``False`` for every table, a table name or a
            list of them, or ``{"exclude": [...]}`` for every table but those.
        versions: Not accepted by SurrealDB 3.3.1 and later, whose exports
            hold only the current state of each record.
    """

    users: bool | None = None
    accesses: bool | None = None
    params: bool | None = None
    functions: bool | None = None
    analyzers: bool | None = None
    tables: ExportTables | None = None
    versions: bool | None = None
    records: bool | None = None
    sequences: bool | None = None

    def body(self) -> dict[str, Any] | None:
        """The JSON the server takes, or ``None`` when nothing was chosen."""
        chosen: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if value is None:
                continue
            if name == "tables" and isinstance(value, Mapping):
                value = {key: _names(names) for key, names in value.items()}
            elif name == "tables" and not isinstance(value, bool):
                value = _names(value)
            chosen[name] = value
        return chosen or None

    def check(self, server_version: str | None) -> None:
        """Refuse an option the server is known not to accept."""
        parsed = parse_version(server_version) if server_version else None
        if self.versions and parsed is not None and parsed >= _NO_VERSIONS:
            raise UnsupportedFeatureError(
                f"SurrealDB {server_version} does not export record versions: "
                "since 3.3.1 an export holds only the current state of each "
                "record. Leave ExportOptions.versions unset"
            )


_NO_VERSIONS = (3, 3, 1)


def _names(names: str | Sequence[str]) -> list[str]:
    """A table name or a sequence of them, as a list - never a str's letters."""
    return [names] if isinstance(names, str) else list(names)


ImportData = str | bytes | os.PathLike[str]
ExportTarget = str | os.PathLike[str] | IO[bytes]

_CHUNK = 1 << 16

_T = TypeVar("_T")


def _base(url: Url) -> str:
    rest = url.raw_url.split("://", 1)[1]
    scheme = "https" if url.scheme in (UrlScheme.HTTPS, UrlScheme.WSS) else "http"
    return f"{scheme}://{rest}"


def _headers(
    token: str | None, namespace: str | None, database: str | None
) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if namespace is not None:
        headers["surreal-ns"] = namespace
    if database is not None:
        headers["surreal-db"] = database
    return headers


@contextmanager
def _payload(data: ImportData) -> Generator[bytes | IO[bytes], None, None]:
    """The request body: a file is passed open, to be streamed, not read."""
    if isinstance(data, bytes):
        yield data
    elif isinstance(data, str):
        yield data.encode()
    else:
        with open(data, "rb") as source:
            yield source


@contextmanager
def _sink(target: ExportTarget) -> Generator[IO[bytes], None, None]:
    """The file to write an export to: opened from a path, or as given."""
    if isinstance(target, (str, os.PathLike)):
        with open(target, "wb") as sink:
            yield sink
    else:
        yield target


def _check_import(status: int, body: str, endpoint: str) -> None:
    """Raise for an import the server did not fully apply."""
    if status not in (200, 422):
        raise HttpStatusError(status, _server_message(body), endpoint)
    try:
        results = json.loads(body) if body else []
    except ValueError:
        if status == 200:
            return
        raise HttpStatusError(status, body, endpoint) from None
    if not isinstance(results, list):
        results = []
    failures = [
        parse_query_error(result)
        for result in results
        if isinstance(result, dict) and result.get("status") == "ERR"
    ]
    if failures or status == 422:
        raise ImportFailedError(failures)


def _check_export(status: int, body: str, endpoint: str, posted: bool) -> None:
    if status == 405 and posted:
        raise UnsupportedFeatureError(
            "export options need a server that accepts POST /export, which "
            "SurrealDB 2.0 does not; call export() without options there"
        )
    if status != 200:
        raise HttpStatusError(status, _server_message(body), endpoint)


def _server_message(body: str) -> str:
    """The useful part of an HTTP error body: its ``information``, if any."""
    try:
        parsed = json.loads(body)
    except ValueError:
        return body[:500]
    if isinstance(parsed, dict) and isinstance(parsed.get("information"), str):
        return parsed["information"]
    return body[:500]


def _timed_out(
    action: str, endpoint: str, timeout: float | None
) -> TransportTimeoutError:
    return TransportTimeoutError(
        f"timed out {action} {endpoint}: no reply {describe(timeout)}"
    )


def _export_response(
    url: Url,
    options: ExportOptions,
    timeout: float | None,
    headers: dict[str, str],
) -> requests.Response:
    endpoint = f"{_base(url)}/export"
    body = options.body()
    try:
        if body is None:
            response = requests.get(
                endpoint, headers=headers, timeout=timeout, stream=True
            )
        else:
            response = requests.post(
                endpoint, headers=headers, json=body, timeout=timeout, stream=True
            )
    except requests.Timeout as exc:
        raise _timed_out("exporting from", endpoint, timeout) from exc
    except requests.RequestException as exc:
        raise ConnectionUnavailableError(
            f"could not export from {endpoint}: {exc}"
        ) from exc
    if response.status_code != 200:
        with response:
            _check_export(
                response.status_code, response.text, endpoint, body is not None
            )
    return response


def export_sql(
    url: Url,
    options: ExportOptions,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> str:
    """Export from the server behind *url*, as SurrealQL."""
    deadline = _deadline(timeout)
    headers = _headers(token, namespace, database)
    with _export_response(url, options, timeout, headers) as response:
        return _read(
            response,
            timeout,
            lambda: read_body(response, deadline).decode(errors="replace"),
        )


def export_sql_to(
    url: Url,
    options: ExportOptions,
    target: ExportTarget,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> None:
    """Export from the server behind *url* into *target*, chunk by chunk."""
    deadline = _deadline(timeout)
    headers = _headers(token, namespace, database)
    with _export_response(url, options, timeout, headers) as response:

        def copy() -> None:
            with _sink(target) as sink:
                for chunk in iter_body(response, deadline):
                    sink.write(chunk)

        _read(response, timeout, copy)


def _deadline(timeout: float | None) -> float | None:
    return None if timeout is None else time.monotonic() + timeout


def _read(
    response: requests.Response, timeout: float | None, read: Callable[[], _T]
) -> _T:
    """Run *read* on a streamed export, mapping a stalled or broken body."""
    endpoint = response.url
    try:
        return read()
    except (requests.Timeout, TimeoutError) as exc:
        raise _timed_out("exporting from", endpoint, timeout) from exc
    except requests.RequestException as exc:
        raise ConnectionUnavailableError(
            f"the export from {endpoint} broke off: {exc}"
        ) from exc


def import_sql(
    url: Url,
    data: ImportData,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> None:
    """Import SurrealQL into the server behind *url*."""
    endpoint = f"{_base(url)}/import"
    deadline = _deadline(timeout)
    try:
        with _payload(data) as payload:
            response = requests.post(
                endpoint,
                headers=_headers(token, namespace, database),
                data=payload,
                timeout=timeout,
                stream=True,
            )
        with response:
            body = read_body(response, deadline)
    except (requests.Timeout, TimeoutError) as exc:
        raise _timed_out("importing into", endpoint, timeout) from exc
    except requests.RequestException as exc:
        raise ConnectionUnavailableError(
            f"could not import into {endpoint}: {exc}"
        ) from exc
    _check_import(response.status_code, body.decode(errors="replace"), endpoint)


async def aexport_sql(
    url: Url,
    options: ExportOptions,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> str:
    """The async counterpart of :func:`export_sql`."""
    chunks: list[bytes] = []

    async def keep(chunk: bytes) -> None:
        chunks.append(chunk)

    await _aexport(url, options, timeout, token, namespace, database, keep)
    return b"".join(chunks).decode()


async def aexport_sql_to(
    url: Url,
    options: ExportOptions,
    target: ExportTarget,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> None:
    """The async counterpart of :func:`export_sql_to`.

    The file is opened and written on a worker thread, so a slow disk does
    not hold up the event loop.
    """
    opened: list[IO[bytes]] = []

    async def start() -> None:
        # Only once the server has said yes, so a failed export leaves an
        # existing file - perhaps the last good backup - as it was.
        if isinstance(target, (str, os.PathLike)):
            opened.append(await asyncio.to_thread(open, target, "wb"))
        else:
            opened.append(target)

    async def write(chunk: bytes) -> None:
        await asyncio.to_thread(opened[0].write, chunk)

    try:
        await _aexport(url, options, timeout, token, namespace, database, write, start)
    finally:
        if opened and opened[0] is not target:
            await asyncio.to_thread(opened[0].close)


async def _aexport(
    url: Url,
    options: ExportOptions,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
    take: Callable[[bytes], Awaitable[None]],
    start: Callable[[], Awaitable[None]] | None = None,
) -> None:
    endpoint = f"{_base(url)}/export"
    headers = _headers(token, namespace, database)
    body = options.body()
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            if body is None:
                request = session.get(endpoint, headers=headers)
            else:
                request = session.post(endpoint, headers=headers, json=body)
            async with request as response:
                if response.status != 200:
                    _check_export(
                        response.status,
                        await response.text(),
                        endpoint,
                        body is not None,
                    )
                if start is not None:
                    await start()
                async for chunk in response.content.iter_chunked(_CHUNK):
                    await take(chunk)
    except TimeoutError as exc:
        raise _timed_out("exporting from", endpoint, timeout) from exc
    except aiohttp.ClientError as exc:
        raise ConnectionUnavailableError(
            f"could not export from {endpoint}: {exc}"
        ) from exc


async def aimport_sql(
    url: Url,
    data: ImportData,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> None:
    """The async counterpart of :func:`import_sql`."""
    endpoint = f"{_base(url)}/import"
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            with _payload(data) as payload:
                async with session.post(
                    endpoint,
                    headers=_headers(token, namespace, database),
                    data=payload,
                ) as response:
                    status, text = response.status, await response.text()
    except TimeoutError as exc:
        raise _timed_out("importing into", endpoint, timeout) from exc
    except aiohttp.ClientError as exc:
        raise ConnectionUnavailableError(
            f"could not import into {endpoint}: {exc}"
        ) from exc
    _check_import(status, text, endpoint)
