"""``import_()`` and ``export()``, over the server's ``/import`` and ``/export``.

Neither has an RPC method, so every transport makes a plain HTTP request to the
same server, carrying the connection's token, namespace and database.

``export()`` returns the SurrealQL the server produced. With no options it uses
``GET /export``, which every supported server answers. With options it posts
them to ``/export``, which SurrealDB 2.0 does not accept.

``import_()`` sends SurrealQL - an export, or anything else that starts with
``OPTION IMPORT;``, which SurrealDB 3 requires. A statement that fails does not
stop the rest, so the server's answer is read for failures: SurrealDB 3.1 and
later answers 422 with only the failed statements, and older servers answer
200 with every statement's result. Either way any failures are raised together
as :class:`~surrealdb.errors.ImportFailedError`.
"""

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import aiohttp
import requests

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

ExportTables = bool | Sequence[str] | Mapping[str, Sequence[str]]


@dataclass(frozen=True)
class ExportOptions:
    """What ``export()`` includes. ``None`` leaves the server's default.

    Attributes:
        users, accesses, params, functions, analyzers, versions, records,
        sequences: Whether to include each kind of definition or data.
        tables: ``True`` or ``False`` for every table, a list of table names,
            or ``{"exclude": [...]}`` for every table but those.
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
            if name == "tables" and not isinstance(value, (bool, Mapping)):
                value = list(value)
            elif name == "tables" and isinstance(value, Mapping):
                value = {key: list(names) for key, names in value.items()}
            chosen[name] = value
        return chosen or None


ImportData = str | bytes | os.PathLike[str]


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


def _payload(data: ImportData) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode()
    with open(data, "rb") as source:
        return source.read()


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


def export_sql(
    url: Url,
    options: ExportOptions,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> str:
    """Export from the server behind *url*, as SurrealQL."""
    endpoint = f"{_base(url)}/export"
    headers = _headers(token, namespace, database)
    body = options.body()
    try:
        if body is None:
            response = requests.get(endpoint, headers=headers, timeout=timeout)
        else:
            response = requests.post(
                endpoint, headers=headers, json=body, timeout=timeout
            )
    except requests.Timeout as exc:
        raise _timed_out("exporting from", endpoint, timeout) from exc
    except requests.RequestException as exc:
        raise ConnectionUnavailableError(
            f"could not export from {endpoint}: {exc}"
        ) from exc
    _check_export(response.status_code, response.text, endpoint, body is not None)
    return response.text


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
    try:
        response = requests.post(
            endpoint,
            headers=_headers(token, namespace, database),
            data=_payload(data),
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise _timed_out("importing into", endpoint, timeout) from exc
    except requests.RequestException as exc:
        raise ConnectionUnavailableError(
            f"could not import into {endpoint}: {exc}"
        ) from exc
    _check_import(response.status_code, response.text, endpoint)


async def aexport_sql(
    url: Url,
    options: ExportOptions,
    timeout: float | None,
    token: str | None,
    namespace: str | None,
    database: str | None,
) -> str:
    """The async counterpart of :func:`export_sql`."""
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
                status, text = response.status, await response.text()
    except TimeoutError as exc:
        raise _timed_out("exporting from", endpoint, timeout) from exc
    except aiohttp.ClientError as exc:
        raise ConnectionUnavailableError(
            f"could not export from {endpoint}: {exc}"
        ) from exc
    _check_export(status, text, endpoint, body is not None)
    return text


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
        async with (
            aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session,
            session.post(
                endpoint,
                headers=_headers(token, namespace, database),
                data=_payload(data),
            ) as response,
        ):
            status, text = response.status, await response.text()
    except TimeoutError as exc:
        raise _timed_out("importing into", endpoint, timeout) from exc
    except aiohttp.ClientError as exc:
        raise ConnectionUnavailableError(
            f"could not import into {endpoint}: {exc}"
        ) from exc
    _check_import(status, text, endpoint)
