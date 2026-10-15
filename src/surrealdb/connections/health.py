"""``health()``: the server's ``/health`` endpoint, which has no RPC equivalent."""

import aiohttp
import requests

from surrealdb.connections.timeouts import describe
from surrealdb.connections.url import Url, UrlScheme
from surrealdb.errors import ConnectionUnavailableError, TransportTimeoutError


def health_url(url: Url) -> str:
    """The ``/health`` endpoint for *url*, over HTTP whatever its scheme."""
    rest = url.raw_url.split("://", 1)[1]
    scheme = "https" if url.scheme in (UrlScheme.HTTPS, UrlScheme.WSS) else "http"
    return f"{scheme}://{rest}/health"


def _unhealthy(endpoint: str, status: int) -> ConnectionUnavailableError:
    return ConnectionUnavailableError(
        f"the server at {endpoint} is not healthy: it answered HTTP {status}"
    )


def check_health(url: Url, timeout: float | None) -> None:
    """Raise unless the server says it is healthy."""
    endpoint = health_url(url)
    try:
        response = requests.get(endpoint, timeout=timeout)
    except requests.Timeout as exc:
        raise TransportTimeoutError(
            f"timed out checking the health of {endpoint}: no reply {describe(timeout)}"
        ) from exc
    except requests.RequestException as exc:
        raise ConnectionUnavailableError(
            f"could not reach {endpoint} to check its health: {exc}"
        ) from exc
    if response.status_code != 200:
        raise _unhealthy(endpoint, response.status_code)


async def acheck_health(url: Url, timeout: float | None) -> None:
    """The async counterpart of :func:`check_health`."""
    endpoint = health_url(url)
    try:
        async with (
            aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session,
            session.get(endpoint) as response,
        ):
            status = response.status
    except TimeoutError as exc:
        raise TransportTimeoutError(
            f"timed out checking the health of {endpoint}: no reply {describe(timeout)}"
        ) from exc
    except aiohttp.ClientError as exc:
        raise ConnectionUnavailableError(
            f"could not reach {endpoint} to check its health: {exc}"
        ) from exc
    if status != 200:
        raise _unhealthy(endpoint, status)
